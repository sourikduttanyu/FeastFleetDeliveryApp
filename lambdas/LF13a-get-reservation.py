"""
LF13a - Get Single Reservation Lambda
======================================
AWS Services: Amazon DynamoDB, Amazon API Gateway (via Cognito Authorizer)

Purpose:
    Retrieves a single reservation for an authenticated user, enriched with
    restaurant name and address. Enforces ownership so users can only access
    their own reservations.

Event Structure (API Gateway Proxy Integration - GET request):
    {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "<cognito-user-uuid>"   # Injected by Cognito JWT authorizer
                }
            }
        },
        "queryStringParameters": {
            "reservation_id": "<uuid>"             # Passed as a URL query parameter
        }
    }

Returns:
    HTTP 200 with a formatted reservation object (including restaurant metadata).
    HTTP 400 if reservation_id is missing from query parameters.
    HTTP 401 if the caller is not authenticated.
    HTTP 403 if the caller does not own the requested reservation.
    HTTP 404 if the reservation does not exist.
    HTTP 500 for unexpected server-side errors.
"""

import boto3
import json

# Initialize the low-level DynamoDB client.
# The low-level client returns native DynamoDB type descriptors (e.g., {'S': '...'}).
dynamodb = boto3.client('dynamodb')

# DynamoDB table names referenced by this Lambda.
RESERVATION_TABLE = 'Reservation'
RESTAURANT_TABLE = 'Restaurant'

def lambda_handler(event, context):
    """
    Main entry point for the Lambda function.

    Validates the authenticated user, reads reservation_id from query string
    parameters, fetches the matching reservation, enforces ownership, then
    joins the associated restaurant record to build an enriched response.

    Args:
        event (dict): API Gateway proxy event containing request context
                      and query string parameters.
        context (LambdaContext): AWS Lambda runtime context (unused).

    Returns:
        dict: API Gateway-compatible HTTP response with a statusCode and
              a JSON-encoded body containing the formatted reservation.
    """
    try:
        # --- Authentication Check ---
        # The 'sub' claim is the unique Cognito user UUID, injected by the
        # API Gateway Cognito authorizer after validating the JWT.
        user_id = event['requestContext']['authorizer']['claims']['sub']
        if not user_id:
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Unauthorized, please login or create an account'})
            }

        # --- Input Extraction ---
        # reservation_id is passed as a URL query parameter (e.g., ?reservation_id=abc123).
        reservation_id = event['queryStringParameters'].get('reservation_id')
        print('RES_ID: ', reservation_id)
        if not reservation_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'reservation_id is required'})
            }

        # --- Reservation Lookup ---
        reservation = get_reservation(reservation_id)
        print(reservation)
        if not reservation:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Reservation not found'})
            }

        # --- Ownership Enforcement ---
        # Compare the stored user_id on the reservation against the authenticated caller.
        # This prevents users from reading other users' reservation details.
        if reservation['user_id']['S'] != user_id:
            return {
                'statusCode': 403,
                'body': json.dumps({'error': 'Access forbidden'})
            }

        # --- Restaurant Enrichment ---
        # Fetch the associated restaurant record so we can include its name
        # and address in the response, rather than exposing only the raw ID.
        restaurant = get_restaurant(reservation['restaurant_id']['S'])
        restaurant_name = restaurant['name']['S']
        restaurant_address = restaurant['address']['S']

        # Format and return the reservation
        return {
            'statusCode': 200,
            'body': json.dumps(format_reservation(reservation, restaurant_name, restaurant_address))
        }

    except Exception as e:
        # Catch-all for unexpected failures such as malformed events or
        # DynamoDB connectivity problems.
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def get_reservation(reservation_id):
    """
    Fetch a single reservation record from DynamoDB by its primary key.

    Uses a GetItem call, which is the most efficient DynamoDB read operation
    when the full partition key is known.

    Args:
        reservation_id (str): The UUID primary key of the reservation.

    Returns:
        dict or None: The raw DynamoDB item (with type descriptors) if found,
                      or None if the reservation does not exist.
    """
    response = dynamodb.get_item(
        TableName=RESERVATION_TABLE,
        Key={'reservation_id': {'S': reservation_id}}
    )
    # 'Item' is absent in the response if no record matches the key.
    return response.get('Item')

def get_restaurant(restaurant_id):
    """
    Fetch a single restaurant record from DynamoDB by its primary key.

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

def format_reservation(reservation, restaurant_name, restaurant_address):
    """
    Transform a raw DynamoDB reservation item into a clean, serializable dict.

    DynamoDB's low-level client returns values wrapped in type descriptors
    (e.g., {'S': 'value'} for strings, {'N': '2'} for numbers). This function
    unwraps those descriptors and also converts party_size from a string
    representation of a number to a proper Python int.

    Args:
        reservation (dict): Raw DynamoDB item with type descriptor wrappers.
        restaurant_name (str): Human-readable restaurant name to embed in the result.
        restaurant_address (str): Restaurant address to embed in the result.

    Returns:
        dict: A clean Python dictionary suitable for JSON serialization and
              direct consumption by the frontend.
    """
    return {
        'reservation_id': reservation['reservation_id']['S'],
        'user_id': reservation['user_id']['S'],
        'restaurant_id': reservation['restaurant_id']['S'],
        'restaurant_name': restaurant_name,
        'restaurant_address': restaurant_address,
        'res_date': reservation['res_date']['S'],
        'time': reservation['time']['S'],
        # DynamoDB stores numeric values as strings under the 'N' key;
        # cast to int for correct JSON output.
        'party_size': int(reservation['party_size']['N'])
    }
