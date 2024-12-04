import boto3
import random
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')

RESTAURANT_TABLE = "Restaurant"

# Generate random opening and closing hours
def generate_random_hours():
    opening_hour = random.randint(5, 11)  # Random hour between 5am and 11am
    closing_hour = random.randint(16, 24)  # Random hour between 4pm and 12am
    return f"{opening_hour:02d}:00", f"{closing_hour:02d}:00"  # Format to "HH:MM"

# Generate random days closed
def generate_days_closed(restaurants, total_restaurants):
    closed_two_days = random.sample(restaurants, total_restaurants // 3)  # Random third
    remaining_restaurants = [r for r in restaurants if r not in closed_two_days]
    closed_one_day = random.sample(remaining_restaurants, total_restaurants // 3)  # Another third
    always_open = [r for r in restaurants if r not in closed_two_days and r not in closed_one_day]
    return closed_two_days, closed_one_day, always_open

# Generate weekly hours for a restaurant
def generate_weekly_hours(closed_days):
    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekly_hours = []
    for day in days_of_week:
        if day in closed_days:
            weekly_hours.append({"day": day, "open": False, "opening_hour": None, "closing_hour": None})
        else:
            opening_hour, closing_hour = generate_random_hours()
            weekly_hours.append({"day": day, "open": True, "opening_hour": opening_hour, "closing_hour": closing_hour})
    return weekly_hours

# Update restaurants in DynamoDB
def update_restaurants_with_schedule(restaurant_table):
    table = dynamodb.Table(restaurant_table)

    # Get all restaurants
    response = table.scan()
    restaurants = response.get("Items", [])
    total_restaurants = len(restaurants)

    # Divide restaurants into groups
    closed_two_days, closed_one_day, always_open = generate_days_closed(restaurants, total_restaurants)

    # Update each restaurant
    for restaurant in restaurants:
        restaurant_id = restaurant["restaurant_id"]

        # Assign capacity
        capacity = random.randint(5, 25)

        # Assign hours
        if restaurant in closed_two_days:
            closed_days = random.sample(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], 2)
        elif restaurant in closed_one_day:
            closed_days = random.sample(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], 1)
        else:
            closed_days = []

        weekly_hours = generate_weekly_hours(closed_days)

        # Update DynamoDB
        table.update_item(
            Key={"restaurant_id": restaurant_id},
            UpdateExpression="SET capacity = :capacity, hours = :hours",
            ExpressionAttributeValues={
                ":capacity": capacity,
                ":hours": weekly_hours
            }
        )
        print(f"Updated Restaurant: {restaurant.get('name')} with capacity {capacity} and hours {weekly_hours}")

    print("Finished updating all restaurants.")

# Main function
if __name__ == "__main__":
    update_restaurants_with_schedule(RESTAURANT_TABLE)
