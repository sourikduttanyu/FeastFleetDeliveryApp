import json
import boto3
from botocore.exceptions import ClientError

def lambda_handler(event, context):
    # Initialize the Cognito client
    client = boto3.client('cognito-idp')
    
    # Extract the access token from the event
    access_token = event.get('access_token')
    
    if not access_token:
        return {
            'statusCode': 400,
            'body': 'Access token is required for logout.'
        }
    
    try:
        # Call Cognito to sign the user out of all devices/sessions
        response = client.global_sign_out(
            AccessToken=access_token
        )
        
        return {
            'statusCode': 200,
            'body': 'User logged out successfully.'
        }
    except client.exceptions.NotAuthorizedException:
        return {
            'statusCode': 401,
            'body': 'Invalid or expired access token.'
        }
    except ClientError as e:
        return {
            'statusCode': 500,
            'body': f"An error occurred: {e.response['Error']['Message']}"
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': f"Internal server error: {str(e)}"
        }
