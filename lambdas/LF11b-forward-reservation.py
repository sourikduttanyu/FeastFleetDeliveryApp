"""
LF11b - Forward Reservation Lambda
-------------------------------------
Purpose:
    Acts as the authenticated intake point for reservation requests. It validates
    the caller's identity via Cognito, validates the request payload, and forwards
    the reservation request to an SQS queue (Q2) for asynchronous processing by
    LF11c (make-reservation).

    This Lambda deliberately does NOT write to DynamoDB directly. Instead, by
    decoupling intake from processing via SQS, the architecture ensures:
      - The API response is fast (just a queue enqueue).
      - Actual availability checks and writes happen asynchronously in LF11c.
      - The queue acts as a buffer, preventing thundering-herd write contention
        on the Reservation table during peak booking times.

AWS Integrations:
    - API Gateway: Triggers this Lambda via a POST request with a Cognito
                   Authorizer. The user's Cognito 'sub' is extracted from the
                   JWT claims injected by API Gateway.
    - SQS (Q2):   Reservation requests are enqueued to Q2-reservation for
                  downstream processing by LF11c.

Event Structure (API Gateway Proxy Integration):
    {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "<cognito-user-uuid>"
                }
            }
        },
        "body": '{"restaurant_id": "...", "res_date": "YYYY-MM-DD", "time": "HH:MM", "party_size": 4}'
    }

Returns:
    HTTP 200 with a confirmation message when the message is successfully enqueued.
    HTTP 400 if any required field is missing from the request body.
    HTTP 401 if the request is not authenticated (no valid Cognito sub).
    HTTP 500 on any unexpected server error.
"""

import boto3
import json
import os
import logging

# Set up CloudWatch logging for visibility into request handling
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# SQS client used to enqueue the reservation request to Q2
sqs = boto3.client('sqs')

# SQS queue URL for Q2-reservation — the queue that LF11c (make-reservation) consumes.
# This is hardcoded; in a production system consider using an environment variable.
QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/699475942485/Q2-reservation'


def lambda_handler(event, context):
    """
    Main entry point for the Forward Reservation Lambda.

    Validates authentication, parses and validates the request body, then enqueues
    the reservation request to SQS for asynchronous processing. Returns immediately
    with a 200 after the enqueue — the actual reservation outcome is communicated
    to the user via email by LF11c.

    Args:
        event (dict): API Gateway proxy event containing Cognito JWT claims in
                      requestContext and the reservation details in the body.
        context (LambdaContext): AWS Lambda context object (unused here).

    Returns:
        dict: API Gateway-compatible HTTP response with statusCode and JSON body.
    """
    logger.info(f"Event: {json.dumps(event)}")

    try:
        # Extract the authenticated user's ID from Cognito JWT claims.
        # API Gateway's Cognito Authorizer injects the decoded token claims into
        # requestContext.authorizer.claims — 'sub' is the stable unique user identifier.
        user_id = event['requestContext']['authorizer']['claims']['sub']
        if not user_id:
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Unauthorized, please login or create an account'})
            }

        # Parse the request body — handle both string (API Gateway proxy) and
        # dict (direct Lambda invocation or already-parsed payload) formats
        if isinstance(event['body'], str):
            body = json.loads(event['body'])
        else:
            body = event['body']

       # Validate required fields — all four are necessary to create a reservation
        required_fields = ['restaurant_id', 'res_date', 'time', 'party_size']
        missing_fields = [field for field in required_fields if field not in body]
        if missing_fields:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': f'Missing fields: {", ".join(missing_fields)}'})
            }

         # Extract input fields from the validated request body
        restaurant_id = body['restaurant_id']
        res_date = body['res_date']
        time = body['time']
        party_size = int(body['party_size'])  # Ensure party_size is stored as int, not string


        # Forward the request to the SQS queue (Q2) as a JSON-encoded message.
        # LF11c will consume this message, perform the availability check, write
        # to DynamoDB, and send a confirmation/failure email to the user.
        response = sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps({
                'user_id': user_id,
                'restaurant_id': restaurant_id,
                'res_date': res_date,
                'time': time,
                'party_size': party_size,
            })
        )

        # Log the SQS response (includes MessageId) for traceability in CloudWatch
        logger.info(f"SQS Send Response: {response}")

        # Return 200 immediately — the reservation is 'submitted', not yet confirmed.
        # The user will receive an email from LF11c once the request is processed.
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Reservation request submitted'})
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
