import json
import boto3
from decimal import Decimal

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb')

# Reference your tables
order_table = dynamodb.Table('Order')
restaurant_table = dynamodb.Table('Restaurant')
delivery_table = dynamodb.Table('Delivery_Tracking')

# Helper function to convert Decimal to int or float
def convert_decimal(obj):
    if isinstance(obj, list):
        return [convert_decimal(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    else:
        return obj

def lambda_handler(event, context):
    try:
        print("Received event:", json.dumps(event))
        
        # Extract order_id from pathParameters
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
        
        # Fetch the order details from the Order table
        order_response = order_table.get_item(Key={'order_id': order_id})
        if 'Item' not in order_response:
            return {
                'statusCode': 404,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type'
                },
                'body': json.dumps({'message': 'Order not found'})
            }
        
        # Convert Decimal fields to native Python types
        order = convert_decimal(order_response['Item'])
        
        # Fetch the restaurant details from the Restaurant table
        restaurant_response = restaurant_table.get_item(Key={'restaurant_id': order['restaurant_id']})
        restaurant = convert_decimal(restaurant_response.get('Item', {}))
        
        # Fetch the delivery tracking details from the Delivery_Tracking table
        delivery_response = delivery_table.get_item(Key={'order_id': order_id})
        delivery = convert_decimal(delivery_response.get('Item', {})) if 'Item' in delivery_response else None
        
        # Construct the response payload
        result = {
            'order_info': order,
            'restaurant_info': restaurant,
            'delivery_info': delivery
        }
        
        return {
            'statusCode': 200,
            'headers': {
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
