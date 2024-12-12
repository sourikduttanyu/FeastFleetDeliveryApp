import json
import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError
from decimal import Decimal

# 初始化 DynamoDB 资源
dynamodb = boto3.resource('dynamodb')

# DynamoDB 表名
TABLE_NAME = 'Menu_Items'

def decimal_to_float(obj):
    """
    递归地将 DynamoDB 中的 Decimal 类型转换为 float。
    """
    if isinstance(obj, list):
        return [decimal_to_float(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj)
    else:
        return obj

def get_menu_by_restaurant_id(restaurant_id):
    """
    使用 DynamoDB Scan 根据 restaurant_id 检索菜单数据。
    """
    table = dynamodb.Table(TABLE_NAME)
    try:
        # 使用 Scan 查询，基于属性过滤
        response = table.scan(
            FilterExpression=Attr('restaurant_id').eq(restaurant_id)
        )

        # 返回结果
        if 'Items' in response and len(response['Items']) > 0:
            return decimal_to_float(response['Items'])
        else:
            return None

    except ClientError as e:
        print(f"Error retrieving menu from DynamoDB: {e}")
        return None

def lambda_handler(event, context):
    """
    Lambda 函数入口点：处理路径参数并查询菜单数据。
    """
    try:
        # 从路径参数中提取 restaurant_id
        body = json.loads(event['body'])
        restaurant_id = body.get('restaurantId')

        if not restaurant_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Restaurant ID is required in the path.'})
            }

        # 查询 DynamoDB
        menu_data = get_menu_by_restaurant_id(restaurant_id)

        if menu_data:
            return {
                'statusCode': 200,
                'body': json.dumps({'menu': menu_data})
            }
        else:
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
