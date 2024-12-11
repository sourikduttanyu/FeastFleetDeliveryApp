import boto3
from decimal import Decimal
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

# AWS region and service
region = 'us-east-1'
service = 'es'

# AWS credentials and OpenSearch authentication
credentials = boto3.Session().get_credentials()
auth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token)

# OpenSearch client configuration
host = ''
client = OpenSearch(
    hosts=[{'host': host, 'port': 443}],
    http_auth=('', ''),
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    timeout=30
)

# DynamoDB table resources
dynamodb = boto3.resource('dynamodb', region_name=region)
restaurant_table = dynamodb.Table('Restaurant')
menu_items_table = dynamodb.Table('Menu_Items')


# Create indexes if they don't already exist
def create_indexes():
    # Restaurant index
    if not client.indices.exists(index='restaurants_index'):
        restaurant_index_body = {
            'settings': {
                'number_of_shards': 1,
                'number_of_replicas': 1
            },
            'mappings': {
                'properties': {
                    'restaurant_id': {'type': 'keyword'},
                    'name': {'type': 'text'},
                    'cuisine': {'type': 'text'},
                    'coordinates': {'type': 'geo_point'}
                }
            }
        }
        client.indices.create(index='restaurants_index', body=restaurant_index_body)
        print("Created index: restaurants_index")

    # Menu items index
    if not client.indices.exists(index='menu_items_index'):
        menu_items_index_body = {
            'settings': {
                'number_of_shards': 1,
                'number_of_replicas': 1
            },
            'mappings': {
                'properties': {
                    'item_name': {'type': 'text'},
                    'restaurant_id': {'type': 'keyword'},
                    'coordinates': {'type': 'geo_point'}
                }
            }
        }
        client.indices.create(index='menu_items_index', body=menu_items_index_body)
        print("Created index: menu_items_index")


# Push data from Restaurant table to restaurants_index
def push_restaurants_to_opensearch():
    last_evaluated_key = None
    total_items_indexed = 0
    total_items_skipped = 0

    while True:
        # Scan the Restaurant table
        if last_evaluated_key:
            response = restaurant_table.scan(
                ExclusiveStartKey=last_evaluated_key,
                Limit=100
            )
        else:
            response = restaurant_table.scan(Limit=100)

        items = response['Items']

        for item in items:
            restaurant_id = item.get('restaurant_id')

            # Check if the document already exists
            if client.exists(index='restaurants_index', id=restaurant_id):
                print(f"Document {restaurant_id} already exists in restaurants_index. Skipping.")
                total_items_skipped += 1
                continue

            # Prepare the document for OpenSearch
            document = {
                'restaurant_id': restaurant_id,
                'name': item.get('name'),
                'cuisine': item.get('cuisine'),
                'coordinates': item.get('coordinates')
            }

            try:
                # Index the document into OpenSearch
                es_response = client.index(index='restaurants_index', id=restaurant_id, body=document)
                total_items_indexed += 1
                print(f"Indexed RestaurantID {restaurant_id}: {es_response['result']}")
            except Exception as e:
                print(f"Failed to index document {restaurant_id}: {str(e)}")

        last_evaluated_key = response.get('LastEvaluatedKey')
        print(f"LastEvaluatedKey: {last_evaluated_key}")

        if not last_evaluated_key:
            print("Finished indexing restaurants.")
            break

    print(f"Total restaurants indexed: {total_items_indexed}")
    print(f"Total restaurants skipped (already exist): {total_items_skipped}")


# Push data from Menu_Items table to menu_items_index
def push_menu_items_to_opensearch():
    last_evaluated_key = None
    total_items_indexed = 0
    total_items_skipped = 0

    while True:
        # Scan the Menu_Items table
        if last_evaluated_key:
            response = menu_items_table.scan(
                ExclusiveStartKey=last_evaluated_key,
                Limit=100
            )
        else:
            response = menu_items_table.scan(Limit=100)

        items = response['Items']

        for item in items:
            item_id = item.get('item_id')

            # Check if the document already exists
            if client.exists(index='menu_items_index', id=item_id):
                print(f"Document {item_id} already exists in menu_items_index. Skipping.")
                total_items_skipped += 1
                continue

            # Prepare the document for OpenSearch
            document = {
                'item_name': item.get('item_name'),
                'restaurant_id': item.get('restaurant_id'),
                'coordinates': item.get('coordinates')
            }

            try:
                # Index the document into OpenSearch
                es_response = client.index(index='menu_items_index', id=item_id, body=document)
                total_items_indexed += 1
                print(f"Indexed ItemID {item_id}: {es_response['result']}")
            except Exception as e:
                print(f"Failed to index document {item_id}: {str(e)}")

        last_evaluated_key = response.get('LastEvaluatedKey')
        print(f"LastEvaluatedKey: {last_evaluated_key}")

        if not last_evaluated_key:
            print("Finished indexing menu items.")
            break

    print(f"Total menu items indexed: {total_items_indexed}")
    print(f"Total menu items skipped (already exist): {total_items_skipped}")


# Main function
if __name__ == "__main__":
    create_indexes()
    push_restaurants_to_opensearch()
    push_menu_items_to_opensearch()
