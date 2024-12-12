import boto3
import json
import requests
from requests_aws4auth import AWS4Auth


region = 'us-east-1'

opensearch_url = 'https://search-feastfleet-ylmv33u5rsoztak4q2xazv4x7u.us-east-1.es.amazonaws.com/restaurants_index'  


service = "es"
session = boto3.Session()
credentials = session.get_credentials()
location_client = boto3.client('location', region_name=region)
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    region,
    service,
    session_token=credentials.token
)
def convert_coordinates_to_address(coordinates):
    try:
        # Coordinates should be in [longitude, latitude] format
        if isinstance(coordinates, dict) and 'lon' in coordinates and 'lat' in coordinates:
            position = [coordinates['lon'], coordinates['lat']]
        elif isinstance(coordinates, (list, tuple)) and len(coordinates) == 2:
            position = coordinates
        else:
            raise ValueError("Invalid coordinates format. Must be a dict with 'lon' and 'lat' keys, or a list/tuple.")

        response = location_client.search_place_index_for_position(
            IndexName='RestaurantPlaceIndex',  # Replace with your Place Index name
            Position=position
        )
        if response['Results']:
            return response['Results'][0]['Place']['Label']  # Return formatted address
        else:
            return None
    except Exception as e:
        print(f"Error converting coordinates to address: {e}")
        return None

def get_restaurant_by_id(restaurant_id):
    
    try:
        url = f"{opensearch_url}/_doc/{restaurant_id}" 
        response = requests.get(url, auth=('admin','Cloudcomputing2024!!'), headers={"Content-Type": "application/json"})
        response_json = response.json()
        print(response_json)
        if "_source" in response_json:
            return response_json["_source"] 
        else:
            return None

    except Exception as e:
        print(f"Error retrieving restaurant by ID: {e}")
        return None

def lambda_handler(event, context):
    try:
        body = json.loads(event['body'])
        print(body)
        restaurant_id = body.get('restaurantId')
        print(restaurant_id)
        if not restaurant_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'restaurantId is required.'})
            }

        restaurant_details = get_restaurant_by_id(restaurant_id)
        print(restaurant_details['coordinates'])
        coordinates = restaurant_details.get('coordinates')  # Assuming format [longitude, latitude]
        if coordinates:
            address = convert_coordinates_to_address(coordinates)
            restaurant_details['address'] = address
        if restaurant_details:
            return {
                'statusCode': 200,
                'body': json.dumps({'restaurantDetails': restaurant_details})
            }
        else:
            return {
                'statusCode': 404,
                'body': json.dumps({'message': 'Restaurant not found.'})
            }

    except Exception as e:
        print("Error in Lambda handler:", e)
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Internal server error', 'error': str(e)})
        }
