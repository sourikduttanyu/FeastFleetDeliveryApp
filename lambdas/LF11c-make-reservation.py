"""
LF11c - Make Reservation Lambda
----------------------------------
Purpose:
    Consumes reservation requests from SQS queue Q2 and fulfils them atomically.
    For each message this Lambda:
      1. Fetches the restaurant's current seating capacity.
      2. Fetches all existing reservations for the same restaurant and date (via GSI).
      3. Checks whether the requested time slot has sufficient remaining capacity,
         accounting for a 1-hour overlap window.
      4. If available, writes a new reservation record to DynamoDB with a conditional
         expression to prevent duplicate reservations (idempotent write).
      5. Sends a confirmation or failure email to the user via Amazon SES.

    This Lambda is the authoritative arbiter of reservation availability — all
    capacity enforcement happens here, not in the intake Lambda (LF11b).

AWS Integrations:
    - SQS (Q2):              Event source trigger; each record is a reservation request
                             forwarded by LF11b.
    - DynamoDB (Restaurant): Queried by restaurant_id to get seating capacity.
    - DynamoDB (Reservation): Queried via GSI to check existing reservations;
                              written to with a ConditionExpression to prevent duplicates.
    - DynamoDB (User):       Queried by user_id to retrieve the customer's email address.
    - SES:                   Sends confirmation or failure email to the customer.

Event Structure (SQS Records):
    Each record['body'] is a JSON string:
    {
        "user_id": "<cognito-sub>",
        "restaurant_id": "<restaurant-uuid>",
        "res_date": "YYYY-MM-DD",
        "time": "HH:MM",
        "party_size": 4
    }

Returns:
    dict with statusCode 200 and a list of per-record success/failure results.
    Returns 500 on unexpected top-level errors.
"""

import boto3
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from botocore.exceptions import ClientError


# DynamoDB low-level client — used here because all reads/writes use the
# DynamoDB typed attribute format (e.g., {'S': '...'}, {'N': '...'})
dynamodb = boto3.client('dynamodb')

# SQS client — not used directly in this file but available for future use
sqs = boto3.client('sqs')

# SES client for sending confirmation/failure emails to the user
ses = boto3.client('ses', region_name="us-east-1")

# DynamoDB table name constants
RESTAURANT_TABLE = 'Restaurant'
RESERVATION_TABLE = 'Reservation'
USER_TABLE = 'User'

# Verified SES sender address — must be confirmed in the AWS SES console
SENDER_EMAIL = 'abr9982@nyu.edu'


def lambda_handler(event, context):
    """
    Main entry point for the Make Reservation Lambda.

    Iterates over each SQS record in the batch, processes the reservation request,
    and sends an appropriate email notification. Collects per-record results and
    returns them all in the response body.

    Args:
        event (dict): SQS event containing a list of records under 'Records'.
        context (LambdaContext): AWS Lambda context object (unused here).

    Returns:
        dict: HTTP 200 response with a JSON body containing per-record outcomes,
              or HTTP 500 if an unexpected top-level error occurs.
    """
    try:
        response_messages = []
        for record in event['Records']:
            # Parse message from SQS — the body field is a JSON-encoded string
            message = json.loads(record['body'])
            user_id = message['user_id']
            restaurant_id = message['restaurant_id']
            res_date = message['res_date']
            time = message['time']
            party_size = int(message['party_size'])

            # Perform the atomic availability check and reservation creation.
            # Returns (True, "success msg") or (False, "error reason").
            success, message = process_reservation(user_id, restaurant_id, res_date, time, party_size)
            response_messages.append({'success': success, 'message': message})
            print(f"Processed reservation for user {user_id}: {message}")
            print('RESPONSE MESSAGES ', response_messages)

            # Retrieve user email for the notification — first check before email send
            user_email = get_user_email(user_id)
            if not user_email:
                print(f"No email found for user {user_id}. Skipping notification.")
                continue

            # Send email notification to the user.
            # Note: get_user_email is called a second time here (minor redundancy).
            # The reservation_id is constructed as a composite key to be human-readable.
            user_email = get_user_email(user_id)
            reservation_id= f"{restaurant_id}#{res_date}#{time}#{user_id}"
            send_email_notification(user_email, reservation_id, restaurant_id, res_date, time, party_size, success, message)


        return {'statusCode': 200, 'body': json.dumps(response_messages)}

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def process_reservation(user_id, restaurant_id, res_date, time, party_size):
    """
    Orchestrates the full reservation lifecycle for a single request.

    Fetches restaurant capacity, checks existing reservations, validates
    availability, and — if available — creates the reservation atomically.

    Args:
        user_id (str):       Cognito sub of the user making the reservation.
        restaurant_id (str): The target restaurant's ID.
        res_date (str):      Reservation date in 'YYYY-MM-DD' format.
        time (str):          Desired reservation time in 'HH:MM' format.
        party_size (int):    Number of guests in the party.

    Returns:
        tuple: (bool success, str message) — True with a success message if
               the reservation was created; False with an error explanation otherwise.
    """
    try:
        # Fetch restaurant capacity and existing reservations
        restaurant = fetch_restaurant(restaurant_id)
        if not restaurant:
            message = f"Restaurant {restaurant_id} not found."
            print(message)
            return False, message

        # Extract the numeric capacity from DynamoDB's typed 'N' format
        capacity = int(restaurant['capacity']['N'])

        # Get all reservations for this restaurant on the same date (via GSI)
        reservations = fetch_reservations(restaurant_id, res_date)

        # Check whether the requested time slot can accommodate the party
        if not is_time_available(reservations, res_date, time, party_size, capacity):
            message = f"Insufficient capacity for reservation at {time}."
            print(message)
            return False, message

        # Attempt to create reservation atomically using a ConditionExpression.
        # If two requests race for the same slot, only one will succeed.
        create_reservation(user_id, restaurant_id, res_date, time, party_size)
        return True, "Reservation successful."

    except Exception as e:
        error_message = f"Error processing reservation: {str(e)}"
        print(error_message)
        return False, error_message


def fetch_restaurant(restaurant_id):
    """
    Fetches a restaurant's full DynamoDB item by its partition key.

    Args:
        restaurant_id (str): The restaurant's primary key value.

    Returns:
        dict: The raw DynamoDB item (with typed attributes) if found, or None.
    """
    response = dynamodb.get_item(
        TableName=RESTAURANT_TABLE,
        Key={'restaurant_id': {'S': restaurant_id}}
    )
    return response.get('Item')


def fetch_reservations(restaurant_id, res_date):
    """
    Fetches all reservations for a restaurant on a specific date using a GSI.

    The Reservation table has a Global Secondary Index (GSI) named
    'restaurant_id-res_date-index' that enables efficient date-scoped queries
    per restaurant, avoiding a full table scan.

    Args:
        restaurant_id (str): GSI partition key — the restaurant to query.
        res_date (str):      GSI sort key — the date to filter by ('YYYY-MM-DD').

    Returns:
        list: Raw DynamoDB items (with typed attributes) for all reservations
              matching the restaurant and date.
    """
    response = dynamodb.query(
        TableName=RESERVATION_TABLE,
        IndexName='restaurant_id-res_date-index',  # GSI enables efficient date-scoped query
        KeyConditionExpression='restaurant_id = :r_id AND res_date = :r_date',
        ExpressionAttributeValues={
            ':r_id': {'S': restaurant_id},
            ':r_date': {'S': res_date}
        }
    )
    return response['Items']


def is_time_available(reservations, res_date, time, party_size, capacity):
    """
    Checks whether a requested time slot can accommodate the party size.

    Two validations are performed:
    1. Temporal guard: Rejects reservations in the past by comparing the
       requested datetime against the current time in Eastern Time (America/New_York).
    2. Capacity guard: Sums the party sizes of all reservations within a 1-hour
       overlap window around the requested time and checks whether adding the
       new party would exceed the restaurant's total seating capacity.

    Args:
        reservations (list): Raw DynamoDB items for existing reservations on this date.
        res_date (str):      The reservation date ('YYYY-MM-DD').
        time (str):          The requested time ('HH:MM').
        party_size (int):    Number of guests in the new party.
        capacity (int):      Total seating capacity of the restaurant.

    Returns:
        bool: True if there is sufficient capacity and the time is not in the past;
              False otherwise.
    """
    # Convert current UTC time to Eastern Time for a timezone-aware comparison.
    # zoneinfo (Python 3.9+) is used for correct DST handling.
    utc_now = datetime.now(ZoneInfo("UTC"))
    now = utc_now.astimezone(ZoneInfo("America/New_York"))

    # Parse the reservation datetime as a naive datetime, then make it timezone-aware
    # in Eastern Time so it can be compared directly against 'now'
    reservation_datetime_naive = datetime.strptime(f"{res_date} {time}", "%Y-%m-%d %H:%M")
    reservation_datetime = reservation_datetime_naive.replace(tzinfo=ZoneInfo("America/New_York"))

    print('NOW: ', now)
    print('Reservation date and time: ', reservation_datetime)
    if reservation_datetime < now:
        print("reservation date and time are in the past")
        return False  # Cannot make a reservation in the past

    # Sum up reserved seats for all reservations within a 1-hour overlap window.
    # Any reservation whose time is within 60 minutes (before or after) of the
    # requested time is assumed to compete for the same physical seating capacity.
    total_reserved = sum(
        int(r['party_size']['N']) for r in reservations
        if abs(
            datetime.strptime(r['time']['S'], "%H:%M") - datetime.strptime(time, "%H:%M")
        ) < timedelta(hours=1)  # Overlap within an hour
    )
    return total_reserved + party_size <= capacity


def create_reservation(user_id, restaurant_id, res_date, time, party_size):
    """
    Writes a new reservation record to the Reservation table in DynamoDB.

    Uses a ConditionExpression ('attribute_not_exists(reservation_id)') to make
    the write idempotent — if a reservation with the same composite key already
    exists (e.g., due to SQS message redelivery or a race condition), the write
    is rejected with a ConditionalCheckFailedException rather than overwriting
    the existing record.

    The reservation_id is a composite key constructed from restaurant, date,
    time, and user — making it deterministic and human-readable.

    Args:
        user_id (str):       Cognito sub of the user.
        restaurant_id (str): The restaurant's ID.
        res_date (str):      Reservation date ('YYYY-MM-DD').
        time (str):          Reservation time ('HH:MM').
        party_size (int):    Number of guests.

    Raises:
        ClientError: If the conditional write fails (e.g., duplicate reservation)
                     or any other DynamoDB error occurs.
    """
    dynamodb.put_item(
        TableName=RESERVATION_TABLE,
        Item={
            # Composite reservation_id encodes all booking dimensions, making
            # it easy to identify and ensuring uniqueness per (restaurant, date, time, user)
            'reservation_id': {'S': f"{restaurant_id}#{res_date}#{time}#{user_id}"},
            'user_id': {'S': user_id},
            'restaurant_id': {'S': restaurant_id},
            'res_date': {'S': res_date},
            'time': {'S': time},
            'party_size': {'N': str(party_size)},
            'status':{'S':'RESERVED'}
        },
        # Idempotency guard: reject the write if this reservation_id already exists.
        # Prevents double-booking if this Lambda is invoked multiple times for the
        # same SQS message (e.g., due to at-least-once delivery semantics).
        ConditionExpression="attribute_not_exists(reservation_id)"  # Ensure no duplicates
    )


def get_user_email(user_id):
    """
    Fetches the email address for a user from the User table.

    The 'email' field is stored as a DynamoDB String attribute ('S') and is
    extracted from the typed response format.

    Args:
        user_id (str): The user's partition key (Cognito 'sub').

    Returns:
        str: The user's email address if the user exists and has an email,
             or None otherwise.
    """
    response = dynamodb.get_item(
        TableName=USER_TABLE,
        Key={'user_id': {'S': user_id}}
    )
    user = response.get('Item')
    if user:
        return user['email']['S']  # Extract the string value from the DynamoDB attribute
    return None


# Function to send email notification
def send_email_notification(user_email, reservation_id, restaurant_id, res_date, time, party_size, success, message):
    """
    Sends a confirmation or failure email to the user via Amazon SES.

    Two distinct email bodies are generated:
    - On success: includes the reservation ID and full booking details.
    - On failure: includes the reason for failure along with the attempted booking details.

    The restaurant name is fetched from DynamoDB to include in the email body,
    making it more informative than just showing the restaurant_id.

    Args:
        user_email (str):    Recipient email address.
        reservation_id (str): Composite reservation ID (restaurant#date#time#user).
        restaurant_id (str): Used to fetch the restaurant name for the email body.
        res_date (str):      Reservation date ('YYYY-MM-DD').
        time (str):          Reservation time ('HH:MM').
        party_size (int):    Number of guests in the party.
        success (bool):      Whether the reservation was successfully created.
        message (str):       Success confirmation or failure reason from process_reservation.

    Raises:
        ClientError: If the SES send_email call fails.
    """
    # Fetch the restaurant's display name for inclusion in the email body.
    # The 'name' attribute is retrieved in DynamoDB's typed format {'S': '...'}.
    restaurant = fetch_restaurant(restaurant_id)['name']
    subject = f"Reservation Update"
    if success:
        body = f"""
        Hello,

        Your reservation with ID {reservation_id} has been made. Please see details below:
            {restaurant['S']}
            date: {res_date}
            time: {time}
            number of people: {party_size}

        Thank you for using our service!

        Best regards,
        FeastFleet Team
        """
    else:
        # Include the failure reason so the user understands why the booking failed
        body = f"""
        Hello,

        We were not able to process your reservation. Please see details below:
        Issue: {message}
            {restaurant['S']}
            date: {res_date}
            time: {time}
            number of people: {party_size}

        Thank you for using our service!

        Best regards,
        FeastFleet Team
        """
    try:
        # SES send_email — Source must be a verified identity in the AWS account.
        # The email is sent as plain text only; no HTML version is included.
        ses.send_email(
            Source=SENDER_EMAIL,
            Destination={"ToAddresses": [user_email]},
            Message={
                "Subject": {"Data": subject},
                "Body": {
                    "Text": {"Data": body}
                }
            }
        )
        print(f"Email sent to {user_email} for reservation {reservation_id} with status {success}")
    except ClientError as e:
        print(f"Error sending email to {user_email}: {e.response['Error']['Message']}")
        raise
