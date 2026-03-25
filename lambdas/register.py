"""
register.py — AWS Lambda: New User Registration

This Lambda function handles new user registration for the FeastFleet delivery
application. It performs a two-phase registration: first creating the user in
Amazon Cognito (for authentication), then storing the user's profile in DynamoDB
(for application-level data).

Registration Flow:
    1. Check DynamoDB to ensure no existing account uses the provided email.
    2. Register the user in the Cognito User Pool via sign_up().
    3. Auto-confirm the user (bypasses the email verification step) via
       admin_confirm_sign_up(), so the user can log in immediately.
    4. Retrieve the Cognito-assigned 'sub' UUID for the user.
    5. Persist the user's profile (keyed by the Cognito 'sub') to the DynamoDB
       'User' table.

AWS Services Used:
    - Amazon Cognito Identity Provider (cognito-idp): Manages user identity and
      authentication credentials.
    - Amazon DynamoDB: Stores user profile data, with a GSI on 'email' to support
      duplicate-email detection before registration.

Event Structure (expected input):
    {
        "email":        "<user's email address — used as the Cognito username>",
        "password":     "<user's desired password>",
        "given_name":   "<user's first name>",
        "family_name":  "<user's last name>",
        "address":      "<user's delivery address>",
        "phone_number": "<user's phone number in E.164 format>"
    }

Returns:
    - 200 with a success message on successful registration
    - 400 if the email already exists (in DynamoDB or Cognito), or if any
      other registration error occurs
"""

import boto3
import uuid
import hmac
import hashlib
import base64
from botocore.exceptions import ClientError
import json
from boto3.dynamodb.conditions import Key


def compute_secret_hash(client_secret, username, client_id):
    """
    Compute the SECRET_HASH required by Cognito when the App Client has a client secret.

    Cognito mandates this HMAC-SHA256 hash for sign_up() calls when the App Client
    is configured with a secret. It prevents unauthorized use of the public client ID.
    The hash is computed as:
        BASE64( HMAC_SHA256(key=client_secret, msg=username + client_id) )

    Args:
        client_secret (str): The Cognito App Client secret.
        username      (str): The username (email) being registered.
        client_id     (str): The Cognito App Client ID.

    Returns:
        str: Base64-encoded HMAC-SHA256 digest to pass as SecretHash.
    """
    # Concatenate username and client_id to form the message to sign
    message = username + client_id

    # Sign the message using HMAC-SHA256 with the client secret as the key
    dig = hmac.new(client_secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).digest()

    # Return the Base64-encoded digest as a plain string
    return base64.b64encode(dig).decode()


def check_user_exists_by_email(table, email):
    """
    Query the DynamoDB 'User' table's email GSI to check if an account with
    the given email already exists.

    Using a Global Secondary Index (GSI) on 'email' allows an efficient O(1) lookup
    rather than a full table scan, which is critical for scalability.

    Args:
        table (boto3.resource DynamoDB.Table): The DynamoDB Table resource object.
        email (str): The email address to check for duplicates.

    Returns:
        bool: True if a user with that email already exists, False otherwise.
    """
    response = table.query(
        IndexName="email-index",  # Replace with the name of your GSI
        KeyConditionExpression=Key('email').eq(email)
    )
    # Check if any items match the query
    if response['Count'] > 0:
        return True  # User exists
    else:
        return False  # User does not exist


def lambda_handler(event, context):
    """
    AWS Lambda entry point for new user registration.

    Orchestrates the full registration workflow: duplicate check, Cognito sign-up,
    auto-confirmation, sub ID retrieval, and DynamoDB profile persistence.

    Args:
        event   (dict): Lambda event payload with user registration fields.
        context (obj):  Lambda context object (runtime metadata, unused here).

    Returns:
        dict: HTTP-style response with 'statusCode' and 'body'.
              200 on successful registration.
              400 if the email already exists, Cognito rejects the request,
              or any other registration-related error occurs.
    """
    # Initialize Cognito and DynamoDB clients
    client = boto3.client('cognito-idp')
    dynamodb_client = boto3.resource('dynamodb')

    dynamodb_table_name = "User"
    table = dynamodb_client.Table(dynamodb_table_name)

    # Extract user details from the event
    email = event['email']  # Email is used for both username and login
    password = event['password']
    given_name = event['given_name']  # First name
    family_name = event['family_name']  # Last name
    address = event['address']  # Address
    phone_number = event['phone_number']  # Phone number

    #Cognito details
    user_pool_id = "us-east-1_rdP8dmCQw"
    client_id = "6mir9pof7b33docg1j3p0ntn71"
    client_secret = "s4jl77f2r3mlqus4t1bmqh43v0nr0mfjjcc885iheamp2a78t7h"

    try:
        # Guard against duplicate registrations by checking DynamoDB first.
        # This check precedes the Cognito call to provide a user-friendly error
        # message and avoid orphaned Cognito accounts.
        if check_user_exists_by_email(table, email):
            return {
                'statusCode': 400,
                'body': 'User with this email already exists in the database.'
            }

        # Compute the HMAC-SHA256 hash required by the Cognito app client secret
        secret_hash = compute_secret_hash(client_secret, email, client_id)

        # Register the new user in the Cognito User Pool.
        # The email is used as the Cognito username to simplify the login flow.
        # All profile attributes are passed as UserAttributes for Cognito to store.
        response = client.sign_up(
            ClientId=client_id,  # Cognito App Client ID
            SecretHash=secret_hash,
            Username=email,  # Use email as the username
            Password=password,
            UserAttributes=[
                {'Name': 'email', 'Value': email},
                {'Name': 'given_name', 'Value': given_name},
                {'Name': 'family_name', 'Value': family_name},
                {'Name': 'address', 'Value': address},
                {'Name': 'phone_number', 'Value': phone_number}
            ]
        )

        # Auto-confirm the user in Cognito — this bypasses the standard email
        # verification step, allowing the user to log in immediately without
        # needing to click a confirmation link.
        client.admin_confirm_sign_up(
            UserPoolId=user_pool_id,
            Username=email
        )

        # Retrieve the full user record from Cognito to extract the 'sub' attribute.
        # The 'sub' is Cognito's globally unique, immutable UUID for the user and
        # is used as the primary key in DynamoDB to decouple storage from email.
        user_details = client.admin_get_user(
            UserPoolId=user_pool_id,
            Username=email
        )

        # Iterate over Cognito UserAttributes to find the 'sub' (subject) UUID
        user_id = None
        for attr in user_details['UserAttributes']:
            if attr['Name'] == 'sub':
                user_id = attr['Value']
                break

        # If 'sub' was not found, something is wrong with the Cognito response;
        # raise an exception to prevent writing an invalid record to DynamoDB
        if not user_id:
            raise Exception("Unable to retrieve Cognito 'sub' ID for the user.")

        # Save the user's information to DynamoDB.
        # The Cognito 'sub' UUID is used as the primary key ('user_id') so that
        # the record remains stable even if the user changes their email address.
        dynamodb_response = table.put_item(
            Item={
                'user_id': user_id,  # Primary key — Cognito 'sub' UUID
                'email': email,
                'given_name': given_name,
                'family_name': family_name,
                'address': address,
                'phone_number': phone_number
            }
        )

        return {
            'statusCode': 200,
            'body': 'User registered successfully.'
        }

    except client.exceptions.UsernameExistsException:
        # Cognito raises this when the email is already registered in the User Pool
        # but was not caught by the DynamoDB pre-check (e.g., race condition)
        return {
            'statusCode': 400,
            'body': 'User with this email already exists in Cognito.'
        }
    except ClientError as e:
        # Handles known AWS service errors (e.g., invalid password policy, throttling)
        return {
            'statusCode': 400,
            'body': f"An error occurred: {e.response['Error']['Message']}"
        }
    except Exception as e:
        # Catch-all for unexpected errors during registration
        return {
            'statusCode': 400,
            'body': str(e)
        }
