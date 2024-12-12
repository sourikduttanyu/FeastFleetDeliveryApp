import boto3
import json
import os
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize SQS client
sqs = boto3.client('sqs')

# SQS queue URL
QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/699475942485/Q2-reservation'

def lambda_handler(event, context):
    logger.info(f"Event: {json.dumps(event)}")

    try:
        # Validate user authentication (Cognito JWT token)
        user_id = event['requestContext']['authorizer']['claims']['sub']
        if not user_id:
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Unauthorized, please login or create an account'})
            }

        if isinstance(event['body'], str):
            body = json.loads(event['body'])
        else:
            body = event['body']  

       # Validate required fields
        required_fields = ['restaurant_id', 'res_date', 'time', 'party_size']
        missing_fields = [field for field in required_fields if field not in body]
        if missing_fields:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': f'Missing fields: {", ".join(missing_fields)}'})
            }

         # Extract input fields
        restaurant_id = body['restaurant_id']
        res_date = body['res_date']
        time = body['time']
        party_size = int(body['party_size'])
        

        # Forward the request to the SQS queue
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

        logger.info(f"SQS Send Response: {response}")

        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Reservation request submitted'})
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
