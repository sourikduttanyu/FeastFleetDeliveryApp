"""
LF8 - Process Order Lambda
---------------------------
Purpose:
    Consumes order status change events from an SQS queue (Q1) and orchestrates
    all downstream side-effects: updating the Order table, writing/updating delivery
    tracking records, and notifying the customer via email.

    This Lambda sits at the heart of the order processing pipeline. Whenever an order
    moves through a status transition (e.g., PLACED -> OUT_FOR_DELIVERY -> DELIVERED),
    a message is pushed to Q1 and this function handles the resulting state changes.

AWS Integrations:
    - SQS (Q1):              Event source trigger; each SQS record represents one order
                             status change event.
    - DynamoDB (Order):      Updated with the new order status and timestamp on every message.
    - DynamoDB (Delivery_Tracking): Created when status becomes OUT_FOR_DELIVERY;
                             updated when status becomes DELIVERED.
    - DynamoDB (Restaurant): Queried to retrieve the restaurant's geographic coordinates,
                             used as the delivery origin.
    - DynamoDB (User):       Queried to retrieve the customer's coordinates (delivery
                             destination) and their email address.
    - SES:                   Sends a transactional email to the customer whenever their
                             order status changes.

Event Structure (SQS Records):
    Each record in event['Records'] has a 'body' field containing a JSON string:
    {
        "order_id": "uuid",
        "user_id": "cognito-sub",
        "restaurant_id": "rest-uuid",
        "status": "OUT_FOR_DELIVERY",   # e.g., PLACED, OUT_FOR_DELIVERY, DELIVERED
        "timestamp": "2024-01-01T12:00:00"
    }

Returns:
    dict with a success message after all records are processed.
    Raises an exception for any individual record that fails, which causes SQS to
    retry that message (or send it to a Dead Letter Queue if configured).
"""

import boto3
import json
from botocore.exceptions import ClientError
from decimal import Decimal

# DynamoDB resource — explicitly targeting us-east-1 where the tables are deployed
dynamodb = boto3.resource('dynamodb', region_name="us-east-1")

# SES client for sending transactional email notifications to customers
ses = boto3.client('ses', region_name="us-east-1")

# DynamoDB table name constants — centralised to make table renames easy
ORDER_TABLE = "Order"
DELIVERY_TRACKING_TABLE = "Delivery_Tracking"
USER_TABLE = "User"
RESTAURANT_TABLE = "Restaurant"

# The verified SES sender address. Must be verified in SES before emails can be sent.
SENDER_EMAIL = ""

# Instantiate DynamoDB Table objects for each table used by this Lambda
order_table = dynamodb.Table(ORDER_TABLE)
delivery_tracking_table = dynamodb.Table(DELIVERY_TRACKING_TABLE)
user_table = dynamodb.Table(USER_TABLE)
restaurant_table = dynamodb.Table(RESTAURANT_TABLE)


def lambda_handler(event, context):
    """
    Main entry point for the Process Order Lambda.

    Iterates over each SQS record in the batch, parses the order status change message,
    and coordinates updates to DynamoDB tables and email notifications. If processing
    any single record raises an exception, it is re-raised so that SQS can handle
    the failure (retry or DLQ).

    Args:
        event (dict): SQS event containing a list of records under 'Records'.
        context (LambdaContext): AWS Lambda context object (unused here).

    Returns:
        dict: A message indicating all records were successfully processed.
    """
    for record in event['Records']:
        try:
            # Parse the message from SQS — the body is a JSON-encoded string
            message = json.loads(record['body'])
            order_id = message['order_id']
            user_id = message['user_id']
            restaurant_id = message['restaurant_id']
            new_status = message['status']
            timestamp = message['timestamp']

            print(f"Processing order {order_id}: New status {new_status}")

            # Always update the Order table with the latest status and timestamp
            update_order_status(order_id, new_status, timestamp)

            # Delivery tracking is only relevant once the order is out for delivery
            # or has been delivered — no entry is created for earlier statuses
            if new_status in ["OUT_FOR_DELIVERY", "DELIVERED"]:
                update_delivery_status(order_id, user_id, restaurant_id, new_status, timestamp)

            # Look up the customer's email to send a notification
            user_email = get_user_email(user_id)
            if not user_email:
                # If no email is on record, skip notification and move on
                print(f"No email found for user {user_id}. Skipping notification.")
                continue

            # Send the status-change email to the customer via SES
            send_email_notification(order_id, new_status, user_email)

        except Exception as e:
            # Log the error and re-raise so that SQS treats this record as failed.
            # This enables SQS's built-in retry mechanism and DLQ routing.
            print(f"Error processing message: {str(e)}")
            raise e

    return {"message": "Successfully processed messages from SQS"}


# Function to update the Order Table
def update_order_status(order_id, new_status, timestamp):
    """
    Updates the 'status' and 'timestamp' fields of an existing order in the Order table.

    Uses ExpressionAttributeNames to safely alias the reserved DynamoDB keyword 'status'
    and the field 'timestamp', avoiding potential expression parsing errors.

    Args:
        order_id (str):   The partition key identifying the order to update.
        new_status (str): The new order status string (e.g., 'OUT_FOR_DELIVERY').
        timestamp (str):  ISO 8601 timestamp string marking when the status changed.

    Raises:
        ClientError: If the DynamoDB update operation fails.
    """
    try:
        order_table.update_item(
            Key={"order_id": order_id},
            # '#s' and '#ts' are expression name aliases required because 'status'
            # and 'timestamp' are reserved words in DynamoDB's expression language
            UpdateExpression="SET #s = :new_status, #ts = :timestamp",
            ExpressionAttributeNames={"#s": "status", "#ts": "timestamp"},
            ExpressionAttributeValues={":new_status": new_status, ":timestamp": timestamp}
        )
        print(f"Order {order_id} status updated to {new_status}")
    except ClientError as e:
        print(f"Error updating order status for {order_id}: {e.response['Error']['Message']}")
        raise


# Function to update the Delivery Tracking Table
def update_delivery_status(order_id, user_id, restaurant_id, new_status, timestamp):
    """
    Manages delivery tracking records in the Delivery_Tracking table.

    Behaviour differs based on the status:
    - OUT_FOR_DELIVERY: Creates (or upserts) a new tracking entry, setting the restaurant's
      coordinates as the initial 'current_location' and the user's coordinates as
      the 'destination'. ETA is set to 'Unknown' as a placeholder.
    - DELIVERED: Updates the existing tracking record to mark it as delivered.

    Args:
        order_id (str):      The order being tracked (partition key in Delivery_Tracking).
        user_id (str):       The customer's user ID, used to fetch delivery destination.
        restaurant_id (str): The restaurant's ID, used to fetch the delivery origin.
        new_status (str):    Either 'OUT_FOR_DELIVERY' or 'DELIVERED'.
        timestamp (str):     ISO 8601 timestamp of the status change.

    Raises:
        Exception: Propagates any DynamoDB or coordinate-fetch errors to the caller.
    """
    try:
        if new_status == "OUT_FOR_DELIVERY":
            # Fetch restaurant coordinates to use as the starting point of delivery
            restaurant_coordinates = get_restaurant_coordinates(restaurant_id)
            if not restaurant_coordinates:
                print(f"Failed to fetch coordinates for restaurant {restaurant_id}")
                return

            # Fetch user coordinates to use as the delivery destination
            user_coordinates = get_user_coordinates(user_id)
            if not user_coordinates:
                print(f"Failed to fetch coordinates for user {user_id}")
                return

            # Upsert a delivery tracking entry — uses update_item so if the record
            # already exists (e.g., a duplicate event), it is safely overwritten
            delivery_tracking_table.update_item(
                Key={"order_id": order_id},
                UpdateExpression="""
                    SET order_status = :status,
                        user_id = :user,
                        restaurant_id = :restaurant,
                        current_location = :location,
                        destination = :destination,
                        eta = :eta,
                        last_updated = :timestamp
                """,
                ExpressionAttributeValues={
                    ":status": new_status,
                    ":user": user_id,
                    ":restaurant": restaurant_id,
                    ":location": restaurant_coordinates,  # Use restaurant coordinates as the initial location
                    ":destination": user_coordinates,  # User's address as the destination
                    ":eta": "Unknown",  # Placeholder for ETA
                    ":timestamp": timestamp
                }
            )
            print(f"New delivery entry created for order {order_id} with status {new_status}")

        elif new_status == "DELIVERED":
            # Only the status and last_updated fields need to change on final delivery
            delivery_tracking_table.update_item(
                Key={"order_id": order_id},
                UpdateExpression="SET order_status = :status, last_updated = :timestamp",
                ExpressionAttributeValues={":status": "DELIVERED", ":timestamp": timestamp}
            )
            print(f"Delivery tracking for {order_id} updated to {new_status}")

    except Exception as e:
        print(f"Error updating delivery tracking for {order_id}: {str(e)}")
        raise


# Function to retrieve restaurant coordinates from the Restaurant Table
def get_restaurant_coordinates(restaurant_id):
    """
    Fetches the geographic coordinates of a restaurant from the Restaurant table.

    The 'coordinates' field is expected to be stored on the restaurant's DynamoDB
    item (e.g., as a map with lat/lng) and is used as the initial delivery location.

    Args:
        restaurant_id (str): The restaurant's partition key.

    Returns:
        The coordinates value (e.g., a map) if found, or None if the restaurant
        does not exist or has no coordinates attribute.

    Raises:
        ClientError: If the DynamoDB get_item call fails.
    """
    try:
        response = restaurant_table.get_item(Key={"restaurant_id": restaurant_id})
        if "Item" in response:
            return response["Item"].get("coordinates")
        return None
    except ClientError as e:
        print(f"Error retrieving coordinates for restaurant {restaurant_id}: {e.response['Error']['Message']}")
        raise


# Function to retrieve user coordinates from the User Table
def get_user_coordinates(user_id):
    """
    Fetches the geographic coordinates of a user (their delivery address) from the User table.

    The 'coordinates' field represents the user's saved delivery location and is
    stored as the delivery destination in the Delivery_Tracking table.

    Args:
        user_id (str): The user's partition key (Cognito 'sub').

    Returns:
        The coordinates value if found, or None if the user does not exist or
        has no coordinates attribute.

    Raises:
        ClientError: If the DynamoDB get_item call fails.
    """
    try:
        response = user_table.get_item(Key={"user_id": user_id})
        if "Item" in response:
            return response["Item"].get("coordinates")
        return None
    except ClientError as e:
        print(f"Error retrieving coordinates for user {user_id}: {e.response['Error']['Message']}")
        raise


# Function to retrieve user email from User Table
def get_user_email(user_id):
    """
    Fetches the email address associated with a user from the User table.

    This email is used as the destination address for SES notifications.

    Args:
        user_id (str): The user's partition key (Cognito 'sub').

    Returns:
        str: The user's email address if found, or None if not present.

    Raises:
        ClientError: If the DynamoDB get_item call fails.
    """
    try:
        response = user_table.get_item(Key={"user_id": user_id})
        if "Item" in response:
            return response["Item"].get("email")
        return None
    except ClientError as e:
        print(f"Error retrieving email for user {user_id}: {e.response['Error']['Message']}")
        raise


# Function to send email notification
def send_email_notification(order_id, new_status, user_email):
    """
    Sends a transactional order status update email to the customer using Amazon SES.

    The email is sent as plain text. The SENDER_EMAIL must be a verified identity
    in SES (either a verified email address or a verified domain). If SES is still
    in sandbox mode, the recipient email must also be verified.

    Args:
        order_id (str):   The order ID referenced in the email body.
        new_status (str): The new order status displayed in the subject and body.
        user_email (str): The recipient's email address.

    Raises:
        ClientError: If the SES send_email call fails (e.g., unverified sender,
                     SES sandbox restrictions, or sending limits exceeded).
    """
    subject = f"Order Status Update: {new_status}"
    body = f"""
    Hello,

    Your order with ID {order_id} has been updated to the following status: **{new_status}**.

    Thank you for using our service!

    Best regards,
    FeastFleet Team
    """
    try:
        # SES send_email requires Source to be a verified identity in the AWS account.
        # Destination.ToAddresses accepts a list, supporting multiple recipients if needed.
        ses.send_email(
            Source=SENDER_EMAIL,
            Destination={"ToAddresses": [user_email]},
            Message={
                "Subject": {"Data": subject},
                "Body": {
                    # Sending as plain text ('Text'); an 'Html' key could be added
                    # here to also send an HTML-formatted version of the email
                    "Text": {"Data": body}
                }
            }
        )
        print(f"Email sent to {user_email} for order {order_id} with status {new_status}")
    except ClientError as e:
        print(f"Error sending email to {user_email}: {e.response['Error']['Message']}")
        raise
