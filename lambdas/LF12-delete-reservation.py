"""
LF12 - Delete Reservation Lambda
=================================
AWS Service: Amazon DynamoDB, Amazon API Gateway (via Cognito Authorizer)

Purpose:
    Allows an authenticated user to delete one of their existing reservations.
    Enforces ownership by verifying that the reservation's user_id matches the
    authenticated caller's Cognito sub before performing the delete.

Event Structure (API Gateway Proxy Integration):
    {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "<cognito-user-uuid>"   # Injected by Cognito JWT authorizer
                }
            }
        },
        "body": "{\"reservation_id\": \"<uuid>\"}"  # JSON string or dict
    }

Returns:
    HTTP 200 with a success message if the reservation was deleted.
    HTTP 400 if reservation_id is missing from the request body.
    HTTP 401 if no authenticated user is found in the request context.
    HTTP 403 if the authenticated user does not own the reservation.
    HTTP 404 if the reservation does not exist in DynamoDB.
    HTTP 500 for unexpected server-side errors.
"""

import boto3
import json

# Initialize DynamoDB client using the low-level boto3 client API.
# The low-level client uses DynamoDB's native type descriptors (e.g., {'S': 'value'}).
dynamodb = boto3.client('dynamodb')

# Name of the DynamoDB table that stores reservation records.
RESERVATION_TABLE = 'Reservation'

def lambda_handler(event, context):
    """
    Main entry point for the Lambda function.

    Validates the caller's identity via the Cognito authorizer, parses the
    request body to extract reservation_id, confirms ownership of the
    reservation, and performs a hard delete from DynamoDB.

    Args:
        event (dict): The API Gateway proxy event containing request context,
                      headers, and body.
        context (LambdaContext): Runtime information provided by AWS Lambda
                                 (unused in this function).

    Returns:
        dict: An API Gateway-compatible HTTP response with a statusCode and
              JSON-encoded body.
    """
    try:
        print('EVENT ', event)

        # --- Authentication Check ---
        # The Cognito JWT authorizer attaches decoded token claims to the
        # request context. The 'sub' claim is the unique Cognito user ID.
        user_id = event['requestContext']['authorizer']['claims']['sub']
        print('USER_ID ', user_id)
        if not user_id:
            # Guard against an edge case where 'sub' key exists but is empty.
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Unauthorized, please login or create an account'})
            }

        # --- Request Body Parsing ---
        body = event['body']
        if isinstance(body, str):
            # API Gateway passes the body as a raw JSON string when the
            # Content-Type is application/json; deserialize it here.
            body = json.loads(body)
        print('BODY: ', body)

        # Validate that the required field is present in the request.
        if 'reservation_id' not in body:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'reservation_id is required'})
            }

        reservation_id = body['reservation_id']

        # --- Ownership Verification ---
        # Fetch the reservation first so we can confirm the caller owns it
        # before allowing the delete. DynamoDB's partition key is reservation_id.
        existing_reservation = dynamodb.get_item(
            TableName=RESERVATION_TABLE,
            Key={'reservation_id': {'S': reservation_id}}
        )

        # If 'Item' is absent in the response, the record does not exist.
        if 'Item' not in existing_reservation:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Reservation not found'})
            }

        # Compare the reservation's stored user_id against the authenticated caller.
        # This prevents one user from deleting another user's reservation.
        if existing_reservation['Item']['user_id']['S'] != user_id:
            return {
                'statusCode': 403,
                'body': json.dumps({'error': 'You are not authorized to delete this reservation'})
            }

        # --- Delete Operation ---
        # Perform a hard delete using the partition key. DynamoDB delete_item
        # is idempotent and succeeds even if the item no longer exists,
        # but ownership has already been verified above.
        dynamodb.delete_item(
            TableName=RESERVATION_TABLE,
            Key={'reservation_id': {'S': reservation_id}}
        )

        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Reservation deleted successfully'})
        }

    except Exception as e:
        # Catch-all for unexpected errors (e.g., DynamoDB connectivity issues,
        # missing keys in the event structure). Return a generic 500 response.
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
