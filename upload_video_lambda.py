import json
import boto3
import uuid
import os
import base64

s3_client = boto3.client('s3')

# Environment variable for your S3 bucket name
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")


def lambda_handler(event, context):
    try:
        if not S3_BUCKET_NAME:
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'S3_BUCKET_NAME environment variable not set.'})
            }

        body = json.loads(event['body'])
        video_data_b64 = body.get('video_data_b64')
        file_name = body.get('file_name')

        if not video_data_b64 or not file_name:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Missing video_data_b64 or file_name.'})
            }

        # Decode base64 video data
        video_bytes = base64.b64decode(video_data_b64)

        # Generate a unique file name for S3
        file_extension = os.path.splitext(file_name)[1]  # e.g., .mp4, .mov
        unique_file_name = f"videos/{uuid.uuid4()}{file_extension}"  # Store in 'videos/' folder

        # Upload video to S3
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=unique_file_name,
            Body=video_bytes,
            ContentType=f"video/{file_extension.lstrip('.')}"  # Set appropriate content type
        )

        video_s3_url = f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/{unique_file_name}"
        # For public access (if S3 bucket policy allows GetObject), this URL will work.
        # If not public, you might need to generate a pre-signed URL here for temporary access.

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'success',
                'message': 'Video uploaded successfully',
                'video_s3_url': video_s3_url
            })
        }

    except Exception as e:
        print(f"Error uploading video: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'status': 'error', 'message': f'Internal server error: {str(e)}'})
        }