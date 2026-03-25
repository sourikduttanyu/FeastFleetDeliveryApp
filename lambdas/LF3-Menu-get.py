"""
LF3-Menu-get.py — AWS Lambda: Fetch Menu Items by Restaurant ID

This Lambda function retrieves all menu items for a given restaurant from
Amazon DynamoDB. It scans the 'Menu_Items' table and filters results by
the specified restaurant ID, returning the full list of menu entries to
the caller.

Because DynamoDB's Decimal type is not natively JSON-serializable, the
response data is recursively converted from Decimal to float before being
serialized and returned.

AWS Services Used:
    - Amazon DynamoDB: Stores menu items in the 'Menu_Items' table. Each item
      includes a 'restaurant_id' attribute used for filtering via a Scan
      with FilterExpression.

Event Structure (expected input):
    {
        "body": "{\"restaurantId\": \"<restaurant identifier>\"}"
    }
    Note: 'body' is a JSON-encoded string, as provided by API Gateway.

Returns:
    - 200 with a list of menu items under the 'menu' key on success
    - 400 if restaurantId is missing from the request body
    - 404 if no menu items are found for the given restaurant ID
    - 500 for any unexpected errors
"""

import json
import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError
from decimal import Decimal

# Initialize the DynamoDB resource client at module level so it is reused
# across Lambda invocations (warm starts), avoiding repeated initialization overhead
dynamodb = boto3.resource('dynamodb')

# Name of the DynamoDB table that stores menu items
TABLE_NAME = 'Menu_Items'


def decimal_to_float(obj):
    """
    Recursively convert all Decimal values within a DynamoDB response object
    to Python floats for JSON serialization compatibility.

    DynamoDB's boto3 client returns numeric values as Python Decimal objects
    to preserve precision. However, the standard json.dumps() function does not
    support Decimal natively and will raise a TypeError. This function performs
    a deep traversal to convert every Decimal encountered in the nested structure.

    Args:
        obj (any): The object to convert. Can be a dict, list, Decimal,
                   or any other type (passed through unchanged).

    Returns:
        any: The same structure with all Decimal values replaced by floats.
    """
    if isinstance(obj, list):
        # Recursively process each element in a list
        return [decimal_to_float(i) for i in obj]
    elif isinstance(obj, dict):
        # Recursively process each value in a dictionary
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        # Convert Decimal to float for JSON serialization
        return float(obj)
    else:
        # Return all other types (str, int, bool, None) unchanged
        return obj


def get_menu_by_restaurant_id(restaurant_id):
    """
    Scan the DynamoDB 'Menu_Items' table and return all items belonging to
    the specified restaurant.

    Note: This uses a DynamoDB Scan with a FilterExpression rather than a
    Query, because 'restaurant_id' is not the table's primary key. For tables
    with a large number of items, a GSI on 'restaurant_id' would be more
    efficient and should be considered as a future optimization.

    Args:
        restaurant_id (str): The ID of the restaurant whose menu is to be retrieved.

    Returns:
        list[dict] | None: A list of menu item dictionaries with Decimal values
                           converted to floats, or None if no items are found or
                           a DynamoDB error occurs.
    """
    table = dynamodb.Table(TABLE_NAME)
    try:
        # Use a Scan with FilterExpression to retrieve all menu items where
        # the 'restaurant_id' attribute equals the requested restaurant ID.
        # FilterExpression is applied after the scan reads all items, so the
        # consumed capacity is proportional to the full table size.
        response = table.scan(
            FilterExpression=Attr('restaurant_id').eq(restaurant_id)
        )

        # Return the filtered items if any were found, converting Decimals to floats
        if 'Items' in response and len(response['Items']) > 0:
            return decimal_to_float(response['Items'])
        else:
            return None

    except ClientError as e:
        print(f"Error retrieving menu from DynamoDB: {e}")
        return None


def lambda_handler(event, context):
    """
    AWS Lambda entry point for retrieving a restaurant's menu.

    Parses the restaurantId from the API Gateway event body, fetches the
    corresponding menu items from DynamoDB, and returns them as a JSON response.

    Args:
        event   (dict): Lambda event from API Gateway. The 'body' field is a
                        JSON-encoded string containing 'restaurantId'.
        context (obj):  Lambda context object (runtime metadata, unused here).

    Returns:
        dict: HTTP-style response with 'statusCode' and 'body'.
              200 with {'menu': [...]} on success.
              400 if restaurantId is absent from the request.
              404 if no menu items exist for the given restaurant ID.
              500 for any unexpected runtime errors.
    """
    try:
        # Parse the restaurant ID from the JSON-encoded API Gateway body
        body = json.loads(event['body'])
        restaurant_id = body.get('restaurantId')

        # Validate that a restaurant ID was provided before querying DynamoDB
        if not restaurant_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Restaurant ID is required in the path.'})
            }

        # Query DynamoDB for all menu items associated with the given restaurant ID
        menu_data = get_menu_by_restaurant_id(restaurant_id)

        if menu_data:
            return {
                'statusCode': 200,
                'body': json.dumps({'menu': menu_data})
            }
        else:
            # Return 404 if no menu items were found for the provided restaurant ID
            return {
                'statusCode': 404,
                'body': json.dumps({'message': 'Menu not found for the given Restaurant ID.'})
            }

    except Exception as e:
        print(f"Error in Lambda handler: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Internal server error', 'error': str(e)})
        }
