import json
import boto3
import hmac
import hashlib
import base64
from botocore.exceptions import ClientError

def compute_secret_hash(client_secret, username, client_id):
    """Compute the SECRET_HASH for Cognito."""
    message = username + client_id
    dig = hmac.new(client_secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).digest()
    return base64.b64encode(dig).decode()

def lambda_handler(event, context):
    client = boto3.client('cognito-idp')
    
    # Extract user credentials from the event
    email = event['email'] 
    password = event['password']
    client_id = "6mir9pof7b33docg1j3p0ntn71"  #Cognito App Client ID
    client_secret = "s4jl77f2r3mlqus4t1bmqh43v0nr0mfjjcc885iheamp2a78t7h"
    
    try:
        secret_hash = compute_secret_hash(client_secret, email, client_id)

        # Authenticate the user
        response = client.initiate_auth(
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': email,
                'PASSWORD': password,
                'SECRET_HASH': secret_hash 
            },
            ClientId=client_id
        )
        return {
            'statusCode': 200,
            'body': response
        }
    except client.exceptions.NotAuthorizedException:
        return {
            'statusCode': 401,
            'body': 'Incorrect username or password.'
        }
    except Exception as e:
        return {
            'statusCode': 400,
            'body': str(e)
        }
