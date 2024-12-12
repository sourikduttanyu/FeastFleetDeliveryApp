import boto3
import json
import logging
import requests 
from requests_aws4auth import AWS4Auth
from requests.auth import HTTPBasicAuth
from botocore.exceptions import ClientError
region = 'us-east-1'
opensearch_url = 'https://search-feastfleet-ylmv33u5rsoztak4q2xazv4x7u.us-east-1.es.amazonaws.com/restaurants_index/_search'

session = boto3.Session()
credentials = session.get_credentials()
service = "es"
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    region,
    service,
    session_token=credentials.token
)


def get_restaurant_by_name(name):

    query = {
        "size": 10,
        "query":{
            "match":{
                "name": name,
            }
        }
    }

    headers = { "Content-Type" : "application/json"}
    try:
        response = requests.get(
            opensearch_url,
            auth=('admin', 'Cloudcomputing2024!!'),
            headers=headers,
            json=query
        )
        response_json = response.json()
        print(response_json)
        restaurant_ids = [hit["_id"] for hit in response_json["hits"]["hits"]]
        return restaurant_ids
    except Exception as e:
        print("Error querying OpenSearch:", e)
        return []


def get_restaurant_recommendations(cuisine_type):

    query = {
        "size": 10,  # 设置返回结果数量
        "query": {
            "match": {
                "cuisine": cuisine_type  # 根据 cuisineType 匹配
            }
        }
    }

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.get(
            opensearch_url,
            auth=('admin', 'Cloudcomputing2024!!'),
            headers=headers,
            json=query
        )
        response_json = response.json()
        print(response_json)
        restaurant_ids = [hit["_id"] for hit in response_json["hits"]["hits"]]
        return restaurant_ids
    except Exception as e:
        print("Error querying OpenSearch:", e)
        return []

def lambda_handler(event, context):
    """
    Lambda 函数入口点
    """
    try:
        body = json.loads(event['body'])
        query_type = body.get('type')
        query = body.get('query')

        restaurant_ids = []
        if query_type == "name":
            restaurant_ids = get_restaurant_by_name(query)
        elif query_type == "cuisineType":
            restaurant_ids = get_restaurant_recommendations(query)
        else:
            return {
                "statusCode": 400,
                "body": "Invalid query type"
            }
        

        return {
            'statusCode': 200,
            'body': json.dumps({'restaurantIds': restaurant_ids})
        }

    except Exception as e:
        print("Error in Lambda handler:", e)
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Internal server error', 'error': str(e)})
        }