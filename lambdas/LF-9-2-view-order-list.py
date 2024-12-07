import json
import boto3
from decimal import Decimal

dynamodb = boto3.resource('dynamodb', region_name="us-east-1")
order_table = dynamodb.Table('Order')
restaurant_table = dynamodb.Table('Restaurant')

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    try:
        print("Received event:", json.dumps(event))
        print("Query parameters:", event.get('queryStringParameters'))
        
        user_id = event.get('queryStringParameters', {}).get('user_id')
        print("Extracted user_id:", user_id)

        if not user_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'user_id is required'})
            }
        
        # Query orders for the user
        response = order_table.scan(
            FilterExpression='user_id = :uid',
            ExpressionAttributeValues={':uid': user_id}
        )
        
        orders = response.get('Items', [])
        
        # Process each order to include restaurant name and item count
        processed_orders = []
        for order in orders:
            # Get restaurant name
            restaurant_response = restaurant_table.get_item(
                Key={'restaurant_id': order['restaurant_id']}
            )
            restaurant_name = restaurant_response.get('Item', {}).get('name', 'Unknown Restaurant')
            
            # Count items
            items_count = sum(item['quantity'] for item in order.get('items', []))
            
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
            }, cls=DecimalEncoder)
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': f'Internal server error: {str(e)}'})
        }
