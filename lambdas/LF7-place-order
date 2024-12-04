import json
import boto3
import uuid
from datetime import datetime
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
order_table = dynamodb.Table('Order')

sqs = boto3.client('sqs')
queue_url = ''  

def lambda_handler(event, context):
    try:
        # Parse request body
        body = json.loads(event['body'])

        # Validate required fields
        if 'restaurant_id' not in body or 'items' not in body:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'restaurant_id and items are required fields.'})
            }

        # Generate a unique order_id
        order_id = str(uuid.uuid4())

        # Get user_id from Cognito
        user_id = event['requestContext']['authorizer']['claims']['sub']  # Cognito user ID (subject)

        # Extract other fields from the request body
        restaurant_id = body['restaurant_id']
        items = body['items']
        total_price = Decimal(str(body.get('total_price', 0)))
        timestamp = datetime.utcnow().isoformat()
        status = 'PLACED'  # Initial order status

        # Prepare order item for DynamoDB
        order_item = {
            'order_id': order_id,
            'user_id': user_id,
            'restaurant_id': restaurant_id,
            'items': items,  # Should be a list of {item_id, quantity}
            'total_price': total_price,
            'timestamp': timestamp,
            'status': status
        }

        order_table.put_item(Item=order_item)

        # Push order status to SQS (Q1)
        sqs_message = {
            'order_id': order_id,
            'user_id': user_id,
            'restaurant_id': restaurant_id,
            'status': status,
            'timestamp': timestamp
        }

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

        # Return success response
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Order placed successfully.',
                'order_id': order_id
            })
        }

    except Exception as e:
        print(f"Error placing order: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Internal server error.'})
        }
