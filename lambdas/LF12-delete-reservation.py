import boto3
import json

# Initialize DynamoDB client
dynamodb = boto3.client('dynamodb')

# Table name
RESERVATION_TABLE = 'Reservation'

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
        if 'reservation_id' not in body:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'reservation_id is required'})
            }

        reservation_id = body['reservation_id']

        # Fetch the reservation to validate ownership
        existing_reservation = dynamodb.get_item(
            TableName=RESERVATION_TABLE,
            Key={'reservation_id': {'S': reservation_id}}
        )

        if 'Item' not in existing_reservation:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Reservation not found'})
            }

        # Ensure the user owns the reservation
        if existing_reservation['Item']['user_id']['S'] != user_id:
            return {
                'statusCode': 403,
                'body': json.dumps({'error': 'You are not authorized to delete this reservation'})
            }

        # Delete the reservation
        dynamodb.delete_item(
            TableName=RESERVATION_TABLE,
            Key={'reservation_id': {'S': reservation_id}}
        )

        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Reservation deleted successfully'})
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

