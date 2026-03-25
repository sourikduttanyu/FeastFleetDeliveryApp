"""
LF6-Cart-view.py — AWS Lambda: View Cart Contents by User ID

This Lambda function retrieves the current cart for a given user from the
DynamoDB 'Cart' table. It performs a direct primary-key lookup using the
user's ID, returning the complete cart record if one exists.

The cart record was previously written by LF4-Cart-add and contains the
user's selected restaurant, ordered items (with quantities and prices),
and the precomputed total price.

AWS Services Used:
    - Amazon DynamoDB: Stores cart records in the 'Cart' table, keyed by
      'user_id'. The get_item call performs an O(1) primary-key lookup,
      making this operation highly efficient regardless of table size.

Event Structure (expected input — passed directly as a dict, not API Gateway format):
    {
        "user_id": "<Cognito user_id>"
    }

Returns:
    - 200 with the full cart record on success
    - 400 if user_id is missing from the request
    - 404 if no cart exists for the given user ID
    - 500 for any unexpected errors
"""

import boto3
from botocore.exceptions import ClientError
import json

# Initialize the DynamoDB resource at module level to reuse the connection
# across Lambda warm-start invocations, reducing per-request latency
dynamodb = boto3.resource('dynamodb')

# Name of the DynamoDB table that stores cart records
CART_TABLE_NAME = 'Cart'


def get_cart_by_user_id(user_id):
    """
    Retrieve a user's cart from DynamoDB using a direct primary-key lookup.

    Uses DynamoDB's get_item API, which performs an O(1) lookup by primary key
    ('user_id'). This is the most efficient DynamoDB read operation, consuming
    a single read capacity unit and avoiding the overhead of a scan or query.

    Args:
        user_id (str): The Cognito user ID ('sub') used as the DynamoDB primary key.

    Returns:
        dict | None: The full cart item (including restaurant_id, item_list,
                     and total_price) if found, or None if no cart exists for
                     the given user ID or if a DynamoDB error occurs.
    """
    table = dynamodb.Table(CART_TABLE_NAME)
    try:
        # Perform a direct primary-key lookup — the most efficient DynamoDB read
        response = table.get_item(Key={'user_id': user_id})

        # DynamoDB returns the item under the 'Item' key if found.
        # If no record matches, the 'Item' key is absent from the response.
        if 'Item' in response:
            return response['Item']
        else:
            return None  # No cart found for this user
    except ClientError as e:
        print(f"Error fetching cart from DynamoDB: {e}")
        return None


def lambda_handler(event, context):
    """
    AWS Lambda entry point for retrieving a user's cart.

    Reads the user_id from the event, fetches the corresponding cart from
    DynamoDB, and returns it as a JSON response. The cart data is serialized
    with default=str to handle DynamoDB's Decimal type, which is not natively
    JSON-serializable.

    Note: Like LF4-Cart-add, this function reads user_id directly from the event
    dict rather than parsing event['body'], indicating direct invocation or a
    non-proxy API Gateway integration.

    Args:
        event   (dict): Lambda event payload containing 'user_id'.
        context (obj):  Lambda context object (runtime metadata, unused here).

    Returns:
        dict: HTTP-style response with 'statusCode' and 'body'.
              200 with {'message': ..., 'cart': {...}} on success.
              400 if user_id is absent from the event.
              404 if no cart exists for the given user_id.
              500 for any unexpected runtime errors.
    """
    try:
        # Extract user_id from the event; use .get() to safely handle missing key
        user_id = event.get('user_id')

        # Validate that a user_id was provided before making the DynamoDB call
        if not user_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Missing user_id in request.'})
            }

        # Fetch the cart from DynamoDB using a primary-key get_item lookup
        cart = get_cart_by_user_id(user_id)

        if cart:
            return {
                'statusCode': 200,
                # default=str handles Decimal serialization (DynamoDB numeric values
                # are returned as Decimal objects, which json.dumps cannot handle natively)
                'body': json.dumps({'message': 'Cart retrieved successfully.', 'cart': cart}, default=str)
            }
        else:
            # No cart record found for the provided user_id
            return {
                'statusCode': 404,
                'body': json.dumps({'message': 'Cart not found for the given user_id.'})
            }

    except Exception as e:
        print(f"Error in Lambda handler: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Internal server error', 'error': str(e)})
        }
