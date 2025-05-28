import json
import boto3
import os
from datetime import datetime, timezone
import requests  # For making API calls
import time  # For mocking delays
import random  # For simulating success/failure

dynamodb = boto3.resource('dynamodb')
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "ScheduledSocialPosts")
table = dynamodb.Table(DYNAMODB_TABLE_NAME)

secrets_client = boto3.client('secretsmanager')

# --- Social Media API Base URLs ---
# Always use a specific API version to avoid unexpected changes
INSTAGRAM_GRAPH_API_BASE_URL = "https://graph.facebook.com/v19.0/"


# CHANGED: Removed 'platform' as it's not strictly needed here; secret contains all credentials
def get_social_media_credentials():
    """Retrieves social media API credentials from AWS Secrets Manager."""
    try:
        secret_name = os.environ.get("SOCIAL_MEDIA_SECRETS_NAME", "social_media_api_keys")
        response = secrets_client.get_secret_value(SecretId=secret_name)
        secret_string = response['SecretString']
        secrets = json.loads(secret_string)
        return secrets
    except Exception as e:
        print(f"Error retrieving social media credentials: {e}")
        return None


# RENAMED from post_to_instagram to clarify it's for images
def post_to_instagram_image(image_url, caption, credentials):
    """
    Attempts to post an IMAGE to Instagram using the Graph API.
    """
    instagram_business_account_id = credentials.get('instagram_business_account_id')
    access_token = credentials.get('instagram_access_token')

    if not instagram_business_account_id or not access_token:
        print("ERROR: Missing Instagram Business Account ID or Access Token for image post.")
        return False, "Instagram API credentials not configured for image posting."

    print(f"Attempting to post IMAGE to Instagram (Business Account ID: {instagram_business_account_id})...")

    # Step 1: Create Media Container for an image
    container_creation_url = f"{INSTAGRAM_GRAPH_API_BASE_URL}{instagram_business_account_id}/media"
    container_params = {
        'image_url': image_url,  # Key for images
        'caption': caption,
        'access_token': access_token
    }

    try:
        container_response = requests.post(container_creation_url, params=container_params)
        container_response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        container_data = container_response.json()
        media_container_id = container_data.get('id')

        if not media_container_id:
            print(f"ERROR: Failed to create Instagram image media container. Response: {container_data}")
            return False, f"Failed to create Instagram image media container: {container_data.get('error', {}).get('message', 'Unknown error')}"

        print(f"Instagram image media container created with ID: {media_container_id}")

        # Step 2: Publish Media Container
        publish_url = f"{INSTAGRAM_GRAPH_API_BASE_URL}{instagram_business_account_id}/media_publish"
        publish_params = {
            'creation_id': media_container_id,
            'access_token': access_token
        }
        publish_response = requests.post(publish_url, params=publish_params)
        publish_response.raise_for_status()
        publish_data = publish_response.json()
        instagram_post_id = publish_data.get('id')

        if not instagram_post_id:
            print(f"ERROR: Failed to publish Instagram image. Response: {publish_data}")
            return False, f"Failed to publish Instagram image: {publish_data.get('error', {}).get('message', 'Unknown error')}"

        print(f"Instagram image published with ID: {instagram_post_id}")
        return True, f"Instagram image post successful (Post ID: {instagram_post_id})."

    except requests.exceptions.HTTPError as http_err:
        error_message = f"HTTP error during Instagram image post: {http_err} - {http_err.response.text}"
        print(error_message)
        return False, error_message
    except requests.exceptions.ConnectionError as conn_err:
        error_message = f"Connection error during Instagram image post: {conn_err}"
        print(error_message)
        return False, error_message
    except requests.exceptions.Timeout as timeout_err:
        error_message = f"Timeout error during Instagram image post: {timeout_err}"
        print(error_message)
        return False, error_message
    except requests.exceptions.RequestException as req_err:
        error_message = f"An error occurred during Instagram image post: {req_err}"
        print(error_message)
        return False, req_err
    except Exception as e:
        error_message = f"An unexpected error occurred during Instagram image post: {str(e)}"
        print(error_message)
        return False, error_message


# NEW FUNCTION: For posting videos to Instagram
def post_to_instagram_video(video_url, caption, credentials):
    """
    Attempts to post a VIDEO to Instagram using the Graph API.
    Requires similar setup as image posting, but different parameters.
    NOTE: Instagram video publishing can be asynchronous for longer videos.
          This implementation assumes a quick response for shorter videos.
          For production, consider polling /media_id?fields=status,status_code.
    """
    instagram_business_account_id = credentials.get('instagram_business_account_id')
    access_token = credentials.get('instagram_access_token')

    if not instagram_business_account_id or not access_token:
        print("ERROR: Missing Instagram Business Account ID or Access Token in credentials.")
        return False, "Instagram API credentials not configured."

    print(f"Attempting to post VIDEO to Instagram (Business Account ID: {instagram_business_account_id})...")

    # Step 1: Create Media Container for Video
    # 'media_type' must be 'VIDEO'. 'video_url' is the key for videos.
    container_creation_url = f"{INSTAGRAM_GRAPH_API_BASE_URL}{instagram_business_account_id}/media"
    container_params = {
        'media_type': 'VIDEO',  # Explicitly set media_type to VIDEO
        'video_url': video_url,  # Publicly accessible video URL (your S3 URL)
        'caption': caption,
        'access_token': access_token
    }

    try:
        container_response = requests.post(container_creation_url, params=container_params)
        container_response.raise_for_status()
        container_data = container_response.json()
        media_container_id = container_data.get('id')

        if not media_container_id:
            print(f"ERROR: Failed to create Instagram video media container. Response: {container_data}")
            return False, f"Failed to create Instagram video media container: {container_data.get('error', {}).get('message', 'Unknown error')}"

        print(f"Instagram video media container created with ID: {media_container_id}. Waiting for processing...")
        # Instagram needs time to process videos before publishing.
        # For simplicity, we'll just wait a bit and hope.
        # In a real app, you'd poll the container status.
        time.sleep(10)  # Wait 10 seconds for Instagram to process the video

        # Step 2: Publish Media Container
        publish_url = f"{INSTAGRAM_GRAPH_API_BASE_URL}{instagram_business_account_id}/media_publish"
        publish_params = {
            'creation_id': media_container_id,
            'access_token': access_token
        }
        publish_response = requests.post(publish_url, params=publish_params)
        publish_response.raise_for_status()
        publish_data = publish_response.json()
        instagram_post_id = publish_data.get('id')

        if not instagram_post_id:
            print(f"ERROR: Failed to publish Instagram video. Response: {publish_data}")
            return False, f"Failed to publish Instagram video: {publish_data.get('error', {}).get('message', 'Unknown error')}"

        print(f"Instagram video published with ID: {instagram_post_id}")
        return True, f"Instagram video post successful (Post ID: {instagram_post_id})."

    except requests.exceptions.HTTPError as http_err:
        error_message = f"HTTP error during Instagram video post: {http_err} - {http_err.response.text}"
        print(error_message)
        return False, error_message
    except requests.exceptions.ConnectionError as conn_err:
        error_message = f"Connection error during Instagram video post: {conn_err}"
        print(error_message)
        return False, error_message
    except requests.exceptions.Timeout as timeout_err:
        error_message = f"Timeout error during Instagram video post: {timeout_err}"
        print(error_message)
        return False, error_message
    except requests.exceptions.RequestException as req_err:
        error_message = f"An error occurred during Instagram video post: {req_err}"
        print(error_message)
        return False, req_err
    except Exception as e:
        error_message = f"An unexpected error occurred during Instagram video post: {str(e)}"
        print(error_message)
        return False, error_message


# RENAMED from post_to_facebook to clarify it's for images (mock)
def post_to_facebook_image(image_url, caption, credentials):
    """Mocks posting an IMAGE to Facebook."""
    print(f"MOCK: Posting IMAGE to Facebook...")
    print(f"  Image URL: {image_url}")
    print(f"  Caption: {caption}")
    # Simulate API call delay
    time.sleep(random.uniform(1, 3))
    # Simulate success or failure
    if random.random() < 0.9:  # 90% chance of success
        print("MOCK: Facebook image post successful!")
        return True, "Mock Facebook image post successful."
    else:
        print("MOCK: Facebook image post failed!")
        return False, "Mock Facebook API error for image."


# NEW FUNCTION: For posting videos to Facebook (mock)
def post_to_facebook_video(video_url, caption, credentials):
    """Mocks posting a VIDEO to Facebook."""
    print(f"MOCK: Posting VIDEO to Facebook...")
    print(f"  Video URL: {video_url}")
    print(f"  Caption: {caption}")
    # Simulate API call delay
    time.sleep(random.uniform(2, 5))  # Videos might take longer
    # Simulate success or failure
    if random.random() < 0.8:  # 80% chance of success for video (can be less reliable in mocks)
        print("MOCK: Facebook video post successful!")
        return True, "Mock Facebook video post successful."
    else:
        print("MOCK: Facebook video post failed!")
        return False, "Mock Facebook API error for video."


# --- Lambda Handler ---
def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event)}")
    post_id = event.get('post_id')

    if not post_id:
        print("Error: Missing post_id in event.")
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Missing post_id in event.'})
        }

    try:
        # 1. Fetch post details from DynamoDB
        response = table.get_item(Key={'post_id': post_id})
        item = response.get('Item')

        if not item:
            print(f"Post with ID {post_id} not found in DynamoDB.")
            return {
                'statusCode': 404,
                'body': json.dumps({'message': f'Post {post_id} not found.'})
            }

        # CHANGED: Retrieve generic media_s3_url and media_type
        # The 'media_s3_url' now holds either the image or video URL
        media_s3_url = item.get('media_s3_url')
        # 'media_type' tells us if it's an 'image' or 'video', default to 'image' for older entries
        media_type = item.get('media_type', 'image')

        caption = item.get('caption')
        platform = item.get('platform')
        current_status = item.get('status')

        if current_status == 'posted':
            print(f"Post {post_id} already posted. Skipping.")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': f'Post {post_id} already posted.'})
            }

        print(f"Attempting to post {media_type} {post_id} to {platform}...")

        # 2. Get social media credentials (no change needed here)
        all_credentials = get_social_media_credentials()  # No platform parameter needed now
        if not all_credentials:
            print(f"Could not retrieve any social media credentials from Secrets Manager.")
            table.update_item(
                Key={'post_id': post_id},
                UpdateExpression="SET #s = :status, #m = :message",
                ExpressionAttributeNames={'#s': 'status', '#m': 'last_message'},
                ExpressionAttributeValues={':status': 'failed', ':message': 'Missing social media credentials secret.'}
            )
            return {
                'statusCode': 500,
                'body': json.dumps({'message': 'Failed to retrieve social media credentials.'})
            }

        # 3. Perform the actual social media post based on platform AND media_type
        success = False
        message = "Unsupported platform/media type or unknown error during posting."

        if platform == "Instagram":
            if media_type == "image":
                success, message = post_to_instagram_image(media_s3_url, caption, all_credentials)
            elif media_type == "video":
                success, message = post_to_instagram_video(media_s3_url, caption, all_credentials)
            else:
                message = f"Unsupported media type for Instagram: {media_type}"
                print(message)
        elif platform == "Facebook":
            if media_type == "image":
                success, message = post_to_facebook_image(media_s3_url, caption, all_credentials)
            elif media_type == "video":
                success, message = post_to_facebook_video(media_s3_url, caption, all_credentials)
            else:
                message = f"Unsupported media type for Facebook: {media_type}"
                print(message)
        else:
            message = f"Unsupported platform: {platform}"
            print(message)

        # 4. Update status in DynamoDB
        new_status = 'posted' if success else 'failed'
        table.update_item(
            Key={'post_id': post_id},
            UpdateExpression="SET #s = :status, #m = :message, #pt = :post_time",
            ExpressionAttributeNames={'#s': 'status', '#m': 'last_message', '#pt': 'actual_post_time_utc'},
            ExpressionAttributeValues={
                ':status': new_status,
                ':message': message,
                ':post_time': datetime.now(timezone.utc).isoformat()
            }
        )

        if success:
            print(f"Successfully posted {post_id} ({media_type}) to {platform}.")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': f'Post {post_id} ({media_type}) successfully processed.'})
            }
        else:
            print(f"Failed to post {post_id} ({media_type}) to {platform}: {message}")
            return {
                'statusCode': 500,
                'body': json.dumps({'message': f'Failed to post {post_id} ({media_type}): {message}'})
            }

    except Exception as e:
        print(f"Error in social_media_poster_lambda: {e}")
        # Update status to failed in case of unhandled exception
        if post_id:  # Only attempt if post_id is known
            try:
                table.update_item(
                    Key={'post_id': post_id},
                    UpdateExpression="SET #s = :status, #m = :message",
                    ExpressionAttributeNames={'#s': 'status', '#m': 'last_message'},
                    ExpressionAttributeValues={':status': 'failed', ':message': f'Unhandled error: {str(e)}'}
                )
            except Exception as update_err:
                print(f"Error updating item status to failed for post_id {post_id}: {update_err}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': f'Internal server error: {str(e)}'})
        }