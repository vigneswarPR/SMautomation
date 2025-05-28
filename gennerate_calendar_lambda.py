import json
import os
import boto3
import google.generativeai as genai
import calendar

# Initialize AWS Secrets Manager client
secrets_client = boto3.client('secretsmanager')

# Environment variables
GEMINI_API_KEY_SECRET_NAME = os.environ.get("GEMINI_API_KEY_SECRET_NAME", "gemini-api-key") # Default name
# In production, use your actual secret name for Gemini API key

def get_gemini_api_key():
    """Retrieves the Gemini API key from AWS Secrets Manager."""
    try:
        response = secrets_client.get_secret_value(SecretId=GEMINI_API_KEY_SECRET_NAME)
        secret_string = response['SecretString']
        secret_dict = json.loads(secret_string)
        return secret_dict.get('GEMINI_API_KEY')
    except Exception as e:
        print(f"Error retrieving Gemini API key from Secrets Manager: {e}")
        raise ValueError("Gemini API key not found or accessible.")

def generate_calendar_lambda_handler(event, context):
    try:
        # Parse incoming request body
        body = json.loads(event['body'])
        month = body.get('month')
        year = body.get('year')
        business_description = body.get('business_description')
        target_audience = body.get('target_audience')
        content_themes = body.get('content_themes')
        post_frequency = body.get('post_frequency')

        if not all([month, year, business_description, target_audience, content_themes, post_frequency]):
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*' # CORS
                },
                'body': json.dumps({'error': 'Missing required calendar parameters'})
            }

        # Configure Gemini API
        gemini_api_key = get_gemini_api_key()
        if not gemini_api_key:
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*' # CORS
                },
                'body': json.dumps({'error': 'Gemini API key not configured or found'})
            }
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-pro') # Using gemini-pro for text generation

        # Craft the prompt for Gemini
        prompt = f"""
        Generate a detailed social media content calendar for hogist food delivery company {calendar.month_name[month]} {year}.
        Business Description: {business_description}
        Target Audience: {target_audience}
        Key Content Themes: {content_themes}
        Desired Post Frequency: {post_frequency}

        Provide the calendar as a daily plan, specifying the date, a suggested content idea/topic, and a brief note on the type of content (e.g., image, video, carousel, story).
        Aim for content variety based on the themes.
        Format the output clearly, ideally in markdown format, using bullet points or a simple list for each day.
        Example format for a day:
        **Day X (Day of Week):**
        - Topic: [Content Idea]
        - Content Type: [Image/Video/Text/Carousel/Story]
        - Note: [Brief explanation or call to action]
        """

        # Generate content with Gemini
        response = model.generate_content(prompt)
        calendar_plan = response.text

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*' # CORS
            },
            'body': json.dumps({'calendar_plan': calendar_plan})
        }

    except Exception as e:
        print(f"Error in generate_calendar_lambda: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*' # CORS
            },
            'body': json.dumps({'error': str(e)})
        }