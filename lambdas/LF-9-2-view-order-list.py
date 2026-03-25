"""
LF9-2 - View Order List Lambda
---------------------------------
Purpose:
    Returns a summarised list of all orders belonging to a specific user.
    For each order the response includes the restaurant name, the total item
    count (sum of all line-item quantities), order status, timestamp, and
    total price — providing enough context for an order history page without
    returning full item-level detail.

    NOTE: This Lambda uses a DynamoDB table scan with a FilterExpression to
    find orders by user_id. This is an O(N) table scan and is suitable for
    development / small datasets. For production scale, adding a GSI on
    (user_id, timestamp) would allow an efficient key-based Query instead.

AWS Integrations:
    - API Gateway: Triggers this Lambda via a GET request with 'user_id' as
                   a query string parameter (e.g., GET /orders?user_id=...).
    - DynamoDB (Order):      Full-table scan filtered by user_id to retrieve
                             the user's order history.
    - DynamoDB (Restaurant): Individual get_item calls per order to resolve
                             the restaurant name for display.

Event Structure (API Gateway Proxy Integration):
    {
        "queryStringParameters": {
            "user_id": "<cognito-sub>"
        }
    }

Returns:
    HTTP 200 with a JSON body containing an 'orders' array of summarised
    order objects on success.
    HTTP 400 if 'user_id' is not provided as a query parameter.
    HTTP 500 on any unexpected server error.
"""

import json
import boto3
from decimal import Decimal

# DynamoDB resource — explicitly targeting us-east-1 where tables are deployed
dynamodb = boto3.resource('dynamodb', region_name="us-east-1")

# Table references used for scanning orders and resolving restaurant names
order_table = dynamodb.Table('Order')
restaurant_table = dynamodb.Table('Restaurant')


class DecimalEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that serialises DynamoDB Decimal values as strings.

    DynamoDB represents all numeric attributes as Python Decimal objects, which
    the standard json.JSONEncoder cannot handle. This subclass overrides the
    default method to convert Decimal to str, preserving full numeric precision
    (avoiding floating-point rounding) at the cost of the value being a string
    in the JSON output.

    Usage:
        json.dumps(data, cls=DecimalEncoder)
    """
    def default(self, obj):
        if isinstance(obj, Decimal):
            # Convert Decimal to string to preserve precision in the JSON output.
            # The caller (typically the frontend) is responsible for parsing it back
            # to a number when needed.
            return str(obj)
        return super(DecimalEncoder, self).default(obj)


def lambda_handler(event, context):
    """
    Main entry point for the View Order List Lambda.

    Reads the 'user_id' from the query string, scans the Order table for all
    matching orders, and enriches each with the restaurant's display name and
    a total item count before returning the list.

    Args:
        event (dict): API Gateway proxy event. 'user_id' must be present in
                      event['queryStringParameters'].
        context (LambdaContext): AWS Lambda context object (unused here).

    Returns:
        dict: API Gateway-compatible HTTP response with statusCode and a JSON
              body containing an 'orders' list.
    """
    try:
        print("Received event:", json.dumps(event))
        print("Query parameters:", event.get('queryStringParameters'))

        # Extract user_id from query string parameters
        user_id = event.get('queryStringParameters', {}).get('user_id')
        print("Extracted user_id:", user_id)

        if not user_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'user_id is required'})
            }

        # Scan the entire Order table and filter client-side for the given user_id.
        # The FilterExpression is applied AFTER DynamoDB reads each page, so it
        # does not reduce read capacity consumption — it reduces only the returned
        # dataset. A GSI on user_id would make this a key-based Query instead.
        response = order_table.scan(
            FilterExpression='user_id = :uid',
            ExpressionAttributeValues={':uid': user_id}
        )

        # 'Items' contains the filtered results from the scan; default to empty list
        orders = response.get('Items', [])

        # Process each order to include restaurant name and item count
        processed_orders = []
        for order in orders:
            # Get restaurant name — one get_item call per order (N+1 reads).
            # Using .get('Item', {}) defensively in case the restaurant was deleted.
            restaurant_response = restaurant_table.get_item(
                Key={'restaurant_id': order['restaurant_id']}
            )
            restaurant_name = restaurant_response.get('Item', {}).get('name', 'Unknown Restaurant')

            # Sum the 'quantity' field across all line-items to get the total
            # number of individual items in the order (not just distinct menu entries)
            items_count = sum(item['quantity'] for item in order.get('items', []))

            # Build a lightweight summary object for the order list view.
            # total_price is explicitly cast to str here to handle Decimal values
            # consistently; the DecimalEncoder below handles any remaining Decimals.
            processed_orders.append({
                'order_id': order['order_id'],
                'restaurant_id': order['restaurant_id'],
                'restaurant_name': restaurant_name,
                'status': order['status'],
                'timestamp': order['timestamp'],
                'total_price': str(order.get('total_price', '0')),
                'items_count': items_count
            })

        return {
            'statusCode': 200,
            'body': json.dumps({
                'orders': processed_orders
            }, cls=DecimalEncoder)  # DecimalEncoder handles any remaining Decimal values
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': f'Internal server error: {str(e)}'})
        }
