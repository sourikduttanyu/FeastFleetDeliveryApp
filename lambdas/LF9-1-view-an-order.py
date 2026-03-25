"""
LF9-1 - View a Single Order Lambda
-------------------------------------
Purpose:
    Returns a fully enriched view of a single order, combining data from four
    DynamoDB tables. Given an order ID (from the URL path), this Lambda:
      1. Fetches the core order record from the Order table.
      2. Enriches each line-item with name and price from the Menu_Items table.
      3. Fetches the associated restaurant's name and address from the Restaurant table.
      4. Fetches delivery tracking information from the Delivery_Tracking table (if available).

    The result is a single composite JSON response suitable for rendering an
    order detail page on the frontend.

AWS Integrations:
    - API Gateway: Triggers this Lambda via a GET request with {orderId} as a
                   path parameter (e.g., GET /orders/{orderId}).
    - DynamoDB (Order):           Fetched by partition key 'order_id'.
    - DynamoDB (Restaurant):      Fetched by partition key 'restaurant_id'.
    - DynamoDB (Delivery_Tracking): Fetched by partition key 'order_id'.
    - DynamoDB (Menu_Items):      Fetched individually per line-item by 'item_id'.

Event Structure (API Gateway Proxy Integration):
    {
        "pathParameters": {
            "orderId": "<order-uuid>"
        }
    }

Returns:
    HTTP 200 with a composite JSON body containing order_info, restaurant_info,
    and delivery_info on success.
    HTTP 400 if orderId is missing from the path.
    HTTP 404 if no order matches the provided orderId.
    HTTP 500 on any unexpected server error.
    All responses include CORS headers to support browser-based clients.
"""

import json
import boto3
from decimal import Decimal

# Initialize DynamoDB resource — uses the execution role's default region
dynamodb = boto3.resource('dynamodb')

# Reference your tables
order_table = dynamodb.Table('Order')
restaurant_table = dynamodb.Table('Restaurant')
delivery_table = dynamodb.Table('Delivery_Tracking')
menu_items_table = dynamodb.Table('Menu_Items')


def convert_decimal(obj):
    """
    Recursively converts DynamoDB Decimal values to native Python int or float.

    DynamoDB stores all numeric values as the Decimal type, which is not JSON-
    serializable by default. This helper traverses nested dicts and lists to
    replace every Decimal with an int (if the value is whole) or float (if it
    has a fractional part), making the object safe to pass to json.dumps().

    Args:
        obj: Any Python object — typically a dict, list, or scalar returned
             by a DynamoDB get_item / query response.

    Returns:
        The same structure with all Decimal instances replaced by int or float.
    """
    if isinstance(obj, list):
        # Recurse into each element of a list
        return [convert_decimal(i) for i in obj]
    elif isinstance(obj, dict):
        # Recurse into each value in a dict (keys are always strings in DynamoDB)
        return {k: convert_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        # Convert whole numbers to int to avoid unnecessary decimal points in JSON
        return int(obj) if obj % 1 == 0 else float(obj)
    else:
        # Non-Decimal scalars (str, int, bool, None) are returned unchanged
        return obj


def lambda_handler(event, context):
    """
    Main entry point for the View Single Order Lambda.

    Validates the path parameter, fetches the order and all related data from
    DynamoDB, and assembles a composite response. Individual item lookups are
    performed in a loop (N+1 pattern) — one get_item call per line-item in the
    order to retrieve name and price from Menu_Items.

    Args:
        event (dict): API Gateway proxy event. The order ID is expected under
                      event['pathParameters']['orderId'].
        context (LambdaContext): AWS Lambda context object (unused here).

    Returns:
        dict: API Gateway-compatible HTTP response with statusCode, CORS headers,
              and a JSON body containing order_info, restaurant_info, delivery_info.
    """
    try:
        print("Received event:", json.dumps(event))

        # Extract order_id from pathParameters — populated by API Gateway from the URL path
        order_id = event.get('pathParameters', {}).get('orderId')
        print(f"Extracted order_id: {order_id}")

        if not order_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type'
                },
                'body': json.dumps({'message': 'Order ID is required'})
            }

        # Fetch the order details from the Order table using the partition key
        order_response = order_table.get_item(Key={'order_id': order_id})
        if 'Item' not in order_response:
            # Order does not exist — return 404 rather than an empty object
            return {
                'statusCode': 404,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type'
                },
                'body': json.dumps({'message': 'Order not found'})
            }

        # Convert Decimal fields to native Python types before further processing
        order = convert_decimal(order_response['Item'])

        # Fetch the restaurant details from the Restaurant table.
        # Uses .get('Item', {}) to safely handle cases where the restaurant
        # record was deleted or is otherwise missing.
        restaurant_response = restaurant_table.get_item(Key={'restaurant_id': order['restaurant_id']})
        restaurant = convert_decimal(restaurant_response.get('Item', {}))
        restaurant_name = restaurant.get('name', 'Unknown')
        restaurant_address = restaurant.get('address', 'Unknown')

        # Fetch the delivery tracking details from the Delivery_Tracking table.
        # Delivery records are only created once an order is OUT_FOR_DELIVERY,
        # so 'delivery' may be None for orders that haven't shipped yet.
        delivery_response = delivery_table.get_item(Key={'order_id': order_id})
        delivery = convert_decimal(delivery_response.get('Item', {})) if 'Item' in delivery_response else None

        # Fetch item details from the Menu_Items table.
        # The order's 'items' field is a list of {item_id, quantity} dicts.
        # We enrich each entry with the item's name and current price by performing
        # an individual get_item lookup per line-item (N+1 reads).
        items_with_details = []
        for item in order['items']:
            item_id = item['item_id']
            item_quantity = item['quantity']
            menu_item_response = menu_items_table.get_item(Key={'item_id': item_id})
            if 'Item' in menu_item_response:
                menu_item = convert_decimal(menu_item_response['Item'])
                items_with_details.append({
                    'item_id': item_id,
                    'item_name': menu_item.get('item_name', 'Unknown'),
                    'price': menu_item.get('price', 0),
                    'quantity': item_quantity,
                })

        # Replace the raw {item_id, quantity} list with the enriched version
        order['items'] = items_with_details

        # Construct the response payload with limited restaurant details.
        # Only name and address are exposed — not the full restaurant document —
        # to avoid leaking internal data (e.g., owner info, coordinates).
        result = {
            'order_info': order,
            'restaurant_info': {
                'name': restaurant_name,
                'address': restaurant_address
            },
            'delivery_info': delivery
        }

        return {
            'statusCode': 200,
            'headers': {
                # CORS headers are required so the browser-based frontend can
                # call this API from a different origin (e.g., S3-hosted SPA)
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': json.dumps(result)
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': json.dumps({'message': 'Internal server error'})
        }
