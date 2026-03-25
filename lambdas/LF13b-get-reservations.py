"""
LF13b - Get All Reservations Lambda
=====================================
AWS Services: Amazon DynamoDB (with GSI), Amazon API Gateway (via Cognito Authorizer)

Purpose:
    Retrieves all reservations belonging to an authenticated user, enriches
    each one with restaurant metadata, and returns them split into two lists:
    past reservations and upcoming reservations, each sorted chronologically.

    Uses a DynamoDB Global Secondary Index (GSI) on the user_id attribute to
    efficiently query all reservations belonging to a specific user without
    performing a full table scan.

Event Structure (API Gateway Proxy Integration - GET request):
    {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "<cognito-user-uuid>"   # Injected by Cognito JWT authorizer
                }
            }
        }
    }

Returns:
    HTTP 200 with a body containing:
        {
            "past_reservations":     [ ...list of formatted reservation objects... ],
            "upcoming_reservations": [ ...list of formatted reservation objects... ]
        }
    HTTP 401 if the caller is not authenticated.
    HTTP 500 for unexpected server-side errors.
"""

import boto3
import json
from datetime import datetime

# Initialize the low-level DynamoDB client.
# The low-level client returns native DynamoDB type descriptors (e.g., {'S': '...'}).
dynamodb = boto3.client('dynamodb')

# DynamoDB table names referenced by this Lambda.
RESERVATION_TABLE = 'Reservation'
RESTAURANT_TABLE = 'Restaurant'

def lambda_handler(event, context):
    """
    Main entry point for the Lambda function.

    Validates the authenticated user, queries all their reservations via a
    DynamoDB GSI, enriches each record with restaurant details, and returns
    the reservations categorized as past or upcoming.

    Args:
        event (dict): API Gateway proxy event containing request context.
        context (LambdaContext): AWS Lambda runtime context (unused).

    Returns:
        dict: API Gateway-compatible HTTP response with a statusCode and a
              JSON-encoded body containing past and upcoming reservation lists.
    """
    try:
        print('EVENT ', event)

        # --- Authentication Check ---
        # The 'sub' claim is the unique Cognito user UUID, set by the
        # API Gateway Cognito authorizer after validating the bearer token.
        user_id = event['requestContext']['authorizer']['claims']['sub']
        if not user_id:
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Unauthorized, please login or create an account'})
            }

        # --- Data Retrieval ---
        # Fetch all reservations for this user using a DynamoDB GSI query.
        reservations = fetch_user_reservations(user_id)

        # --- Classification ---
        # Sort all reservations by datetime and split into past vs. upcoming.
        past_reservations, upcoming_reservations = categorize_reservations(reservations)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'past_reservations': past_reservations,
                'upcoming_reservations': upcoming_reservations
            })
        }

    except Exception as e:
        # Catch-all for unexpected failures such as DynamoDB errors or
        # missing keys in the event payload.
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def fetch_user_reservations(user_id):
    """
    Query DynamoDB for all reservations belonging to the given user.

    This function uses a Global Secondary Index (GSI) named 'user_id-index'
    on the Reservation table so that reservations can be efficiently looked
    up by user_id without scanning the entire table. The GSI must be
    pre-configured in DynamoDB with user_id as its partition key.

    Args:
        user_id (str): The Cognito UUID of the authenticated user.

    Returns:
        list[dict]: A list of simplified reservation dictionaries, each
                    containing reservation_id, restaurant_id, res_date,
                    time, and party_size (as int). Returns an empty list
                    if no reservations are found.
    """
    response = dynamodb.query(
        TableName=RESERVATION_TABLE,
        IndexName='user_id-index',  # Ensure you have a GSI on `user_id`
        # KeyConditionExpression restricts the query to items belonging
        # to this specific user; ':user_id' is the expression placeholder.
        KeyConditionExpression='user_id = :user_id',
        ExpressionAttributeValues={
            ':user_id': {'S': user_id}
        }
    )
    # Unwrap DynamoDB type descriptors and normalize the returned items
    # into plain Python dictionaries for downstream processing.
    return [
        {
            'reservation_id': item['reservation_id']['S'],
            'restaurant_id': item['restaurant_id']['S'],
            'res_date': item['res_date']['S'],          # Format: "YYYY-MM-DD"
            'time': item['time']['S'],                   # Format: "HH:MM"
            # DynamoDB stores numbers as strings under 'N'; cast to int here.
            'party_size': int(item['party_size']['N'])
        }
        for item in response['Items']
    ]


def categorize_reservations(reservations):
    """
    Sort all reservations by datetime and split them into past and upcoming.

    Each reservation is enriched with restaurant name and address by calling
    fetch_restaurant() per reservation. Reservations whose datetime is before
    the current time are classified as past; all others are upcoming.

    Args:
        reservations (list[dict]): List of reservation dicts as returned by
                                   fetch_user_reservations().

    Returns:
        tuple[list[dict], list[dict]]: A 2-tuple of (past_reservations,
                                       upcoming_reservations), each a list of
                                       enriched reservation dictionaries sorted
                                       in ascending chronological order.
    """
    now = datetime.now()

    # Combine res_date (YYYY-MM-DD) and time (HH:MM) into a datetime object
    # for accurate chronological sorting across all reservations.
    sorted_reservations = sorted(
        reservations,
        key=lambda r: datetime.strptime(f"{r['res_date']} {r['time']}", "%Y-%m-%d %H:%M")
    )

    past_reservations = []
    upcoming_reservations = []

    for reservation in sorted_reservations:
        # Fetch and embed restaurant details into each reservation dict.
        # This performs one DynamoDB GetItem call per reservation.
        restaurant = fetch_restaurant(reservation['restaurant_id'])
        reservation['restaurant_name'] = restaurant['name']['S']
        reservation['restaurant_address'] = restaurant['address']['S']

        # Parse the combined date+time string to compare against now.
        reservation_datetime = datetime.strptime(
            f"{reservation['res_date']} {reservation['time']}", "%Y-%m-%d %H:%M"
        )
        # Classify the reservation based on whether it's in the past or future.
        if reservation_datetime < now:
            past_reservations.append(reservation)
        else:
            upcoming_reservations.append(reservation)

    return past_reservations, upcoming_reservations



def fetch_restaurant(restaurant_id):
    """
    Fetch a single restaurant record from DynamoDB by its primary key.

    Used to enrich reservation records with human-readable restaurant
    name and address rather than exposing only the raw restaurant_id.

    Args:
        restaurant_id (str): The UUID primary key of the restaurant.

    Returns:
        dict or None: The raw DynamoDB item (with type descriptors) if found,
                      or None if the restaurant does not exist.
    """
    response = dynamodb.get_item(
        TableName=RESTAURANT_TABLE,
        Key={'restaurant_id': {'S': restaurant_id}}
    )
    return response.get('Item')
