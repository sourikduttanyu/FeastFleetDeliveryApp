"""
login.py — AWS Lambda: User Authentication (Login)

This Lambda function handles user login for the FeastFleet delivery application.
It integrates with Amazon Cognito User Pools to authenticate a user by email and
password using the USER_PASSWORD_AUTH flow.

AWS Services Used:
    - Amazon Cognito Identity Provider (cognito-idp): Authenticates the user and
      issues JWT tokens (IdToken, AccessToken, RefreshToken).

Event Structure (expected input):
    {
        "email":    "<user's email address>",
        "password": "<user's plaintext password>"
    }

Returns:
    - 200 + Cognito AuthenticationResult (JWT tokens) on success
    - 401 if credentials are incorrect
    - 400 for any other error (e.g., user not found, malformed request)
"""

import json
import boto3
import hmac
import hashlib
import base64
from botocore.exceptions import ClientError


def compute_secret_hash(client_secret, username, client_id):
    """
    Compute the SECRET_HASH required by Cognito when an App Client has a secret.

    Cognito requires this HMAC-SHA256 hash whenever the App Client is configured
    with a client secret. It is computed as:
        BASE64( HMAC_SHA256(key=client_secret, msg=username + client_id) )

    Args:
        client_secret (str): The Cognito App Client secret.
        username      (str): The username (email) of the authenticating user.
        client_id     (str): The Cognito App Client ID.

    Returns:
        str: Base64-encoded HMAC-SHA256 digest to be passed as SECRET_HASH.
    """
    # Concatenate username and client_id to form the HMAC message
    message = username + client_id

    # Compute HMAC-SHA256 using the client secret as the key
    dig = hmac.new(client_secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).digest()

    # Base64-encode the raw digest and return as a UTF-8 string
    return base64.b64encode(dig).decode()


def lambda_handler(event, context):
    """
    AWS Lambda entry point for user login.

    Receives user credentials from the event, computes the required Cognito
    SECRET_HASH, and calls Cognito's InitiateAuth API to authenticate the user.
    On success, returns the full Cognito authentication result containing the
    IdToken, AccessToken, and RefreshToken.

    Args:
        event   (dict): Lambda event payload containing 'email' and 'password'.
        context (obj):  Lambda context object (runtime metadata, unused here).

    Returns:
        dict: HTTP-style response with 'statusCode' and 'body'.
              On success (200), 'body' contains the Cognito AuthenticationResult.
              On auth failure (401) or other errors (400), 'body' contains a message.
    """
    # Create a Cognito Identity Provider client using the Lambda execution role's credentials
    client = boto3.client('cognito-idp')

    # Extract user credentials from the incoming event payload
    email = event['email']
    password = event['password']

    # Cognito App Client ID and secret — these must match the User Pool app client configuration
    client_id = "6mir9pof7b33docg1j3p0ntn71"  #Cognito App Client ID
    client_secret = "s4jl77f2r3mlqus4t1bmqh43v0nr0mfjjcc885iheamp2a78t7h"

    try:
        # Compute the HMAC-SHA256 SECRET_HASH required by the Cognito app client
        secret_hash = compute_secret_hash(client_secret, email, client_id)

        # Authenticate the user via Cognito using email/password auth flow.
        # USER_PASSWORD_AUTH is a standard SRP-less flow suitable for server-side auth.
        # On success, Cognito returns IdToken, AccessToken, and RefreshToken.
        response = client.initiate_auth(
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': email,
                'PASSWORD': password,
                'SECRET_HASH': secret_hash  # Required because the app client has a secret
            },
            ClientId=client_id
        )

        return {
            'statusCode': 200,
            # 'headers': {
            #     "Access-Control-Allow-Origin": "*",
            #     "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            #     "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token"
            # },
            'body': response  # Contains AuthenticationResult with JWT tokens
        }

    except client.exceptions.NotAuthorizedException:
        # Cognito raises NotAuthorizedException when the email/password combination is wrong
        return {
            'statusCode': 401,
            'body': 'Incorrect username or password.'
        }
    except Exception as e:
        # Catch-all for unexpected errors (e.g., user not found, network issues)
        return {
            'statusCode': 400,
            'body': str(e)
        }
