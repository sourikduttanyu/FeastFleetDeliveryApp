import json
import logging
import requests
import boto3
import os
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal
import uuid

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
lambda_client = boto3.client("lambda")

# DynamoDB table names
MENU_TABLE_NAME = 'Menu_Items'
CART_TABLE_NAME = 'Cart'

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
    elif intent_name == "OrderIntent":
        return handle_order_intent(event, session_attributes)
    else:
        return default_fallback_response(event, session_attributes)

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def handle_main_intent(event, session_attributes):
    """
    Handler for MainIntent.
    Determines if the user wants to place an order and fetches nearby restaurants based on user coordinates.
    """
    invocation_source = event['invocationSource'] if 'invocationSource' in event else event.get('proposedNextState', {}).get('dialogAction', {}).get('type')
    intent = event['sessionState']['intent']
    slots = intent['slots']
    proceed_order = (
        slots.get("ProceedOrder", {}).get("value", {}).get("interpretedValue")
        if slots.get("ProceedOrder") else None
    )

    # Simulate fetching user_id from Cognito (in a real scenario, extract this from the event)
    user_id = "test123"

    if not proceed_order:
        return {
            "sessionState": {
                "sessionAttributes": session_attributes,
                "dialogAction": {"type": "ElicitSlot", "slotToElicit": "ProceedOrder"},
                "intent": intent
            },
            "messages": [{"contentType": "PlainText", "content": "Would you like to proceed with placing an order?"}]
        }

    if proceed_order.lower() == "yes":
        # Fetch user's coordinates from DynamoDB
        try:
            user_table = dynamodb.Table('User')
            response = user_table.query(
                KeyConditionExpression=Key('user_id').eq(user_id)
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
        
        items = response.get('Items', [])
        if not items:
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
        
        user_data = items[0]
        logger.info(f"user_data retrieved: {json.dumps(user_data, indent=2, default=decimal_default)}")
        
        # Extract coordinates
        coordinates = user_data.get('coordinates', {})
        logger.info(f"Coordinates field: {json.dumps(coordinates, indent=2, default=decimal_default)}")

        lat = float(coordinates.get('lat', 0))
        lon = float(coordinates.get('lon', 0))
        logger.info(f"Latitude: {lat}, Longitude: {lon}")

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
                        "name": "OrderIntent",
                        "state": "InProgress",
                        "slots": {
                            "RestaurantName": None,
                            "ItemName": None,
                            "Quantity": None,
                            "AdditionalOrder": None,
                            "OrderConfirmation": None
                        }
                    },
                    "dialogAction": {
                        "type": "ElicitSlot",
                        "slotToElicit": "RestaurantName"
                    }
                },
                "messages": [
                    {
                        "contentType": "PlainText",
                        "content": (
                            "I'll help you place an order. Based on your location, here are the 10 nearest restaurants:\n\n"
                            f"{restaurant_list}.\n\n"
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
    elif proceed_order.lower() == "no":
        # End the conversation gracefully
        return {
            "sessionState": {
                "sessionAttributes": session_attributes,
                "dialogAction": {"type": "Close"},
                "intent": intent
            },
            "messages": [{"contentType": "PlainText", "content": "Alright, let me know if you'd like to place an order later. Have a great day!"}]
        }

    # Default fallback for unexpected values
    return {
        "sessionState": {
            "sessionAttributes": session_attributes,
            "dialogAction": {"type": "Close"},
            "intent": intent
        },
        "messages": [{"contentType": "PlainText", "content": "I didn't quite understand your response. Please try again later."}]
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

def decimal_to_float(obj):
    """
    Recursively convert DynamoDB Decimal types to float.
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
    Query DynamoDB Menu_Items table for menu items by restaurant_name.
    """
    table = dynamodb.Table(MENU_TABLE_NAME)
    try:
        response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('restaurant_id').eq(restaurant_id)
        )
        return decimal_to_float(response.get('Items', []))
    except Exception as e:
        logger.error(f"Error retrieving menu from DynamoDB: {e}")
        return []

def update_cart(user_id, restaurant_id, item_name, quantity, price):
    """
    Add an item to the user's cart in the Cart table.
    """
    table = dynamodb.Table(CART_TABLE_NAME)
    try:
        # Calculate total price for the item
        total_price = Decimal(str(quantity)) * Decimal(str(price))

        # Insert or update the cart
        table.put_item(
            Item={
                'user_id': user_id,
                'restaurant_id': restaurant_id,
                'item_list': [{
                    'item_name': item_name,
                    'item_quantity': Decimal(str(quantity)),
                    'item_price': Decimal(str(price))
                }],
                'total_price': total_price
            }
        )
        return True
    except Exception as e:
        logger.error(f"Error updating cart in DynamoDB: {e}")
        return False

def get_restaurant_id_by_name(restaurant_name):
    """
    Query the DynamoDB Restaurant table for the restaurant_id by comparing normalized names.
    """
    try:
        # Access the DynamoDB Restaurant table
        restaurant_table = dynamodb.Table("Restaurant")

        # Scan the table to find a matching restaurant name
        response = restaurant_table.scan()
        items = response.get("Items", [])

        # Iterate through items and find a match
        for item in items:
            db_name = item.get("name", "").strip().lower()  # Normalize DB name for comparison
            if db_name == restaurant_name.strip().lower():  # Normalize input name for comparison
                return item.get("restaurant_id")  # Return the matched restaurant_id

        # No match found
        logger.warning(f"No restaurant found with the name: {restaurant_name}")
        return None
    except Exception as e:
        logger.error(f"Error querying restaurant_id for {restaurant_name}: {e}")
        return None

def initialize_cart(user_id):
    try:
        cart_table = dynamodb.Table("Cart")
        
        # Query the Cart table for the user's cart
        response = cart_table.get_item(Key={"user_id": user_id})
        
        # If cart exists, return it
        if "Item" in response:
            logger.info(f"Cart found for user {user_id}.")
            return response["Item"].get("cart", [])
        
        # If cart doesn't exist, initialize it
        logger.info(f"No cart found for user {user_id}. Initializing a new cart.")
        cart_table.put_item(
            Item={
                "user_id": user_id,
                "cart": []  # Start with an empty cart
            }
        )
        return []  # Return an empty cart
    except Exception as e:
        logger.error(f"Error initializing cart for user {user_id}: {e}")
        return []  # Return an empty cart as a fallback

def handle_order_intent(event, session_attributes):
    """
    Handles the order intent by retrieving the menu, collecting item and quantity, and updating the cart.
    """
    intent = event['sessionState']['intent']
    slots = intent['slots']
    user_id = "test123"  # Replace with actual user ID retrieval logic

    # Safely retrieve slot values
    restaurant_name = (
        slots.get("RestaurantName", {}).get("value", {}).get("originalValue")
        if slots.get("RestaurantName") else None
    )
    item_name = (
        slots.get("ItemName", {}).get("value", {}).get("originalValue")
        if slots.get("ItemName") else None
    )
    quantity = (
        slots.get("Quantity", {}).get("value", {}).get("interpretedValue")
        if slots.get("Quantity") else None
    )
    additional_order = (
        slots.get("AdditionalOrder", {}).get("value", {}).get("interpretedValue")
        if slots.get("AdditionalOrder") else None
    )
    order_confirmation = (
        slots.get("OrderConfirmation", {}).get("value", {}).get("interpretedValue")
        if slots.get("OrderConfirmation") else None
    )

    # Step 1: Retrieve and store restaurant ID
    if not restaurant_name:
        return {
            "sessionState": {
                "dialogAction": {"type": "ElicitSlot", "slotToElicit": "RestaurantName"},
                "intent": intent
            },
            "messages": [{"contentType": "PlainText", "content": "Which restaurant would you like to order from?"}]
        }
    
    # Initialize the cart if it does not exist in session attributes
    if "cart" not in session_attributes:
        session_attributes["cart"] = json.dumps([])  # Initialize an empty cart in session attributes
        try:
            cart_table = dynamodb.Table("Cart")
            response = cart_table.get_item(Key={"user_id": user_id})
            if "Item" in response:
                session_attributes["cart"] = json.dumps(response["Item"]["cart"])  # Load the cart from the database
                logger.info(f"Cart loaded from database for user {user_id}.")
            else:
                # Initialize a new cart in DynamoDB
                cart_table.put_item(
                    Item={
                        "user_id": user_id,
                        "cart": []  # Save an empty cart in DynamoDB
                    }
                )
                logger.info(f"Initialized a new cart for user {user_id} in DynamoDB.")
        except Exception as e:
            logger.error(f"Error initializing cart for user {user_id}: {e}")


    restaurant_id = session_attributes.get("restaurant_id")
    if "restaurant_id" not in session_attributes:
        restaurant_id = get_restaurant_id_by_name(restaurant_name)  # Fetch restaurant ID based on name
        if not restaurant_id:
            return {
                "sessionState": {
                    "dialogAction": {"type": "Close"},
                    "intent": intent
                },
                "messages": [{"contentType": "PlainText", "content": "I couldn't find the restaurant. Please try again."}]
            }
        session_attributes["restaurant_id"] = restaurant_id

    # Step 2: Retrieve menu and prompt for item name
    if not item_name:
        # Check if user is already being asked for the item name
        if session_attributes.get("waiting_for_item_name") == "true":
            return {
                "sessionState": {
                    "sessionAttributes": session_attributes,
                    "dialogAction": {"type": "ElicitSlot", "slotToElicit": "ItemName"},
                    "intent": intent
                },
                "messages": [{"contentType": "PlainText", "content": "Please choose an item from the menu."}]
            }

        # Set flag to track that we are eliciting the item name
        session_attributes["waiting_for_item_name"] = "true"

        # Ensure restaurant_id exists
        if not restaurant_id:
            logger.error("Restaurant ID is missing while trying to retrieve the menu.")
            return {
                "sessionState": {
                    "sessionAttributes": session_attributes,
                    "dialogAction": {"type": "ElicitSlot", "slotToElicit": "RestaurantName"},
                    "intent": intent
                },
                "messages": [{"contentType": "PlainText", "content": "It seems I lost the restaurant information. Could you tell me the name of the restaurant again?"}]
            }

        # Retrieve menu for the given restaurant
        menu = get_menu_by_restaurant_id(restaurant_id)
        if not menu:
            return {
                "sessionState": {
                    "sessionAttributes": session_attributes,
                    "dialogAction": {"type": "Close"},
                    "intent": intent
                },
                "messages": [{"contentType": "PlainText", "content": "I couldn't find the menu for this restaurant. Please try another one."}]
            }

        # Format and store the menu
        menu_list = "\n".join([f"{i+1}. {item['item_name']} - ${item['price']:.2f}" for i, item in enumerate(menu)])
        session_attributes["menu"] = json.dumps(menu)
        return {
            "sessionState": {
                "sessionAttributes": session_attributes,
                "dialogAction": {"type": "ElicitSlot", "slotToElicit": "ItemName"},
                "intent": intent
            },
            "messages": [{"contentType": "PlainText", "content": f"Great Choice! Here's the menu from the restaurant:\n{menu_list}\nWhat would you like to order?"}]
        }
    else:
        # Reset flag after item name is provided
        session_attributes.pop("waiting_for_item_name", None)

    # Step 3: Ask for quantity
    if not quantity:
        return {
            "sessionState": {
                "sessionAttributes": session_attributes,
                "dialogAction": {"type": "ElicitSlot", "slotToElicit": "Quantity"},
                "intent": intent
            },
            "messages": [{"contentType": "PlainText", "content": f"How many {item_name} would you like to order?"}]
        }

    # Fetch the menu from session attributes
    menu = json.loads(session_attributes.get("menu", "[]"))
    item = next((menu_item for menu_item in menu if menu_item["item_name"].lower() == item_name.lower()), None)

    if not item:
        logger.error(f"Item with name '{item_name}' not found in the menu.")
        return {
            "sessionState": {
                "dialogAction": {"type": "ElicitSlot", "slotToElicit": "ItemName"},
                "intent": intent
            },
            "messages": [{"contentType": "PlainText", "content": f"I couldn't find {item_name} in the menu. Please try again."}]
        }

    # Fetch or initialize the cart from session attributes
    cart = json.loads(session_attributes.get("cart", "[]"))

    # Check if the item already exists in the cart
    existing_item = next((cart_item for cart_item in cart if cart_item["item_id"] == item["item_id"]), None)
    if existing_item:
        # Update quantity only once if the item already exists
        existing_item["quantity"] = int(quantity)
        logger.info(f"Updated quantity for item: {existing_item['item_name']}. New quantity: {existing_item['quantity']}")
    else:
        # Add new item to the cart
        new_item = {
            "item_id": item["item_id"],
            "item_name": item["item_name"],
            "quantity": int(quantity),
            "price": float(item["price"])
        }
        cart.append(new_item)
        logger.info(f"Added new item to the cart: {new_item['item_name']} (Quantity: {new_item['quantity']})")

    # Save the updated cart to session attributes
    session_attributes["cart"] = json.dumps(cart)

    # Save the updated cart to DynamoDB only when confirmed and after modifying the cart
    try:
        cart_table = dynamodb.Table("Cart")
        cart_table.put_item(
            Item={
                "user_id": user_id,
                "cart": decimal_to_float(cart)  # Save the updated cart
            }
        )
        logger.info(f"Updated cart saved for user {user_id}.")
    except Exception as e:
        logger.error(f"Error saving updated cart to DynamoDB for user {user_id}: {e}")

    # Step 5: Check for additional orders
    if not additional_order:
        return {
            "sessionState": {
                "sessionAttributes": session_attributes,
                "dialogAction": {"type": "ElicitSlot", "slotToElicit": "AdditionalOrder"},
                "intent": intent
            },
            "messages": [{"contentType": "PlainText", "content": f"Added {quantity}x {item_name} to your cart. Would you like anything else?"}]
        }
    elif additional_order.lower() == "yes":
        # Reset slots for the next item
        slots["ItemName"] = None
        slots["Quantity"] = None
        slots["AdditionalOrder"] = None
        return {
            "sessionState": {
                "sessionAttributes": session_attributes,
                "dialogAction": {"type": "ElicitSlot", "slotToElicit": "ItemName"},
                "intent": intent
            },
            "messages": [{"contentType": "PlainText", "content": "What else would you like to order?"}]
        }

    # Step 6: Confirm the order
    if not order_confirmation:
        # Summarize cart content (use the session-stored cart to avoid doubling quantities)
        total_items = "\n".join([f"{i+1}. {item['quantity']}x {item['item_name']} - ${item['price'] * item['quantity']:.2f}" for i, item in enumerate(cart)])
        total_price = sum(item["price"] * item["quantity"] for item in cart)
        session_attributes["total_price"] = total_price
        return {
            "sessionState": {
                "sessionAttributes": session_attributes,
                "dialogAction": {"type": "ElicitSlot", "slotToElicit": "OrderConfirmation"},
                "intent": intent
            },
            "messages": [{"contentType": "PlainText", "content": f"Here's your order summary:\n{total_items}\nTotal: ${total_price:.2f}\nWould you like to place this order?"}]
        }

    # Step 7: Place the order
    if order_confirmation.lower() == "yes":
        restaurant_id = session_attributes["restaurant_id"]
        items = [{"item_id": item["item_id"], "quantity": item["quantity"]} for item in cart]
        total_price = session_attributes["total_price"]

        # Generate a unique order ID
        order_id = str(uuid.uuid4())

        # Format payload for LF7-place-order
        order_payload = {
            "body": json.dumps({  # Ensure 'body' is a serialized JSON string
                "order_id": order_id,
                "restaurant_id": restaurant_id,
                "items": items,
                "total_price": total_price
            }),
            "requestContext": {
                "authorizer": {
                    "claims": {
                        "sub": user_id  # Include user_id in the requestContext
                    }
                }
            }
        }

        try:
            # Invoke LF7-place-order Lambda function
            response = lambda_client.invoke(
                FunctionName="arn:aws:lambda:us-east-1:699475942485:function:LF7-place-order",  # Your actual Lambda ARN
                InvocationType="RequestResponse",  # Synchronous invocation to get a response
                Payload=json.dumps(order_payload)  # Send the payload as JSON
            )

            # Parse the response from LF7
            response_payload = json.loads(response["Payload"].read())
            if response.get("StatusCode") == 200:
                estimated_delivery_time = response_payload.get("estimated_delivery_time", "unspecified")

                # Clear the cart after placing the order
                try:
                    cart_table = dynamodb.Table("Cart")
                    cart_table.put_item(
                        Item={
                            "user_id": user_id,
                            "cart": []  # Save an empty cart to clear it in DynamoDB
                        }
                    )
                    logger.info(f"Cart cleared for user {user_id} after placing the order.")
                except Exception as e:
                    logger.error(f"Error clearing cart for user {user_id}: {e}")

                session_attributes["cart"] = json.dumps([])  # Clear the session cart

                return {
                    "sessionState": {
                        "dialogAction": {"type": "Close"},
                        "intent": intent
                    },
                    "messages": [{"contentType": "PlainText", "content": f"Your order has been placed successfully! Order ID: {order_id}. You can check the order status in the App."}]
                }
            else:
                logger.error(f"Error from LF7: {response_payload}")
                return {
                    "sessionState": {
                        "dialogAction": {"type": "Close"},
                        "intent": intent
                    },
                    "messages": [{"contentType": "PlainText", "content": "There was an issue placing your order. Please try again later."}]
                }
        except Exception as e:
            logger.error(f"Error invoking LF7 Lambda function: {e}")
            return {
                "sessionState": {
                    "dialogAction": {"type": "Close"},
                    "intent": intent
                },
                "messages": [{"contentType": "PlainText", "content": "There was an issue placing your order. Please try again later."}]
            }

    # Handle order cancellation
    elif order_confirmation.lower() == "no":
        return {
            "sessionState": {
                "dialogAction": {"type": "Close"},
                "intent": intent
            },
            "messages": [{"contentType": "PlainText", "content": "Your order has been canceled. Let me know if you'd like to start again."}]
        }

    # Default fallback response
    return {
        "sessionState": {
            "dialogAction": {"type": "Close"},
            "intent": intent
        },
        "messages": [{"contentType": "PlainText", "content": "Something went wrong. Please try again later."}]
    }