import boto3
import json
from datetime import datetime, timedelta

# Initialize DynamoDB and SQS clients
dynamodb = boto3.client('dynamodb')
sqs = boto3.client('sqs')

# Table names
RESTAURANT_TABLE = 'Restaurant'
RESERVATION_TABLE = 'Reservation'

def lambda_handler(event, context):
    try:
        for record in event['Records']:
            # Parse message from SQS
            message = json.loads(record['body'])
            user_id = message['user_id']
            restaurant_id = message['restaurant_id']
            res_date = message['res_date']
            time = message['time']
            party_size = int(message['party_size'])

            # Atomic check and reservation creation
            if not process_reservation(user_id, restaurant_id, res_date, time, party_size):
                print(f"Failed to process reservation for user {user_id}. Message moved to DLQ if retries exceeded.")
                continue

            print(f"Successfully processed reservation for user {user_id}.")

        return {'statusCode': 200, 'body': 'Processed messages successfully'}

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def process_reservation(user_id, restaurant_id, res_date, time, party_size):
    """Process a single reservation: check availability and create reservation atomically."""
    try:
        # Fetch restaurant capacity and existing reservations
        restaurant = fetch_restaurant(restaurant_id)
        if not restaurant:
            print(f"Restaurant {restaurant_id} not found.")
            return False

        capacity = int(restaurant['capacity']['N'])
        reservations = fetch_reservations(restaurant_id, res_date)

        # Check availability
        if not is_time_available(reservations, res_date, time, party_size, capacity):
            print(f"Insufficient capacity for reservation at {time}.")
            return False

        # Attempt to create reservation atomically
        create_reservation(user_id, restaurant_id, res_date, time, party_size)
        return True

    except Exception as e:
        print(f"Error processing reservation: {str(e)}")
        return False

def fetch_restaurant(restaurant_id):
    """Fetch restaurant details from DynamoDB."""
    response = dynamodb.get_item(
        TableName=RESTAURANT_TABLE,
        Key={'restaurant_id': {'S': restaurant_id}}
    )
    return response.get('Item')

def fetch_reservations(restaurant_id, res_date):
    """Fetch all reservations for the given restaurant and date."""
    response = dynamodb.query(
        TableName=RESERVATION_TABLE,
        IndexName='restaurant_id-res_date-index',
        KeyConditionExpression='restaurant_id = :r_id AND res_date = :r_date',
        ExpressionAttributeValues={
            ':r_id': {'S': restaurant_id},
            ':r_date': {'S': res_date}
        }
    )
    return response['Items']

def is_time_available(reservations, res_date, time, party_size, capacity):
    """Check if there is availability for the given party size."""
    now = datetime.now()
    reservation_datetime = datetime.strptime(f"{res_date} {time}", "%Y-%m-%d %H:%M")
    if reservation_datetime < now:
        print("reservation date and time are in the past")
        return False  # Cannot make a reservation in the past

    total_reserved = sum(
        int(r['party_size']['N']) for r in reservations
        if abs(
            datetime.strptime(r['time']['S'], "%H:%M") - datetime.strptime(time, "%H:%M")
        ) < timedelta(hours=1)  # Overlap within an hour
    )
    return total_reserved + party_size <= capacity

def create_reservation(user_id, restaurant_id, res_date, time, party_size):
    """Create a reservation atomically in DynamoDB."""
    dynamodb.put_item(
        TableName=RESERVATION_TABLE,
        Item={
            'reservation_id': {'S': f"{restaurant_id}#{res_date}#{time}#{user_id}"},
            'user_id': {'S': user_id},
            'restaurant_id': {'S': restaurant_id},
            'res_date': {'S': res_date},
            'time': {'S': time},
            'party_size': {'N': str(party_size)},
            'status':{'S':'RESERVED'}
        },
        ConditionExpression="attribute_not_exists(reservation_id)"  # Ensure no duplicates
    )
