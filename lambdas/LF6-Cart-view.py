import boto3
from botocore.exceptions import ClientError
import json

# 初始化 DynamoDB 资源
dynamodb = boto3.resource('dynamodb')

# DynamoDB 表名
CART_TABLE_NAME = 'Cart'

def get_cart_by_user_id(user_id):
    """
    根據 user_id 查詢用戶的 cart。
    """
    table = dynamodb.Table(CART_TABLE_NAME)
    try:
        # 查詢 DynamoDB
        response = table.get_item(Key={'user_id': user_id})
        if 'Item' in response:
            return response['Item']
        else:
            return None  # 未找到對應的 cart
    except ClientError as e:
        print(f"Error fetching cart from DynamoDB: {e}")
        return None

def lambda_handler(event, context):
    """
    Lambda 函數入口點。
    """
    try:
        # 假設事件中包含 user_id
        user_id = event.get('user_id')
        if not user_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Missing user_id in request.'})
            }

        # 查詢用戶的 cart
        cart = get_cart_by_user_id(user_id)

        if cart:
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Cart retrieved successfully.', 'cart': cart}, default=str)
            }
        else:
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
