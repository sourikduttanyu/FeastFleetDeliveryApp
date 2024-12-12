from decimal import Decimal
import json
import boto3
from botocore.exceptions import ClientError

# 初始化 DynamoDB 资源
dynamodb = boto3.resource('dynamodb')

# DynamoDB 表名
CART_TABLE_NAME = 'Cart'

def calculate_total_price(item_list):
    """
    计算购物车总价格。
    """
    total_price = sum(Decimal(str(item['item_quantity'])) * Decimal(str(item['item_price'])) for item in item_list)
    return total_price  # 返回 Decimal 类型

def insert_cart(data):
    """
    插入购物车数据到 DynamoDB。
    """
    table = dynamodb.Table(CART_TABLE_NAME)
    try:
        table.put_item(Item=data)
        return True
    except ClientError as e:
        print(f"Error inserting cart into DynamoDB: {e}")
        return False

def lambda_handler(event, context):
    """
    Lambda 函数入口点。
    """
    try:
        # 解析请求体
        body = event

        # 验证必需字段
        required_fields = ['userid', 'restaurant_id', 'item_list']
        for field in required_fields:
            if field not in body:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'message': f'Missing required field: {field}.'})
                }

        # 计算总价格
        item_list = body['item_list']
        total_price = calculate_total_price(item_list)
        print(item_list)
        # 构建数据
        cart_data = {
            'user_id': body['userid'],
            'restaurant_id': body['restaurant_id'],
            'item_list': [
                {
                    'item_id':item['item_id'],
                    'item_name': item['item_name'],
                    'item_quantity': Decimal(str(item['item_quantity'])),
                    'item_price': Decimal(str(item['item_price']))
                }
                for item in item_list
            ],
            'total_price': total_price
        }

        # 插入数据到 DynamoDB
        success = insert_cart(cart_data)

        if success:
            return {
                'statusCode': 200,
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
