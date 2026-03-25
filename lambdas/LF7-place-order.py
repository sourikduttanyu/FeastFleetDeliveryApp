"""
LF7 - Place Order Lambda
------------------------
Purpose:
    Handles new food order submissions from authenticated users via the FeastFleet API.
    This is the entry point for the order workflow — it validates the incoming request,
    persists the order to DynamoDB, and enqueues an 'OrderPlaced' event to an SQS queue
    so that downstream processing (LF8) can react to the new order asynchronously.

AWS Integrations:
    - API Gateway: Triggers this Lambda via a POST request (authenticated via Cognito Authorizer)
    - DynamoDB:    Writes the new order record to the 'Order' table
    - SQS:         Publishes an OrderPlaced message to Q1 for downstream consumers (e.g., LF8)
    - Cognito:     The caller's identity (user_id) is extracted from the JWT claims injected
                   by API Gateway's Cognito Authorizer

Event Structure (API Gateway Proxy Integration):
    {
        "body": '{"restaurant_id": "...", "items": [...], "total_price": 29.99}',
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "<cognito-user-uuid>"
                }
            }
        }
    }

Returns:
    HTTP 200 with order_id on success.
    HTTP 400 if required fields are missing.
    HTTP 500 on any unexpected server error.
"""

import json
import boto3
import uuid
from datetime import datetime
from decimal import Decimal

# DynamoDB resource — uses the default region configured for the Lambda execution role
dynamodb = boto3.resource('dynamodb')

# Reference to the 'Order' table where all order records are stored
order_table = dynamodb.Table('Order')

# SQS client used to publish order events to the downstream processing queue (Q1)
sqs = boto3.client('sqs')

# The URL of the SQS queue (Q1) that LF8 consumes to process order status changes.
# This is intentionally left blank here and should be populated with the actual queue URL.
queue_url = ''


def lambda_handler(event, context):
    """
    Main entry point for the Place Order Lambda.

    Validates the incoming request, creates a new order record in DynamoDB with an
    initial status of 'PLACED', and publishes an 'OrderPlaced' event to the SQS queue
    so that LF8 can process the order asynchronously.

    Args:
        event (dict): API Gateway proxy event containing the request body and
                      Cognito authorizer claims.
        context (LambdaContext): AWS Lambda context object (unused here).

    Returns:
        dict: API Gateway-compatible HTTP response with statusCode and JSON body.
    """
    try:
        # Parse request body — API Gateway sends it as a JSON string
        body = json.loads(event['body'])

        # Validate required fields — both restaurant_id and items must be present
        if 'restaurant_id' not in body or 'items' not in body:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'restaurant_id and items are required fields.'})
            }

        # Generate a unique order_id using UUID v4 to avoid collisions
        order_id = str(uuid.uuid4())

        # Extract the authenticated user's ID from Cognito JWT claims.
        # API Gateway injects 'sub' (subject) from the Cognito token into requestContext.
        user_id = event['requestContext']['authorizer']['claims']['sub']  # Cognito user ID (subject)

        # Extract other fields from the request body
        restaurant_id = body['restaurant_id']
        items = body['items']

        # Use Decimal for total_price to comply with DynamoDB's requirement that float
        # values be stored as Decimal, not Python float (which DynamoDB rejects)
        total_price = Decimal(str(body.get('total_price', 0)))

        # ISO 8601 UTC timestamp marks when the order was placed
        timestamp = datetime.utcnow().isoformat()

        # All new orders start in the 'PLACED' status; downstream services update this
        status = 'PLACED'  # Initial order status

        # Build the full order document to be written to DynamoDB
        order_item = {
            'order_id': order_id,
            'user_id': user_id,
            'restaurant_id': restaurant_id,
            'items': items,  # Should be a list of {item_id, quantity}
            'total_price': total_price,
            'timestamp': timestamp,
            'status': status
        }

        # Persist the order to DynamoDB; this is a simple put (upsert semantics)
        order_table.put_item(Item=order_item)

        # Build the SQS message payload — only the fields needed by LF8 for processing
        # are included; full item details are retrieved from DynamoDB by the consumer.
        sqs_message = {
            'order_id': order_id,
            'user_id': user_id,
            'restaurant_id': restaurant_id,
            'status': status,
            'timestamp': timestamp
        }

        # Send the message to Q1 with a custom MessageAttribute 'EventType' set to
        # 'OrderPlaced'. This allows SQS consumers or message filters to route messages
        # based on the event type without parsing the full message body.
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(sqs_message),
            MessageAttributes={
                'EventType': {
                    'StringValue': 'OrderPlaced',
                    'DataType': 'String'
                }
            }
        )

        # Return success response with the newly created order_id for client reference
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Order placed successfully.',
                'order_id': order_id
            })
        }

    except Exception as e:
        # Log the error for CloudWatch visibility and return a generic 500 response
        # to avoid leaking internal details to the client
        print(f"Error placing order: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Internal server error.'})
        }
