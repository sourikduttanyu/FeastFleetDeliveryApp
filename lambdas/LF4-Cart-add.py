"""
LF4-Cart-add.py — AWS Lambda: Add or Replace Cart in DynamoDB

This Lambda function handles cart creation and replacement for the FeastFleet
delivery application. When a user finalizes their item selection, this function
computes the order total and writes the complete cart (user, restaurant, items,
and total price) as a single record to the DynamoDB 'Cart' table.

Because DynamoDB's put_item replaces the existing record if one with the same
primary key already exists, this function effectively implements an "upsert"
— creating a new cart or overwriting an existing one for the same user.

Pricing is handled using Python's Decimal type throughout to avoid floating-point
precision errors when computing monetary totals.

AWS Services Used:
    - Amazon DynamoDB: Stores the cart record in the 'Cart' table, keyed by
      'user_id'. Each write replaces any previously saved cart for that user.

Event Structure (expected input — passed directly as a dict, not API Gateway format):
    {
        "userid":        "<Cognito user_id>",
        "restaurant_id": "<restaurant identifier>",
        "item_list": [
            {
                "item_id":       "<menu item ID>",
                "item_name":     "<menu item name>",
                "item_quantity": <integer quantity>,
                "item_price":    <float or string price per unit>
            },
            ...
        ]
    }

Returns:
    - 200 with the saved cart data on success
    - 400 if any required field (userid, restaurant_id, item_list) is missing
    - 500 if the DynamoDB write fails or any unexpected error occurs
"""

from decimal import Decimal
import json
import boto3
from botocore.exceptions import ClientError

# Initialize the DynamoDB resource at module level to reuse the connection
# across Lambda warm-start invocations, reducing per-request latency
dynamodb = boto3.resource('dynamodb')

# Name of the DynamoDB table that stores cart records
CART_TABLE_NAME = 'Cart'


def calculate_total_price(item_list):
    """
    Compute the total price of all items in the cart using fixed-point Decimal arithmetic.

    Using Decimal (rather than float) is critical for monetary calculations to avoid
    floating-point precision errors (e.g., 0.1 + 0.2 != 0.3 in IEEE 754 floats).
    Item quantities and prices are explicitly cast via str() before constructing
    Decimal objects to prevent implicit float precision loss.

    Args:
        item_list (list[dict]): A list of cart items, each containing:
            - 'item_quantity' (int | str | float): Number of units ordered.
            - 'item_price'    (float | str):       Price per unit.

    Returns:
        Decimal: The total price of all items (quantity * unit_price, summed).
                 Returned as Decimal to maintain precision for the DynamoDB write.
    """
    # Sum quantity * price for each item, casting through str to avoid float imprecision
    total_price = sum(Decimal(str(item['item_quantity'])) * Decimal(str(item['item_price'])) for item in item_list)
    return total_price  # Return Decimal type for precise monetary storage


def insert_cart(data):
    """
    Write the cart record to DynamoDB using put_item.

    DynamoDB's put_item performs an unconditional write: if a record with the
    same primary key ('user_id') already exists, it is completely replaced.
    This makes the cart effectively a single active cart per user.

    Args:
        data (dict): The cart record to write. Must include 'user_id' as the
                     primary key and all required cart fields. Numeric values
                     should be Decimal (not float) for DynamoDB compatibility.

    Returns:
        bool: True if the write succeeded, False if a DynamoDB ClientError occurred.
    """
    table = dynamodb.Table(CART_TABLE_NAME)
    try:
        # put_item creates or fully replaces the record for the given user_id
        table.put_item(Item=data)
        return True
    except ClientError as e:
        print(f"Error inserting cart into DynamoDB: {e}")
        return False


def lambda_handler(event, context):
    """
    AWS Lambda entry point for adding or replacing a user's cart.

    Validates the incoming event, calculates the order total, structures the
    cart data with Decimal-typed prices for DynamoDB compatibility, and persists
    the cart. Returns the saved cart data to the caller on success.

    Note: Unlike most API Gateway Lambdas, this function reads the event dict
    directly (not event['body']), indicating it may be invoked directly or via
    a proxy that already parsed the body.

    Args:
        event   (dict): Lambda event payload containing 'userid', 'restaurant_id',
                        and 'item_list'. Consumed directly (not as a JSON string).
        context (obj):  Lambda context object (runtime metadata, unused here).

    Returns:
        dict: HTTP-style response with 'statusCode' and 'body'.
              200 with the full cart data (serialized with default=str to handle
              Decimal values) on success.
              400 if any required field is missing.
              500 if the DynamoDB write fails or an unexpected error occurs.
    """
    try:
        # The event is consumed directly as a dict (no JSON parsing needed),
        # which differs from API Gateway proxy integration where body is a string
        body = event

        # Validate that all required fields are present before processing.
        # Missing any of these makes it impossible to create a valid cart record.
        required_fields = ['userid', 'restaurant_id', 'item_list']
        for field in required_fields:
            if field not in body:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'message': f'Missing required field: {field}.'})
                }

        # Compute the total order price from the item list before building the record
        item_list = body['item_list']
        total_price = calculate_total_price(item_list)
        print(item_list)

        # Build the DynamoDB cart record.
        # All numeric price/quantity fields are cast to Decimal via str() to ensure:
        #   1. DynamoDB compatibility (DynamoDB does not accept Python floats)
        #   2. Precision integrity for monetary values
        cart_data = {
            'user_id': body['userid'],          # Primary key — Cognito user ID
            'restaurant_id': body['restaurant_id'],
            'item_list': [
                {
                    'item_id': item['item_id'],
                    'item_name': item['item_name'],
                    'item_quantity': Decimal(str(item['item_quantity'])),  # Cast to Decimal for DynamoDB
                    'item_price': Decimal(str(item['item_price']))         # Cast to Decimal for DynamoDB
                }
                for item in item_list
            ],
            'total_price': total_price  # Pre-computed Decimal total
        }

        # Persist the cart record to DynamoDB; existing cart for this user is overwritten
        success = insert_cart(cart_data)

        if success:
            return {
                'statusCode': 200,
                # default=str handles Decimal serialization since json doesn't support it natively
                'body': json.dumps({'message': 'Cart inserted successfully.', 'cart': cart_data}, default=str)
            }
        else:
            return {
                'statusCode': 500,
                'body': json.dumps({'message': 'Failed to insert cart.'})
            }

    except Exception as e:
        print(f"Error in Lambda handler: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Internal server error', 'error': str(e)})
        }
