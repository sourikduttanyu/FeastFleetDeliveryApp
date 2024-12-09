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

        # Get reservation_id from query string parameters
        reservation_id = event['queryStringParameters'].get('reservation_id')
        if not reservation_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'reservation_id is required'})
            }

        # Fetch the reservation
        reservation = get_reservation(reservation_id)
        if not reservation:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Reservation not found'})
            }

        # Ensure the user requesting it is the creator of the reservation
        if reservation['user_id']['S'] != user_id:
            return {
                'statusCode': 403,
                'body': json.dumps({'error': 'Access forbidden'})
            }

        # Format and return the reservation
        return {
            'statusCode': 200,
            'body': json.dumps(format_reservation(reservation))
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def get_reservation(reservation_id):
    """Fetch a reservation by its reservation_id."""
    response = dynamodb.get_item(
        TableName=RESERVATION_TABLE,
        Key={'reservation_id': {'S': reservation_id}}
    )
    return response.get('Item')

def format_reservation(reservation):
    """Format the reservation into a readable format."""
    return {
        'reservation_id': reservation['reservation_id']['S'],
        'user_id': reservation['user_id']['S'],
        'restaurant_id': reservation['restaurant_id']['S'],
        'res_date': reservation['res_date']['S'],
        'time': reservation['time']['S'],
        'party_size': int(reservation['party_size']['N'])
    }
