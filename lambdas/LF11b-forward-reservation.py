import boto3
import json
import os

# Initialize SQS client
sqs = boto3.client('sqs')

# SQS queue URL
QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/699475942485/Q2-reservation'

def lambda_handler(event, context):
    try:
        # Validate user authentication (Cognito JWT token)
        user_id = event['requestContext']['authorizer']['claims']['sub']
        if not user_id:
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Unauthorized, please login or create an account'})
            }

        # Parse input
        body = json.loads(event['body'])
        required_fields = ['restaurant_id', 'res_date', 'time', 'party_size']

        # Ensure all required fields are provided
        for field in required_fields:
            if field not in body:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': f'{field} is required'})
                }

        # Forward the request to the SQS queue
        sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps({
                'user_id': user_id,
                'restaurant_id': body['restaurant_id'],
                'res_date': body['res_date'],
                'time': body['time'],
                'party_size': int(body['party_size']),
            })
        )

        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Reservation request submitted'})
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
