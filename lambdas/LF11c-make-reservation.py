import boto3
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from botocore.exceptions import ClientError


# Initialize DynamoDB and SQS clients
dynamodb = boto3.client('dynamodb')
sqs = boto3.client('sqs')
ses = boto3.client('ses', region_name="us-east-1")

# Table names
RESTAURANT_TABLE = 'Restaurant'
RESERVATION_TABLE = 'Reservation'
USER_TABLE = 'User'
SENDER_EMAIL = 'abr9982@nyu.edu'

def lambda_handler(event, context):
    try:
        response_messages = []
        for record in event['Records']:
            # Parse message from SQS
            message = json.loads(record['body'])
            user_id = message['user_id']
            restaurant_id = message['restaurant_id']
            res_date = message['res_date']
            time = message['time']
            party_size = int(message['party_size'])

            # Atomic check and reservation creation
            success, message = process_reservation(user_id, restaurant_id, res_date, time, party_size)
            response_messages.append({'success': success, 'message': message})
            print(f"Processed reservation for user {user_id}: {message}")
            print('RESPONSE MESSAGES ', response_messages)

            user_email = get_user_email(user_id)
            if not user_email:
                print(f"No email found for user {user_id}. Skipping notification.")
                continue

            # Send email notification to the user
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
    """Process a single reservation: check availability and create reservation atomically."""
    try:
        # Fetch restaurant capacity and existing reservations
        restaurant = fetch_restaurant(restaurant_id)
        if not restaurant:
            message = f"Restaurant {restaurant_id} not found."
            print(message)
            return False, message

        capacity = int(restaurant['capacity']['N'])
        reservations = fetch_reservations(restaurant_id, res_date)

        # Check availability
        if not is_time_available(reservations, res_date, time, party_size, capacity):
            message = f"Insufficient capacity for reservation at {time}."
            print(message)
            return False, message

        # Attempt to create reservation atomically
        create_reservation(user_id, restaurant_id, res_date, time, party_size)
        return True, "Reservation successful."

    except Exception as e:
        error_message = f"Error processing reservation: {str(e)}"
        print(error_message)
        return False, error_message

def fetch_restaurant(restaurant_id):
    """Fetch restaurant details from DynamoDB."""
    response = dynamodb.get_item(
        TableName=RESTAURANT_TABLE,
        Key={'restaurant_id': {'S': restaurant_id}}
    )
    return response.get('Item')

def fetch_reservations(restaurant_id, res_date):
    """Fetch all reservations for the given restaurant and date."""
    response = dynamodb.query(
        TableName=RESERVATION_TABLE,
        IndexName='restaurant_id-res_date-index',
        KeyConditionExpression='restaurant_id = :r_id AND res_date = :r_date',
        ExpressionAttributeValues={
            ':r_id': {'S': restaurant_id},
            ':r_date': {'S': res_date}
        }
    )
    return response['Items']

def is_time_available(reservations, res_date, time, party_size, capacity):
    """Check if there is availability for the given party size."""
    # Convert UTC to a specific timezone
    utc_now = datetime.now(ZoneInfo("UTC"))
    now = utc_now.astimezone(ZoneInfo("America/New_York"))

    # Parse the reservation datetime and make it timezone-aware
    reservation_datetime_naive = datetime.strptime(f"{res_date} {time}", "%Y-%m-%d %H:%M")
    reservation_datetime = reservation_datetime_naive.replace(tzinfo=ZoneInfo("America/New_York"))

    print('NOW: ', now)
    print('Reservation date and time: ', reservation_datetime)
    if reservation_datetime < now:
        print("reservation date and time are in the past")
        return False  # Cannot make a reservation in the past

    total_reserved = sum(
        int(r['party_size']['N']) for r in reservations
        if abs(
            datetime.strptime(r['time']['S'], "%H:%M") - datetime.strptime(time, "%H:%M")
        ) < timedelta(hours=1)  # Overlap within an hour
    )
    return total_reserved + party_size <= capacity

def create_reservation(user_id, restaurant_id, res_date, time, party_size):
    """Create a reservation atomically in DynamoDB."""
    dynamodb.put_item(
        TableName=RESERVATION_TABLE,
        Item={
            'reservation_id': {'S': f"{restaurant_id}#{res_date}#{time}#{user_id}"},
            'user_id': {'S': user_id},
            'restaurant_id': {'S': restaurant_id},
            'res_date': {'S': res_date},
            'time': {'S': time},
            'party_size': {'N': str(party_size)},
            'status':{'S':'RESERVED'}
        },
        ConditionExpression="attribute_not_exists(reservation_id)"  # Ensure no duplicates
    )

def get_user_email(user_id):
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
    Sends email notification using SES.
    """
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
