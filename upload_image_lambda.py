import json
import boto3
import base64
import uuid
import os

s3_client = boto3.client('s3')

# Replace with your S3 bucket name
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "your-unique-image-upload-bucket-name")

def lambda_handler(event, context):
    try:
        # Parse the request body
        body = json.loads(event['body'])
        image_data_base64 = body.get('image_data')
        filename = body.get('filename', 'uploaded_image.png')

        if not image_data_base64:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Missing image_data in request body.'})
            }

        # Decode base64 image data
        image_bytes = base64.b64decode(image_data_base64)

        # Generate a unique filename for S3
        file_extension = filename.split('.')[-1] if '.' in filename else 'png'
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        s3_key = f"uploads/{unique_filename}" # Store in an 'uploads' folder

        # Upload to S3
        s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=s3_key, Body=image_bytes, ContentType=f'image/{file_extension}')

        # Generate the S3 URL
        s3_url = f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/{s3_key}"

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*' # IMPORTANT for CORS with Streamlit
            },
            'body': json.dumps({
                'message': 'Image uploaded successfully',
                's3_url': s3_url
            })
        }
    except Exception as e:
        print(f"Error: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': f'Internal server error: {str(e)}'})
        }

