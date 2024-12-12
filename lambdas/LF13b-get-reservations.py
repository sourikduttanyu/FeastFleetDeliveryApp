import boto3
import json
from datetime import datetime

# Initialize DynamoDB client
dynamodb = boto3.client('dynamodb')

# Table name
RESERVATION_TABLE = 'Reservation'
RESTAURANT_TABLE = 'Restaurant'

def lambda_handler(event, context):
    try:
        print('EVENT ',event)
        # Validate user authentication (Cognito JWT token)
        user_id = event['requestContext']['authorizer']['claims']['sub']
        if not user_id:
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Unauthorized, please login or create an account'})
            }

        # Fetch user's reservations
        reservations = fetch_user_reservations(user_id)

        # Sort and categorize reservations
        past_reservations, upcoming_reservations = categorize_reservations(reservations)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'past_reservations': past_reservations,
                'upcoming_reservations': upcoming_reservations
            })
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def fetch_user_reservations(user_id):
    """Fetch all reservations for the given user."""
    response = dynamodb.query(
        TableName=RESERVATION_TABLE,
        IndexName='user_id-index',  # Ensure you have a GSI on `user_id`
        KeyConditionExpression='user_id = :user_id',
        ExpressionAttributeValues={
            ':user_id': {'S': user_id}
        }
    )
    return [
        {
            'reservation_id': item['reservation_id']['S'],
            'restaurant_id': item['restaurant_id']['S'],
            'res_date': item['res_date']['S'],
            'time': item['time']['S'],
            'party_size': int(item['party_size']['N'])
        }
        for item in response['Items']
    ]


def categorize_reservations(reservations):
    """Categorize reservations into past and upcoming."""
    now = datetime.now()

    # Parse and sort reservations
    sorted_reservations = sorted(
        reservations,
        key=lambda r: datetime.strptime(f"{r['res_date']} {r['time']}", "%Y-%m-%d %H:%M")
    )

    past_reservations = []
    upcoming_reservations = []

    for reservation in sorted_reservations:
        restaurant = fetch_restaurant(reservation['restaurant_id'])
        reservation['restaurant_name'] = restaurant['name']['S']
        reservation['restaurant_address'] = restaurant['address']['S']

        reservation_datetime = datetime.strptime(
            f"{reservation['res_date']} {reservation['time']}", "%Y-%m-%d %H:%M"
        )
        if reservation_datetime < now:
            past_reservations.append(reservation)
        else:
            upcoming_reservations.append(reservation)

    return past_reservations, upcoming_reservations



def fetch_restaurant(restaurant_id):
    """Fetch restaurant details from DynamoDB."""
    response = dynamodb.get_item(
        TableName=RESTAURANT_TABLE,
        Key={'restaurant_id': {'S': restaurant_id}}
    )
    return response.get('Item')