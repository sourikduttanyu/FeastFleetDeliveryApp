import json
import logging
import requests
import boto3
import os

# Initialize AWS clients
dynamodb = boto3.client('dynamodb')

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Environment variables for OpenSearch credentials and endpoint
username = os.getenv("OPENSEARCH_USERNAME")
password = os.getenv("OPENSEARCH_PASSWORD")
endpoint = os.getenv("OPENSEARCH_ENDPOINT")

def lambda_handler(event, context):
    """
    Main Lambda handler for Lex V2.
    This function determines which intent is triggered and routes the request to the appropriate handler.
    """
    
    # Extract the intent name from the event payload
    intent_name = event['sessionState']['intent']['name']
    session_attributes = event.get('sessionState', {}).get('sessionAttributes', {})

    # Route to the appropriate handler based on the intent
    if intent_name == "MainIntent":
        return handle_main_intent(event, session_attributes)
    elif intent_name == "OrderStartIntent":
        return handle_order_start_intent(event, session_attributes)
    elif intent_name == "GetRestaurantIntent":
        return handle_get_restaurant_intent(event, session_attributes)
    elif intent_name == "ConfirmOrderIntent":
        return handle_confirm_order_intent(event, session_attributes)
    else:
        return default_fallback_response(event, session_attributes)


def handle_main_intent(event, session_attributes):
    """
    Handler for MainIntent.
    Determines if the user wants to place an order and fetches nearby restaurants based on user coordinates.
    """
    invocation_source = event['invocationSource'] if 'invocationSource' in event else event.get('proposedNextState', {}).get('dialogAction', {}).get('type')
    service_type = event['sessionState']['intent']['slots']['ServiceType']['value']['interpretedValue']

    # Simulate fetching user_id from Cognito (in a real scenario, extract this from the event)
    user_id = "test123"

    if service_type.lower() == "order":
        # Fetch user's coordinates from DynamoDB
        try:
            response = dynamodb.get_item(
                TableName='User',  # Replace with your table name
                Key={'user_id': {'S': user_id}}
            )
        except Exception as e:
            logger.error(f"Error fetching user from DynamoDB: {e}")
            return {
                "sessionState": {
                    "sessionAttributes": session_attributes,
                    "intent": {
                        "name": "MainIntent",
                        "state": "Failed"
                    },
                    "dialogAction": {
                        "type": "Close",
                        "fulfillmentState": "Failed"
                    }
                },
                "messages": [
                    {"contentType": "PlainText", "content": "I couldn't retrieve your location. Please make sure your account is set up correctly."}
                ]
            }
        
        user_data = response.get('Item', {})
        if not user_data:
            logger.error(f"User data not found in DynamoDB for user_id: {user_id}")
            return {
                "sessionState": {
                    "sessionAttributes": session_attributes,
                    "intent": {
                        "name": "MainIntent",
                        "state": "Failed"
                    },
                    "dialogAction": {
                        "type": "Close",
                        "fulfillmentState": "Failed"
                    }
                },
                "messages": [
                    {"contentType": "PlainText", "content": "Your user information is incomplete. Please update your profile and try again."}
                ]
            }

        # Extract coordinates
        coordinates = user_data.get('coordinates', {}).get('M', {})
        lat = coordinates.get('lat', {}).get('N')
        lon = coordinates.get('lon', {}).get('N')

        if not lat or not lon:
            logger.error(f"Coordinates not found for user_id: {user_id}")
            return {
                "sessionState": {
                    "sessionAttributes": session_attributes,
                    "intent": {
                        "name": "MainIntent",
                        "state": "Failed"
                    },
                    "dialogAction": {
                        "type": "Close",
                        "fulfillmentState": "Failed"
                    }
                },
                "messages": [
                    {"contentType": "PlainText", "content": "Your location is missing. Please update your profile."}
                ]
            }
        
        # Log extracted coordinates
        logger.info(f"Extracted coordinates for user_id {user_id}: lat={lat}, lon={lon}")
        
        # Query OpenSearch for the nearest restaurants
        try:
            search_results = query_nearby_restaurants(float(lat), float(lon))
            if not search_results:
                logger.info(f"No nearby restaurants found for user_id {user_id} at coordinates ({lat}, {lon})")
                return {
                    "sessionState": {
                        "sessionAttributes": session_attributes,
                        "intent": {
                            "name": "MainIntent",
                            "state": "Failed"
                        },
                        "dialogAction": {
                            "type": "Close",
                            "fulfillmentState": "Failed"
                        }
                    },
                    "messages": [
                        {"contentType": "PlainText", "content": "No nearby restaurants found. Please try again later or verify your location."}
                    ]
                }

            # Store and format results
            session_attributes['NearbyRestaurants'] = json.dumps(search_results)
            restaurant_list = "\n".join(
                [f"{i+1}. {r['name']} ({r['distance']} km) - {r['cuisine']}" for i, r in enumerate(search_results)]
            )

            # Response structure for ReadyForFulfillment state
            return {
                "sessionState": {
                    "sessionAttributes": session_attributes,
                    "intent": {
                        "name": "MainIntent",
                        "state": "Fulfilled"
                    },
                    "dialogAction": {
                        "type": "Close"
                    }
                },
                "messages": [
                    {
                        "contentType": "PlainText",
                        "content": (
                            "I'll help you place an order. Based on your location, here are the 10 nearest restaurants:\n\n"
                            f"{restaurant_list}\n\n"
                            "Which restaurant would you like to order from?"
                        )
                    }
                ]
            }
        except Exception as e:
            logger.error(f"Error querying nearby restaurants for user_id {user_id}: {e}")
            return {
                "sessionState": {
                    "sessionAttributes": session_attributes,
                    "intent": {
                        "name": "MainIntent",
                        "state": "Failed"
                    },
                    "dialogAction": {
                        "type": "Close",
                        "fulfillmentState": "Failed"
                    }
                },
                "messages": [
                    {"contentType": "PlainText", "content": "Something went wrong while searching for restaurants. Please try again."}
                ]
            }

    elif service_type.lower() == "reservation":
        logger.info(f"User {user_id} requested a reservation.")
        return {
            "sessionState": {
                "sessionAttributes": session_attributes,
                "intent": {
                    "name": "MainIntent",
                    "state": "InProgress"
                },
                "dialogAction": {
                    "type": "Delegate"
                }
            },
            "messages": [
                {"contentType": "PlainText", "content": "I'll help you make a reservation. Let's proceed."}
            ]
        }

def query_nearby_restaurants(lat, lon):
    """
    Queries OpenSearch for restaurants near the provided coordinates.
    """
    search_body = {
        "size": 10,  # Limit to 10 results
        "query": {
            "geo_distance": {
                "distance": "5km",  # Adjust the radius as needed
                "coordinates": {"lat": lat, "lon": lon}
            }
        },
        "sort": [
            {
                "_geo_distance": {
                    "coordinates": {"lat": lat, "lon": lon},
                    "order": "asc",  # Closest first
                    "unit": "km"
                }
            }
        ]
    }

    try:
        response = requests.post(
            f"{endpoint}/restaurants_index/_search",
            auth=(username, password),
            headers={"Content-Type": "application/json"},
            json=search_body
        )
        if response.status_code == 200:
            search_data = response.json()
            results = [
                {
                    "name": hit['_source']['name'],
                    "cuisine": hit['_source']['cuisine'],
                    "distance": round(hit['sort'][0], 2)
                }
                for hit in search_data.get("hits", {}).get("hits", [])
            ]
            return results
        else:
            logger.error(f"OpenSearch query failed with status {response.status_code}: {response.text}")
            return []
    except Exception as e:
        logger.error(f"Error querying OpenSearch: {e}")
        return []