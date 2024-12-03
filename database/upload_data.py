import boto3
import csv
import uuid
from decimal import Decimal


dynamodb = boto3.resource('dynamodb')
location_client = boto3.client('location')

RESTAURANT_TABLE = "Restaurant"
MENU_ITEMS_TABLE = "Menu_Items"

PLACE_INDEX_NAME = "RestaurantPlaceIndex"


# Geocoding using AWS Location Service
def get_coordinates(address):
    try:
        response = location_client.search_place_index_for_text(
            IndexName="RestaurantPlaceIndex",
            Text=address,
            MaxResults=1
        )
        if response['Results']:
            position = response['Results'][0]['Place']['Geometry']['Point']
            return {"lat": Decimal(str(position[1])), "lon": Decimal(str(position[0]))}  # AWS returns [lon, lat]
        else:
            print(f"Could not geocode address: {address}")
            return None
    except Exception as e:
        print(f"Error during geocoding for address '{address}': {e}")
        return None


# Process and upload restaurant data
def process_and_upload_restaurant_data(input_file, restaurant_table):
    table = dynamodb.Table(restaurant_table)

    with open(input_file, mode='r') as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            # Generate unique restaurant_id
            restaurant_id = str(uuid.uuid4())

            # Get coordinates using AWS Location Service
            coordinates = get_coordinates(row["Address"])
            if not coordinates:
                continue  # Skip rows that couldn't be geocoded

            # Prepare item
            item = {
                "restaurant_id": restaurant_id,
                "name": row["Name"],
                "cuisine": row["Cuisine"],
                "address": row["Address"],
                "coordinates": coordinates,
                "full_url": row["Full_URL"]
            }

            # Upload to DynamoDB
            table.put_item(Item=item)
            print(f"Uploaded Restaurant: {item['name']} with coordinates {coordinates}")

    print("Finished processing and uploading restaurant data.")

# Process and upload menu items data
def process_and_upload_menu_data(input_file, menu_items_table, restaurant_mapping):
    table = dynamodb.Table(menu_items_table)
    total_uploaded = 0  # Counter to track successfully uploaded items

    with open(input_file, mode='r') as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            # Generate unique item_id
            item_id = str(uuid.uuid4())

            # Map restaurant_name to restaurant_id
            restaurant_id = restaurant_mapping.get(row["Restaurant"])
            if not restaurant_id:
                print(f"Warning: No restaurant_id found for {row['Restaurant']}")
                continue

            # Clean and validate price
            try:
                raw_price = row["Price"].strip()  # Remove any leading/trailing spaces
                # Remove non-numeric characters like '$'
                cleaned_price = ''.join(c for c in raw_price if c.isdigit() or c == '.')
                if not cleaned_price or not cleaned_price.replace('.', '', 1).isdigit():  # Validate numeric value
                    raise ValueError(f"Invalid price value: {row['Price']}")
                price = Decimal(cleaned_price)  # Convert cleaned price to Decimal
            except Exception as e:
                print(f"Error converting price for {row['Item']}: {e}")
                continue  # Skip this row if the price is invalid

            # Prepare item
            item = {
                "restaurant_name": row["Restaurant"],
                "restaurant_id": restaurant_id,
                "item_id": item_id,
                "item_name": row["Item"],
                "price": price  # Use Decimal for price
            }

            # Upload to DynamoDB
            table.put_item(Item=item)
            print(f"Uploaded Menu Item: {item['item_name']} for {row['Restaurant']} at price {price}")
            total_uploaded += 1  # Increment counter for successfully uploaded items

    # Log the total count of uploaded items
    print(f"Finished processing and uploading menu data. Total items uploaded: {total_uploaded}")

def get_restaurant_mapping(restaurant_table):
    table = dynamodb.Table(restaurant_table)
    response = table.scan()  # Scan the entire table to get all restaurants
    mapping = {item["name"]: item["restaurant_id"] for item in response.get("Items", [])}
    return mapping

# Main function
if __name__ == "__main__":
    # File paths
    restaurant_data_file = ""
    menu_data_file = ""
    restaurant_mapping = get_restaurant_mapping(RESTAURANT_TABLE)

    #process_and_upload_restaurant_data(restaurant_data_file, RESTAURANT_TABLE)
    process_and_upload_menu_data(menu_data_file, MENU_ITEMS_TABLE, restaurant_mapping)
