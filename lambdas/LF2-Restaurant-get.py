"""
LF2-Restaurant-get.py — AWS Lambda: Fetch Restaurant Details by ID

This Lambda function retrieves full details for a specific restaurant from
Amazon OpenSearch, then enriches the response by converting the stored
geographic coordinates into a human-readable address using the AWS Location
Service.

Data Flow:
    1. Parse the restaurantId from the API Gateway event body.
    2. Fetch the restaurant document from OpenSearch by its document ID.
    3. Pass the stored coordinates to AWS Location Service to reverse-geocode
       them into a formatted address string.
    4. Attach the resolved address to the restaurant details and return them.

AWS Services Used:
    - Amazon OpenSearch Service: Stores and serves restaurant documents indexed
      under 'restaurants_index'. Each document is retrieved directly by its _id.
    - AWS Location Service (location): Provides reverse geocoding via the
      SearchPlaceIndexForPosition API, converting [longitude, latitude] into
      a human-readable address label.
    - AWS Signature Version 4 (via requests_aws4auth): SigV4 credentials are
      constructed for IAM-based OpenSearch auth (the implementation currently
      uses HTTP Basic Auth for the OpenSearch calls).

Event Structure (expected input):
    {
        "body": "{\"restaurantId\": \"<OpenSearch document _id>\"}"
    }
    Note: 'body' is a JSON-encoded string, as provided by API Gateway.

Returns:
    - 200 with full restaurant details (including resolved address) on success
    - 400 if restaurantId is missing from the request
    - 404 if no restaurant with the given ID exists in OpenSearch
    - 500 for any unexpected errors
"""

import boto3
import json
import requests
from requests_aws4auth import AWS4Auth

# AWS region where both OpenSearch and the Location Service place index are deployed
region = 'us-east-1'

# Base URL for the OpenSearch 'restaurants_index'.
# Individual document retrieval appends '/_doc/<id>' to this URL.
opensearch_url = 'https://search-feastfleet-ylmv33u5rsoztak4q2xazv4x7u.us-east-1.es.amazonaws.com/restaurants_index'

# Build AWS SigV4 authentication credentials from the Lambda execution role.
# These are used for IAM-authenticated requests; the current implementation
# also uses Basic Auth directly for the OpenSearch HTTP calls.
service = "es"
session = boto3.Session()
credentials = session.get_credentials()

# Initialize the AWS Location Service client for reverse geocoding
location_client = boto3.client('location', region_name=region)

# Construct SigV4 auth object using temporary IAM credentials from the execution role
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    region,
    service,
    session_token=credentials.token  # Required for temporary credentials (e.g., from an IAM role)
)


def convert_coordinates_to_address(coordinates):
    """
    Reverse-geocode geographic coordinates into a human-readable address string
    using the AWS Location Service.

    The AWS Location Service's SearchPlaceIndexForPosition API takes a
    [longitude, latitude] position and returns the nearest matching place,
    including a formatted address label.

    Args:
        coordinates (dict | list | tuple): The restaurant's geographic location.
            Accepted formats:
                - dict: {'lon': <float>, 'lat': <float>}
                - list or tuple: [longitude, latitude]

    Returns:
        str | None: The formatted address label (e.g., "123 Main St, New York, NY")
                    if a result is found, or None if geocoding fails or returns
                    no results.
    """
    try:
        # Normalize the coordinate input into the [longitude, latitude] list format
        # expected by the AWS Location Service API
        if isinstance(coordinates, dict) and 'lon' in coordinates and 'lat' in coordinates:
            # Handle OpenSearch geo_point stored as a dict with 'lon' and 'lat' keys
            position = [coordinates['lon'], coordinates['lat']]
        elif isinstance(coordinates, (list, tuple)) and len(coordinates) == 2:
            # Handle coordinates already in [longitude, latitude] list/tuple format
            position = coordinates
        else:
            raise ValueError("Invalid coordinates format. Must be a dict with 'lon' and 'lat' keys, or a list/tuple.")

        # Call the AWS Location Service to reverse-geocode the position.
        # 'RestaurantPlaceIndex' is a pre-configured Place Index resource in AWS Location.
        response = location_client.search_place_index_for_position(
            IndexName='RestaurantPlaceIndex',  # Replace with your Place Index name
            Position=position  # [longitude, latitude] as expected by AWS Location
        )

        # Return the formatted address label from the first (most relevant) result
        if response['Results']:
            return response['Results'][0]['Place']['Label']  # Return formatted address
        else:
            return None

    except Exception as e:
        print(f"Error converting coordinates to address: {e}")
        return None


def get_restaurant_by_id(restaurant_id):
    """
    Retrieve a restaurant document from OpenSearch by its unique document ID.

    Uses the OpenSearch Document Get API (GET /<index>/_doc/<id>) to fetch the
    full source document for a restaurant. This is an O(1) lookup by ID,
    more efficient than a search query when the exact document ID is known.

    Args:
        restaurant_id (str): The OpenSearch document _id for the restaurant.

    Returns:
        dict | None: The '_source' object from the OpenSearch document (containing
                     all restaurant fields), or None if the document does not exist
                     or if an error occurs.
    """
    try:
        # Construct the direct document retrieval URL: /<index>/_doc/<id>
        url = f"{opensearch_url}/_doc/{restaurant_id}"

        # Fetch the document from OpenSearch using Basic Auth
        response = requests.get(url, auth=('admin', 'Cloudcomputing2024!!'), headers={"Content-Type": "application/json"})
        response_json = response.json()
        print(response_json)

        # OpenSearch wraps the document data under the '_source' key when found.
        # If the document does not exist, '_source' will be absent from the response.
        if "_source" in response_json:
            return response_json["_source"]
        else:
            return None

    except Exception as e:
        print(f"Error retrieving restaurant by ID: {e}")
        return None


def lambda_handler(event, context):
    """
    AWS Lambda entry point for fetching restaurant details.

    Parses the restaurantId from the API Gateway event, retrieves the restaurant
    document from OpenSearch, reverse-geocodes the stored coordinates into a
    human-readable address, and returns the enriched restaurant details.

    Args:
        event   (dict): Lambda event from API Gateway. The 'body' field is a
                        JSON-encoded string containing 'restaurantId'.
        context (obj):  Lambda context object (runtime metadata, unused here).

    Returns:
        dict: HTTP-style response with 'statusCode' and 'body'.
              200 with {'restaurantDetails': {...}} (including 'address') on success.
              400 if restaurantId is missing from the request body.
              404 if the restaurant is not found in OpenSearch.
              500 for any unexpected runtime errors.
    """
    try:
        # Parse the JSON-encoded body string provided by API Gateway
        body = json.loads(event['body'])
        print(body)

        restaurant_id = body.get('restaurantId')
        print(restaurant_id)

        # Validate that a restaurant ID was provided before making downstream calls
        if not restaurant_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'restaurantId is required.'})
            }

        # Fetch the full restaurant document from OpenSearch by document ID
        restaurant_details = get_restaurant_by_id(restaurant_id)
        print(restaurant_details['coordinates'])

        # If the restaurant has stored coordinates, reverse-geocode them into
        # a human-readable address and attach it to the response payload
        coordinates = restaurant_details.get('coordinates')  # Assuming format [longitude, latitude]
        if coordinates:
            address = convert_coordinates_to_address(coordinates)
            # Enrich the restaurant document with the resolved address string
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
