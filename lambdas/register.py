import boto3
import uuid
import hmac
import hashlib
import base64
from botocore.exceptions import ClientError
import json
from boto3.dynamodb.conditions import Key

def compute_secret_hash(client_secret, username, client_id):
    """Compute the SECRET_HASH for Cognito."""
    message = username + client_id
    dig = hmac.new(client_secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).digest()
    return base64.b64encode(dig).decode()

def check_user_exists_by_email(table, email):
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
        if check_user_exists_by_email(table, email):
            return {
                'statusCode': 400,
                'body': 'User with this email already exists in the database.'
            }

        secret_hash = compute_secret_hash(client_secret, email, client_id)

        # Create a new user in Cognito User Pool
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

        # Auto-confirm the user in Cognito
        client.admin_confirm_sign_up(
            UserPoolId=user_pool_id,
            Username=email
        )

        # Generate a unique user ID for DynamoDB
        user_id = str(uuid.uuid4())

        # Save the user's information to DynamoDB
        dynamodb_response = table.put_item(
            Item={
                'user_id': user_id,  # Primary key
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
        return {
            'statusCode': 400,
            'body': 'User with this email already exists in Cognito.'
        }
    except ClientError as e:
        return {
            'statusCode': 400,
            'body': f"An error occurred: {e.response['Error']['Message']}"
        }
    except Exception as e:
        return {
            'statusCode': 400,
            'body': str(e)
        }
