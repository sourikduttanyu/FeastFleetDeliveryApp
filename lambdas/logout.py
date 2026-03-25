"""
logout.py — AWS Lambda: User Logout (Global Sign-Out)

This Lambda function handles user logout for the FeastFleet delivery application.
It integrates with Amazon Cognito to perform a global sign-out, which invalidates
all active sessions and refresh tokens for the authenticated user across all devices.

AWS Services Used:
    - Amazon Cognito Identity Provider (cognito-idp): Revokes all sessions tied to
      the provided access token via the GlobalSignOut API call.

Event Structure (expected input):
    {
        "access_token": "<Cognito AccessToken issued at login>"
    }

Returns:
    - 200 with a success message if the user was logged out successfully
    - 400 if the access_token field is missing from the event
    - 401 if the access token is invalid or has already expired
    - 500 for any internal AWS service or unexpected errors
"""

import json
import boto3
from botocore.exceptions import ClientError


def lambda_handler(event, context):
    """
    AWS Lambda entry point for user logout.

    Accepts an active Cognito AccessToken and calls Cognito's GlobalSignOut API
    to invalidate all refresh tokens and access tokens for the user across all
    devices and sessions. This is the recommended approach for a secure logout.

    Args:
        event   (dict): Lambda event payload containing 'access_token'.
        context (obj):  Lambda context object (runtime metadata, unused here).

    Returns:
        dict: HTTP-style response with 'statusCode' and 'body'.
              200 on successful logout.
              400 if the access token is absent from the request.
              401 if the token is invalid/expired (Cognito NotAuthorizedException).
              500 for any other AWS or unexpected runtime error.
    """
    # Initialize the Cognito client
    client = boto3.client('cognito-idp')

    # Extract the access token from the event; use .get() to avoid KeyError
    access_token = event.get('access_token')

    # Validate that the caller has provided an access token before making the API call
    if not access_token:
        return {
            'statusCode': 400,
            'body': 'Access token is required for logout.'
        }

    try:
        # Perform a global sign-out — this invalidates ALL tokens for this user,
        # including refresh tokens, effectively ending all active sessions on all devices.
        response = client.global_sign_out(
            AccessToken=access_token
        )

        return {
            'statusCode': 200,
            'body': 'User logged out successfully.'
        }

    except client.exceptions.NotAuthorizedException:
        # Raised by Cognito when the supplied access token is invalid, expired,
        # or has already been revoked
        return {
            'statusCode': 401,
            'body': 'Invalid or expired access token.'
        }
    except ClientError as e:
        # Handles known AWS service errors (e.g., throttling, missing permissions)
        # by surfacing the AWS error message to the caller
        return {
            'statusCode': 500,
            'body': f"An error occurred: {e.response['Error']['Message']}"
        }
    except Exception as e:
        # Catch-all for any unexpected runtime errors not covered by the above handlers
        return {
            'statusCode': 500,
            'body': f"Internal server error: {str(e)}"
        }
