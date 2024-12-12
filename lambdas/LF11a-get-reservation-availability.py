import boto3
import json
from datetime import datetime, timedelta
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize DynamoDB client
dynamodb = boto3.client('dynamodb')

# Table names (update these to match your setup)
RESTAURANT_TABLE = 'Restaurant'
RESERVATION_TABLE = 'Reservation'

days_of_week = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6
}


def lambda_handler(event, context):
    try:
        # Parse input from event
        restaurant_id = event['queryStringParameters']['restaurant_id']
        date_str = event['queryStringParameters']['date']  # Format: YYYY-MM-DD
        party_size = int(event['queryStringParameters'].get('party_size', 1))

        # Parse the date
        date = datetime.strptime(date_str, "%Y-%m-%d")
        today = datetime.now().date()

        # Check if the requested date is in the past
        if date.date() < today:
            return {
                'statusCode': 200,
                'body': json.dumps({'available_times': []})  # Closed on that day
            }

        day_of_week = date.strftime("%A")  # Get day name (e.g., Monday)

        # Get restaurant hours for the given day
        hours_capacity = get_restaurant_hours_and_capacity(restaurant_id, day_of_week)
        if not hours_capacity:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'available_times': [],
                    'message': "hours not found"
                    })
            }
        elif hours_capacity.get('message'):
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'available_times': [],
                    'message': hours_capacity['message']
                    })
            }

        opening_hour = datetime.strptime(hours_capacity['opening_hour'], "%H:%M")
        closing_hour = datetime.strptime(hours_capacity['closing_hour'], "%H:%M")
        capacity = int(hours_capacity['capacity'])

        # Adjust opening and closing hours to the selected date
        opening_hour = datetime.combine(date, opening_hour.time())
        closing_hour = datetime.combine(date, closing_hour.time())

        # Filter out past times if the requested date is today
        now = datetime.now() - timedelta(hours=5)
        if date.date() == today:
            opening_hour = max(opening_hour, now)
        opening_hour = round_up_to_next_15_minutes(opening_hour)

        # Get existing reservations for the given restaurant and date
        reservations = get_reservations(restaurant_id, date_str)

        # Calculate availability
        available_times = calculate_availability(opening_hour, closing_hour, reservations, party_size, capacity)

        # Return available times
        return {
            'statusCode': 200,
            'body': json.dumps({
                'available_times': available_times,
                'opening_hour':opening_hour.strftime("%H:%M"),
                'closing_hour':closing_hour.strftime("%H:%M")
                })
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def get_restaurant_hours_and_capacity(restaurant_id, day_of_week):
    """Fetch the restaurant's hours and capacity for a specific day."""
    response = dynamodb.query(
        TableName=RESTAURANT_TABLE,
        KeyConditionExpression='restaurant_id = :r_id',
        ExpressionAttributeValues={
            ':r_id': {'S': restaurant_id}
        }
    )
    if response['Items']:
        # Extract hours and capacity
        hours = response['Items'][0]['hours']['L']  # 'hours' is a list of maps (L)
        capacity = int(response['Items'][0]['capacity']['N'])

        # Find the hours for the specified day_of_week
        for day_info in hours:
            if day_info['M']['day']['S'] == day_of_week:
                # Check if the restaurant is open on this day
                if not day_info['M']['open']['BOOL']:
                    logger.info('restaurant closed')
                    return {'message' : "Restaurant is closed."}  # Restaurant is closed on this day

                return {
                    'capacity': capacity,
                    'opening_hour': day_info['M']['opening_hour']['S'],
                    'closing_hour': day_info['M']['closing_hour']['S']
                }

    return None  # Restaurant or hours not found

def get_reservations(restaurant_id, res_date):
    """Fetch reservations for the given restaurant and date."""
    response = dynamodb.query(
        TableName=RESERVATION_TABLE,
        IndexName="restaurant_id-res_date-index",  # GSI Name
        KeyConditionExpression='restaurant_id = :r_id AND res_date = :r_date',
        ExpressionAttributeValues={
            ':r_id': {'S': restaurant_id},
            ':r_date': {'S': res_date}
        }
    )
    return [
        {
            'time': item['time']['S'],
            'party_size': int(item['party_size']['N'])
        }
        for item in response['Items']
    ]


def calculate_availability(opening_time, closing_time, reservations, party_size, capacity):
    """Calculate available times based on restaurant hours and existing reservations."""
    available_times = []
    current_time = opening_time

    while current_time <= closing_time:
        time_str = current_time.strftime("%H:%M")
        if is_time_available(current_time, reservations, party_size, capacity):
            available_times.append(['A', current_time.strftime("%I:%M %p")]) # Return in 12-hour format with AM/PM
        else:
            available_times.append(['U', current_time.strftime("%I:%M %p")]) 
        current_time += timedelta(minutes=15)

    return available_times


def is_time_available(current_time, reservations, party_size, capacity):
    """Check if a time slot is available based on overlapping reservations."""
    overlapping_reservations = [
        res for res in reservations
        if abs(
            datetime.strptime(res['time'], "%H:%M") - current_time
        ) < timedelta(hours=1)  # Overlap within an hour
    ]

    total_reserved = sum(res['party_size'] for res in overlapping_reservations)
    return (total_reserved + party_size) <= capacity

def round_up_to_next_15_minutes(date):
    """Round the given datetime object to the next greater 15-minute interval."""
    minute = date.minute
    if minute == 0:
        return date
    elif minute <= 15:
        remainder = 15 - minute
    elif minute <= 30:
        remainder = 30 - minute
    elif minute <= 45:
        remainder = 45 - minute
    else:
        remainder = 60 - minute
    return date + timedelta(minutes=remainder, seconds=-date.second, microseconds=-date.microsecond)
