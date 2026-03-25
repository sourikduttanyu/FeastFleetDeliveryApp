"""
LF11a - Get Reservation Availability Lambda
--------------------------------------------
Purpose:
    Returns a list of all 15-minute time slots for a given restaurant, date, and
    party size, marking each slot as either Available ('A') or Unavailable ('U').
    This powers the reservation time-picker on the frontend.

    The availability calculation accounts for:
      - The restaurant's opening and closing hours for the requested day of week.
      - Whether the restaurant is closed on that day entirely.
      - Whether the requested date is in the past (returns empty list).
      - The current time (if the date is today, past slots are excluded).
      - Existing reservations within a 1-hour overlap window around each slot,
        comparing aggregated party sizes against the restaurant's seating capacity.

AWS Integrations:
    - API Gateway: Triggers this Lambda via a GET request with query string parameters.
    - DynamoDB (Restaurant):   Queried by restaurant_id to retrieve operating hours
                               (a list-of-maps attribute) and total seating capacity.
    - DynamoDB (Reservation):  Queried via a GSI ('restaurant_id-res_date-index') to
                               efficiently retrieve all reservations for a specific
                               restaurant on a specific date without a table scan.

Event Structure (API Gateway Query Parameters):
    {
        "queryStringParameters": {
            "restaurant_id": "<restaurant-uuid>",
            "date": "YYYY-MM-DD",
            "party_size": "4"    # Optional, defaults to 1
        }
    }

Returns:
    HTTP 200 with a JSON body containing:
        - 'available_times': list of ['A'|'U', 'HH:MM AM/PM'] tuples for each
          15-minute slot between opening and closing hours.
        - 'opening_hour': adjusted opening time (HH:MM, 24-hour).
        - 'closing_hour': closing time (HH:MM, 24-hour).
        - 'message': explanatory string if the restaurant is closed or hours
          are not found.
    HTTP 500 on any unexpected server error.
"""

import boto3
import json
from datetime import datetime, timedelta
import logging

# Set up CloudWatch logging for operational visibility
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# DynamoDB low-level client — used here (vs. resource) because the data is accessed
# using the raw DynamoDB type-annotated format (e.g., {'S': '...'}, {'N': '...'})
dynamodb = boto3.client('dynamodb')

# Table names (update these to match your setup)
RESTAURANT_TABLE = 'Restaurant'
RESERVATION_TABLE = 'Reservation'

# Mapping of day name to weekday index — kept for reference but not directly used
# in the current implementation (strftime is used to get the day name directly)
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
    """
    Main entry point for the Get Reservation Availability Lambda.

    Orchestrates the availability check by:
      1. Parsing and validating query parameters.
      2. Returning an empty list immediately if the date is in the past.
      3. Fetching restaurant hours and capacity.
      4. Fetching existing reservations for the given restaurant and date.
      5. Computing and returning the availability grid in 15-minute increments.

    Args:
        event (dict): API Gateway proxy event with 'queryStringParameters' containing
                      'restaurant_id', 'date', and optionally 'party_size'.
        context (LambdaContext): AWS Lambda context object (unused here).

    Returns:
        dict: API Gateway-compatible response with statusCode and JSON body.
    """
    try:
        # Parse input from event
        restaurant_id = event['queryStringParameters']['restaurant_id']
        date_str = event['queryStringParameters']['date']  # Format: YYYY-MM-DD
        party_size = int(event['queryStringParameters'].get('party_size', 1))

        # Parse the date string into a datetime object for comparison and manipulation
        date = datetime.strptime(date_str, "%Y-%m-%d")
        today = datetime.now().date()

        # If the requested date is before today, no slots can be available —
        # return an empty list immediately without querying DynamoDB
        if date.date() < today:
            return {
                'statusCode': 200,
                'body': json.dumps({'available_times': []})  # Closed on that day
            }

        # Get the day name (e.g., "Monday") to look up the correct hours entry
        day_of_week = date.strftime("%A")  # Get day name (e.g., Monday)

        # Fetch the restaurant's hours for the given day and its seating capacity
        hours_capacity = get_restaurant_hours_and_capacity(restaurant_id, day_of_week)
        if not hours_capacity:
            # Restaurant or hours record not found at all
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'available_times': [],
                    'message': "hours not found"
                    })
            }
        elif hours_capacity.get('message'):
            # Restaurant was found but is marked as closed on this day
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'available_times': [],
                    'message': hours_capacity['message']
                    })
            }

        # Parse the opening and closing time strings into datetime objects
        opening_hour = datetime.strptime(hours_capacity['opening_hour'], "%H:%M")
        closing_hour = datetime.strptime(hours_capacity['closing_hour'], "%H:%M")
        capacity = int(hours_capacity['capacity'])

        # Adjust opening and closing hours to the selected date so they can be
        # compared directly against datetime.now() (which includes a date component)
        opening_hour = datetime.combine(date, opening_hour.time())
        closing_hour = datetime.combine(date, closing_hour.time())

        # Adjust for UTC offset: the Lambda runs in UTC but the restaurant times
        # are in Eastern Time (UTC-5). Subtract 5 hours from UTC now to approximate
        # the current Eastern Time without relying on pytz/zoneinfo.
        now = datetime.now() - timedelta(hours=5)
        if date.date() == today:
            # If today, the opening slot should not be earlier than right now
            opening_hour = max(opening_hour, now)

        # Round the opening hour up to the nearest 15-minute boundary so the first
        # available slot is always a clean quarter-hour (e.g., 12:00, 12:15, 12:30)
        opening_hour = round_up_to_next_15_minutes(opening_hour)

        # Fetch all existing reservations for this restaurant on the requested date
        # using the GSI to avoid a full table scan
        reservations = get_reservations(restaurant_id, date_str)

        # Compute which 15-minute slots are available given current reservations
        available_times = calculate_availability(opening_hour, closing_hour, reservations, party_size, capacity)

        # Return available times along with the (possibly adjusted) window
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
    """
    Fetches the restaurant's operating hours and seating capacity for a given day.

    The Restaurant table uses a list-of-maps ('L' type) for the 'hours' attribute,
    where each map ('M') contains 'day', 'open' (bool), 'opening_hour', and
    'closing_hour' fields stored in DynamoDB's low-level typed format.

    Args:
        restaurant_id (str): The restaurant's partition key.
        day_of_week (str):   Day name string matching the 'day' field in the hours
                             list (e.g., "Monday", "Tuesday").

    Returns:
        dict with keys 'capacity', 'opening_hour', 'closing_hour' if the restaurant
        is open on that day.
        dict with key 'message' set to "Restaurant is closed." if closed that day.
        None if the restaurant does not exist or has no hours data.
    """
    response = dynamodb.query(
        TableName=RESTAURANT_TABLE,
        KeyConditionExpression='restaurant_id = :r_id',
        ExpressionAttributeValues={
            ':r_id': {'S': restaurant_id}
        }
    )
    if response['Items']:
        # Extract hours and capacity from the first (and expected only) matching item.
        # 'hours' is stored as a DynamoDB List ('L') of Maps ('M'), one entry per day.
        hours = response['Items'][0]['hours']['L']  # 'hours' is a list of maps (L)
        capacity = int(response['Items'][0]['capacity']['N'])

        # Iterate over each day entry in the hours list to find the matching day
        for day_info in hours:
            if day_info['M']['day']['S'] == day_of_week:
                # Check if the restaurant is open on this day
                if not day_info['M']['open']['BOOL']:
                    logger.info('restaurant closed')
                    return {'message' : "Restaurant is closed."}  # Restaurant is closed on this day

                # Return hours in HH:MM string format along with integer capacity
                return {
                    'capacity': capacity,
                    'opening_hour': day_info['M']['opening_hour']['S'],
                    'closing_hour': day_info['M']['closing_hour']['S']
                }

    return None  # Restaurant or hours not found


def get_reservations(restaurant_id, res_date):
    """
    Retrieves all reservations for a restaurant on a specific date using a GSI.

    The Reservation table has a Global Secondary Index (GSI) named
    'restaurant_id-res_date-index' with 'restaurant_id' as the partition key
    and 'res_date' as the sort key. This allows efficient date-scoped queries
    per restaurant without scanning the entire Reservation table.

    Args:
        restaurant_id (str): The restaurant's ID (GSI partition key).
        res_date (str):      The reservation date in 'YYYY-MM-DD' format (GSI sort key).

    Returns:
        list of dicts, each with 'time' (HH:MM string) and 'party_size' (int),
        representing all confirmed reservations for that restaurant and date.
    """
    response = dynamodb.query(
        TableName=RESERVATION_TABLE,
        IndexName="restaurant_id-res_date-index",  # GSI Name
        KeyConditionExpression='restaurant_id = :r_id AND res_date = :r_date',
        ExpressionAttributeValues={
            ':r_id': {'S': restaurant_id},
            ':r_date': {'S': res_date}
        }
    )
    # Flatten the DynamoDB typed format to plain Python dicts for easier processing
    return [
        {
            'time': item['time']['S'],
            'party_size': int(item['party_size']['N'])
        }
        for item in response['Items']
    ]


def calculate_availability(opening_time, closing_time, reservations, party_size, capacity):
    """
    Builds the full availability grid between opening and closing time in 15-minute steps.

    Each slot is checked against existing reservations and labelled 'A' (Available)
    or 'U' (Unavailable). The frontend receives the full grid so it can render
    both open and blocked slots to the user.

    Args:
        opening_time (datetime): The (adjusted) start of the availability window.
        closing_time (datetime): The end of the availability window.
        reservations (list):     List of existing reservation dicts (time, party_size).
        party_size (int):        The party size the user wants to book.
        capacity (int):          Total seating capacity of the restaurant.

    Returns:
        list of ['A'|'U', 'HH:MM AM/PM'] pairs for every 15-minute slot in the window.
    """
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
    """
    Determines whether a specific time slot has enough remaining capacity.

    An 'overlap window' of 1 hour is used: any reservation within 60 minutes
    of the candidate slot (before or after) is considered to compete for the
    same table capacity. This prevents double-booking of tables for back-to-back
    seatings that would physically overlap.

    Args:
        current_time (datetime): The candidate time slot being evaluated.
        reservations (list):     All reservations for the restaurant on this date.
        party_size (int):        The party size the user wants to book.
        capacity (int):          Total seating capacity of the restaurant.

    Returns:
        bool: True if adding party_size to the overlapping reserved count would
              not exceed the restaurant's total capacity; False otherwise.
    """
    # Find all reservations whose time falls within 1 hour of the candidate slot
    overlapping_reservations = [
        res for res in reservations
        if abs(
            datetime.strptime(res['time'], "%H:%M") - current_time
        ) < timedelta(hours=1)  # Overlap within an hour
    ]

    # Sum the party sizes of all overlapping reservations to get current occupancy
    total_reserved = sum(res['party_size'] for res in overlapping_reservations)

    # Slot is available only if the new party fits within the remaining capacity
    return (total_reserved + party_size) <= capacity


def round_up_to_next_15_minutes(date):
    """
    Rounds a datetime up to the next 15-minute boundary (ceiling, not nearest).

    Used to ensure the first available time slot is always a clean quarter-hour.
    For example: 12:03 -> 12:15, 12:16 -> 12:30, 12:47 -> 13:00.
    If the time is already on a 15-minute boundary (minute == 0), it is returned
    unchanged.

    Seconds and microseconds are zeroed out in the result to produce a clean time.

    Args:
        date (datetime): The datetime to round up.

    Returns:
        datetime: The input datetime rounded up to the next 15-minute interval,
                  with seconds and microseconds set to 0.
    """
    minute = date.minute
    if minute == 0:
        # Already on a 15-minute boundary — no adjustment needed
        return date
    elif minute <= 15:
        remainder = 15 - minute
    elif minute <= 30:
        remainder = 30 - minute
    elif minute <= 45:
        remainder = 45 - minute
    else:
        # Minute is between 46 and 59 — round up to the next full hour
        remainder = 60 - minute
    return date + timedelta(minutes=remainder, seconds=-date.second, microseconds=-date.microsecond)
