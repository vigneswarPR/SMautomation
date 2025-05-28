import json
import os
import boto3
import google.generativeai as genai
from google.cloud import storage  # NEW: For interacting with Google Cloud Storage
import tempfile  # NEW: For creating temporary files
from datetime import datetime, timezone
import random

s3_client = boto3.client('s3')



# Initialize Google Cloud Storage client and Gemini model
try:
    # Load credentials from environment variable
    gcp_credentials_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if not gcp_credentials_json:
        raise ValueError("GOOGLE_APPLICATION_CREDENTIALS_JSON environment variable is not set.")


    with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as temp_key_file:
        temp_key_file.write(gcp_credentials_json)
        google_credentials_path = temp_key_file.name


    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = google_credentials_path


    gcs_client = storage.Client()
    GCS_BUCKET_NAME = os.environ.get("GCS_TEMPORARY_BUCKET_NAME")
    if not GCS_BUCKET_NAME:
        raise ValueError("GCS_TEMPORARY_BUCKET_NAME environment variable is not set.")
    gcs_bucket = gcs_client.bucket(GCS_BUCKET_NAME)


    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))  # Ensure GEMINI_API_KEY is also set
    GEMINI_MODEL_NAME = os.environ.get("GEMINI_MODEL_NAME", "gemini-pro-vision")
    gemini_model = genai.GenerativeModel(GEMINI_MODEL_NAME)


    if os.path.exists(google_credentials_path):
        os.remove(google_credentials_path)

except Exception as e:
    print(f"Failed to initialize Google Cloud clients or Gemini: {e}")

    raise


dynamodb = boto3.resource('dynamodb')
# Replace with your DynamoDB table name for scheduled posts
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "ScheduledSocialPosts")
table = dynamodb.Table(DYNAMODB_TABLE_NAME)


def generate_video_captions_with_gemini(gcs_video_uri, style, custom_prompt, target_audience, business_goals,
                                        num_variants):

    print(f"Generating captions for GCS video URI: {gcs_video_uri} with style: {style}")


    prompt_parts = []

    # Add video input using the GCS URI
    video_input = genai.upload_file(gcs_video_uri)  # This function implies fetching from a URL/GCS URI
    prompt_parts.append(video_input)


    base_prompt = "Generate social media captions for this video."
    if style == 'high_engagement':
        base_prompt += " Focus on high engagement, using trending topics and questions to encourage interaction. Provide 3 options."
    elif style == 'story_style':
        base_prompt += " Create a narrative or story-telling style caption. Provide 3 options."
    elif style == 'viral_potential':
        base_prompt += " Aim for virality with catchy phrases, humor, or strong calls to action. Provide 3 options."
    elif style == 'targeted' and target_audience and business_goals:
        base_prompt += f" Target a {target_audience} audience to achieve the goal of {business_goals}. Provide 3 options."
    elif style == 'A/B Test' and num_variants > 0:
        base_prompt += f" Generate {num_variants} distinct variants for A/B testing, exploring different angles or tones."
    elif style == 'custom' and custom_prompt:
        base_prompt = custom_prompt  # Custom prompt overrides everything
    else:
        base_prompt += " Provide 3 standard, descriptive captions."

    prompt_parts.append(base_prompt)

    try:
        response = gemini_model.generate_content(prompt_parts)
        response.resolve()  # Ensure the content is available if it was streamed

        raw_text = response.text.strip()
        print(f"Raw Gemini response: {raw_text}")


        captions = []
        # Simple parsing for numbered or bulleted lists from Gemini's response
        lines = raw_text.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith(('1.', '2.', '3.', '-', '*')) or (line and line[0].isdigit() and '.' in line):

                caption_text = line.split('.', 1)[-1].strip() if '.' in line else line.split(' ', 1)[-1].strip()
                captions.append({'text': caption_text, 'engagement_score': random.randint(70, 99)})  # Mock score
            elif line:  # If not a numbered list, treat each non-empty line as a caption
                captions.append({'text': line, 'engagement_score': random.randint(70, 99)})


        if not captions and raw_text:
            captions.append({'text': raw_text, 'engagement_score': random.randint(70, 99)})

        return captions
    except Exception as e:
        print(f"Error calling Gemini API for video: {e}")
        return []


def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event)}")

    video_s3_url = event.get('video_s3_url')
    style = event.get('style', 'high_engagement')
    custom_prompt = event.get('custom_prompt')
    target_audience = event.get('target_audience')
    business_goals = event.get('business_goals')
    num_variants = event.get('num_variants', 3)  # For A/B testing

    if not video_s3_url:
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Missing video_s3_url in event.'})
        }


    try:
        url_parts = video_s3_url.split('/')
        s3_bucket_name = url_parts[2].split('.')[0]
        s3_key = '/'.join(url_parts[3:])
    except Exception as e:
        print(f"Could not parse S3 URL: {video_s3_url}, Error: {e}")
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Invalid S3 video URL format.'})
        }

    temp_video_path = None
    gcs_temp_object_name = None
    gcs_video_uri = None

    try:
        # --- Step 1: Download video from S3 to Lambda's /tmp directory ---
        print(f"Downloading video from S3://{s3_bucket_name}/{s3_key} to /tmp...")
        temp_video_path = os.path.join(tempfile.gettempdir(), os.path.basename(s3_key))
        s3_client.download_file(s3_bucket_name, s3_key, temp_video_path)
        print(f"Video downloaded to {temp_video_path}")

        # --- Step 2: Upload video from /tmp to Google Cloud Storage (GCS) ---
        print(f"Uploading video from /tmp to GCS bucket: {GCS_BUCKET_NAME}...")
        gcs_temp_object_name = f"temp_gemini_video_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{os.path.basename(s3_key)}"
        gcs_blob = gcs_bucket.blob(gcs_temp_object_name)
        gcs_blob.upload_from_filename(temp_video_path)
        gcs_video_uri = f"gs://{GCS_BUCKET_NAME}/{gcs_temp_object_name}"
        print(f"Video uploaded to GCS: {gcs_video_uri}")

        # --- Step 3: Generate captions using Gemini from GCS URI ---
        captions = generate_video_captions_with_gemini(
            gcs_video_uri,
            style,
            custom_prompt,
            target_audience,
            business_goals,
            num_variants
        )

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'captions': captions})
        }

    except Exception as e:
        print(f"Error processing video for caption generation: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': f'Failed to generate video captions: {str(e)}'})
        }
    finally:
        # --- Step 4: Clean up temporary files ---
        # Remove local temp file
        if temp_video_path and os.path.exists(temp_video_path):
            os.remove(temp_video_path)
            print(f"Cleaned up local temp file: {temp_video_path}")

        # Remove temporary video from GCS
        if gcs_temp_object_name:
            try:
                gcs_blob = gcs_bucket.blob(gcs_temp_object_name)
                if gcs_blob.exists():
                    gcs_blob.delete()
                    print(f"Cleaned up GCS temp object: {gcs_temp_object_name}")
            except Exception as e:
                print(f"Error cleaning up GCS object {gcs_temp_object_name}: {e}")