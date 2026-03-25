"""
LF1-Restaurant-search.py — AWS Lambda: Restaurant Search via OpenSearch

This Lambda function enables restaurant discovery for the FeastFleet delivery
application. It accepts a search query and a query type, then performs a
full-text search against an Amazon OpenSearch Service index to return matching
restaurant IDs.

Two search modes are supported:
    - "name":        Full-text match on the restaurant's name field.
    - "cuisineType": Full-text match on the restaurant's cuisine field.

AWS Services Used:
    - Amazon OpenSearch Service (formerly Elasticsearch): Hosts the
      'restaurants_index' index and handles full-text search queries.
    - AWS Signature Version 4 (via requests_aws4auth): Signs HTTP requests
      to OpenSearch for IAM-based authentication (constructed but the actual
      requests use HTTP Basic Auth in the current implementation).

Event Structure (expected input):
    {
        "body": "{\"type\": \"name\" | \"cuisineType\", \"query\": \"<search term>\"}"
    }
    Note: 'body' is a JSON-encoded string, as provided by API Gateway.

Returns:
    - 200 with a list of matching restaurant IDs on success
    - 400 if the query type is not recognized
    - 500 for any unexpected errors during the search
"""

import boto3
import json
import logging
import requests
from requests_aws4auth import AWS4Auth
from requests.auth import HTTPBasicAuth
from botocore.exceptions import ClientError

# AWS region where the OpenSearch domain is deployed
region = 'us-east-1'

# Full URL for the OpenSearch search endpoint targeting the restaurants index
opensearch_url = 'https://search-feastfleet-ylmv33u5rsoztak4q2xazv4x7u.us-east-1.es.amazonaws.com/restaurants_index/_search'

# Build AWS SigV4 credentials for OpenSearch authentication.
# These are derived from the Lambda execution role at runtime,
# so no hardcoded AWS keys are needed for IAM-based auth.
session = boto3.Session()
credentials = session.get_credentials()
service = "es"
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    region,
    service,
    session_token=credentials.token  # Required when using temporary IAM credentials
)


def get_restaurant_by_name(name):
    """
    Search OpenSearch for restaurants whose name matches the given query string.

    Uses an OpenSearch 'match' query, which performs full-text analysis including
    tokenization, stemming, and relevance scoring. Returns up to 10 results.

    Args:
        name (str): The restaurant name (or partial name) to search for.

    Returns:
        list[str]: A list of OpenSearch document IDs (_id) for matching restaurants.
                   Returns an empty list if the query fails or no results are found.
    """
    # Build the OpenSearch DSL (Domain-Specific Language) query.
    # 'match' performs analyzed full-text search, scoring results by relevance.
    query = {
        "size": 10,  # Limit results to top 10 matches
        "query": {
            "match": {
                "name": name,  # Match against the 'name' field in the index
            }
        }
    }

    headers = {"Content-Type": "application/json"}
    try:
        # Send the search query to OpenSearch using HTTP Basic Auth.
        # Note: awsauth (SigV4) is constructed above but Basic Auth is used here
        # as the OpenSearch domain has fine-grained access control with a master user.
        response = requests.get(
            opensearch_url,
            auth=('admin', 'Cloudcomputing2024!!'),
            headers=headers,
            json=query
        )
        response_json = response.json()
        print(response_json)

        # Extract the document IDs from the search hits.
        # Each '_id' maps to a restaurant's unique identifier in the index.
        restaurant_ids = [hit["_id"] for hit in response_json["hits"]["hits"]]
        return restaurant_ids
    except Exception as e:
        print("Error querying OpenSearch:", e)
        return []


def get_restaurant_recommendations(cuisine_type):
    """
    Search OpenSearch for restaurants that serve the specified cuisine type.

    Uses an OpenSearch 'match' query on the 'cuisine' field to find restaurants
    whose cuisine type matches the provided string. Returns up to 10 results.

    Args:
        cuisine_type (str): The cuisine type to search for (e.g., "Italian", "Chinese").

    Returns:
        list[str]: A list of OpenSearch document IDs (_id) for matching restaurants.
                   Returns an empty list if the query fails or no results are found.
    """
    # Build the OpenSearch DSL query targeting the 'cuisine' field.
    # 'match' allows partial and analyzed matches (e.g., "italian" matches "Italian").
    query = {
        "size": 10,  # Limit results to top 10 matches
        "query": {
            "match": {
                "cuisine": cuisine_type  # Match against the 'cuisine' field in the index
            }
        }
    }

    headers = {"Content-Type": "application/json"}

    try:
        # Send the cuisine-based search query to OpenSearch
        response = requests.get(
            opensearch_url,
            auth=('admin', 'Cloudcomputing2024!!'),
            headers=headers,
            json=query
        )
        response_json = response.json()
        print(response_json)

        # Extract the document IDs (_id) from the OpenSearch hits array
        restaurant_ids = [hit["_id"] for hit in response_json["hits"]["hits"]]
        return restaurant_ids
    except Exception as e:
        print("Error querying OpenSearch:", e)
        return []


def lambda_handler(event, context):
    """
    AWS Lambda entry point for restaurant search.

    Parses the incoming API Gateway event body to determine the search type
    ('name' or 'cuisineType') and delegates to the appropriate OpenSearch
    query function. Returns the list of matching restaurant IDs to the caller.

    Args:
        event   (dict): Lambda event from API Gateway. The 'body' field is a
                        JSON-encoded string containing 'type' and 'query'.
        context (obj):  Lambda context object (runtime metadata, unused here).

    Returns:
        dict: HTTP-style response with 'statusCode' and 'body'.
              200 with {'restaurantIds': [...]} on a successful search.
              400 if the query type is not 'name' or 'cuisineType'.
              500 for any unexpected runtime errors.
    """
    try:
        # API Gateway wraps the request payload as a JSON string in event['body'];
        # parse it back into a dictionary to access the search parameters
        body = json.loads(event['body'])
        query_type = body.get('type')   # Determines which search strategy to use
        query = body.get('query')       # The actual search term provided by the user

        restaurant_ids = []

        # Route the search request to the appropriate OpenSearch query function
        # based on the query type supplied by the client
        if query_type == "name":
            # Search by restaurant name using full-text match
            restaurant_ids = get_restaurant_by_name(query)
        elif query_type == "cuisineType":
            # Search by cuisine type using full-text match
            restaurant_ids = get_restaurant_recommendations(query)
        else:
            # Reject any unrecognized query type with a descriptive 400 error
            return {
                "statusCode": 400,
                "body": "Invalid query type"
            }

        # Return the list of matching restaurant IDs as a JSON-encoded response body
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
