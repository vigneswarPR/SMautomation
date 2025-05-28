import json
import boto3
import uuid
import os
from datetime import datetime, timezone

dynamodb = boto3.resource('dynamodb')
# Replace with your DynamoDB table name
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "ScheduledSocialPosts")
table = dynamodb.Table(DYNAMODB_TABLE_NAME)

eventbridge_client = boto3.client('scheduler')


def lambda_handler(event, context):
    try:
        body = json.loads(event['body'])

        # CHANGED: Renamed from image_s3_url to media_s3_url
        media_s3_url = body.get('media_s3_url')

        caption = body.get('caption')
        platform = body.get('platform')
        scheduled_time_utc_str = body.get('scheduled_time_utc')  # ISO format string
        user_id = body.get('user_id', 'anonymous')  # Get user ID, default to anonymous

        # NEW: Added media_type (e.g., 'image', 'video'), defaulting to 'image'
        media_type = body.get('media_type', 'image')

        # CHANGED: Updated validation to use media_s3_url
        if not all([media_s3_url, caption, platform, scheduled_time_utc_str, media_type]):
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                                       'message': 'Missing required fields (media_s3_url, caption, platform, scheduled_time_utc, media_type).'})
            }

        # Convert scheduled time string to datetime object
        scheduled_datetime_utc = datetime.fromisoformat(scheduled_time_utc_str.replace('Z', '+00:00'))
        # Ensure it's timezone-aware UTC
        if scheduled_datetime_utc.tzinfo is None:
            scheduled_datetime_utc = scheduled_datetime_utc.replace(tzinfo=timezone.utc)
        else:
            scheduled_datetime_utc = scheduled_datetime_utc.astimezone(timezone.utc)

        post_id = str(uuid.uuid4())
        creation_time = datetime.now(timezone.utc).isoformat()

        # Store post details in DynamoDB
        item = {
            'post_id': post_id,
            'user_id': user_id,
            'media_s3_url': media_s3_url,  # CHANGED: Storing as generic media_s3_url
            'media_type': media_type,  # NEW: Storing media type
            'caption': caption,
            'platform': platform,
            'scheduled_time_utc': scheduled_time_utc_str,
            'creation_time_utc': creation_time,
            'status': 'pending'  # Initial status
        }
        table.put_item(Item=item)

        # --- Create EventBridge Schedule ---
        # The ARN of the social_media_poster_lambda will be passed as an environment variable
        # Or you can construct it if you know the region and account ID
        target_lambda_arn = os.environ.get("SOCIAL_MEDIA_POSTER_LAMBDA_ARN")
        if not target_lambda_arn:
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'SOCIAL_MEDIA_POSTER_LAMBDA_ARN not configured.'})
            }

        schedule_name = f"social-post-{post_id}"
        # EventBridge Scheduler expects a string for the schedule expression
        # For one-time schedules, use 'at(YYYY-MM-DDTHH:MM:SS)'
        schedule_expression = f"at({scheduled_datetime_utc.strftime('%Y-%m-%dT%H:%M:%S')})"

        eventbridge_client.create_schedule(
            Name=schedule_name,
            Description=f"Schedule for social media post {post_id} on {platform}",
            ScheduleExpression=schedule_expression,
            FlexibleTimeWindow={'Mode': 'OFF'},  # For precise scheduling
            Target={
                'Arn': target_lambda_arn,
                'RoleArn': os.environ.get("EVENTBRIDGE_SCHEDULE_ROLE_ARN"),  # IAM Role for EventBridge to invoke Lambda
                'Input': json.dumps({'post_id': post_id})  # Pass post_id to the target Lambda
            },
            State='ENABLED'
        )

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'success',
                'message': 'Post scheduled successfully',
                'post_id': post_id
            })
        }
    except Exception as e:
        print(f"Error scheduling post: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'status': 'error', 'message': f'Internal server error: {str(e)}'})
        }