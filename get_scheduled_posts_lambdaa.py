import json
import boto3
import os

dynamodb = boto3.resource('dynamodb')
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "ScheduledSocialPosts")
table = dynamodb.Table(DYNAMODB_TABLE_NAME)

def lambda_handler(event, context):
    try:
        # In a real application, you would use event['requestContext']['authorizer']['claims']['sub']
        # or similar to get the authenticated user_id. For this demo, we'll use a query parameter.
        query_params = event.get('queryStringParameters', {})
        user_id = query_params.get('user_id', 'demo_user_123') # Default for demo

        # Scan the table for items belonging to the user_id
        # For production, consider using query with a GSI if you need to filter by user_id frequently
        # and it's not part of the primary key.
        response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('user_id').eq(user_id)
        )
        items = response.get('Items', [])

        # Continue scanning if there are more items (pagination)
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('user_id').eq(user_id),
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response.get('Items', []))


        # Sort items by scheduled_time_utc for better display
        sorted_items = sorted(items, key=lambda x: x.get('scheduled_time_utc', ''), reverse=True)

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(sorted_items)
        }
    except Exception as e:
        print(f"Error fetching scheduled posts: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': f'Internal server error: {str(e)}'})
        }

