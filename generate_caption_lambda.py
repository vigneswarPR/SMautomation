import json
import google.generativeai as genai
from PIL import Image
import requests
import io
import os
import base64 # For converting image from URL to base64 for Gemini if needed
import uuid # For temporary file names


genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# Initialize the Gemini model
model = genai.GenerativeModel('gemini-1.5-flash')

# Engagement-focused prompt templates (copied from your original script)
engagement_prompts = {
    'high_engagement': """
    Analyze this food image and create 3 highly engaging Instagram captions for a food delivery service.

    Requirements for maximum engagement:
    1. Start with attention-grabbing hooks (questions, bold statements, emojis)
    2. Include emotional triggers (craving, comfort, satisfaction)
    3. Add interactive elements (ask questions, encourage comments)
    4. Use food delivery specific CTAs
    5. Include trending food hashtags
    6. Keep it conversational and relatable
    7. Create FOMO (fear of missing out)

    Format each caption as:
    Caption 1: [caption text]
    Engagement Score: [rate 1-10 for potential engagement]

    Focus on captions that make people want to:
    - Comment about their cravings
    - Tag friends
    - Share the post
    - Place an order immediately
    """,

    'story_style': """
    Create 5 Instagram captions for this food image that tell a story and increase engagement.

    Style requirements:
    1. Use storytelling techniques
    2. Create relatable scenarios
    3. Include sensory descriptions (taste, smell, texture)
    4. Add personal touches
    5. End with engaging questions
    6. Use appropriate emojis strategically

    Make people feel like they're experiencing the food through your words.
    """,

    'viral_potential': """
    Generate 3 Instagram captions with viral potential for this food delivery image.

    Viral elements to include:
    1. Trending phrases and slang
    2. Relatable situations everyone experiences
    3. Humor or wit
    4. Universal food experiences
    5. Shareable moments
    6. Interactive challenges or questions

    Think about what makes people share food content and incorporate those elements.
    """
}

def _parse_captions(response_text):
    """Parse the generated captions from Gemini response."""
    captions = []
    lines = response_text.split('\n')

    current_caption = ""
    current_score = None

    for line in lines:
        line = line.strip()
        # Check for "Caption X:" or "Caption X (Strategy):" to start a new caption
        if (line.startswith('Caption') or line.startswith('Variant')) and ':' in line:
            if current_caption: # If there's a current caption being built, save it first
                captions.append({
                    'text': current_caption.strip(),
                    'engagement_score': current_score,
                    'word_count': len(current_caption.split()),
                    'character_count': len(current_caption)
                })

            # Reset for the new caption
            parts = line.split(':', 1)
            current_caption = parts[1].strip() if len(parts) > 1 else "" # Get text after colon
            current_score = None

        elif line.startswith('Engagement Score') and ':' in line:
            try:
                score_str = line.split(':')[1].strip().split('/')[0].strip() # Handle "/10" format
                current_score = int(score_str)
            except ValueError: # Handle cases where score might not be a clean integer
                current_score = None

        elif line.startswith('Target Appeal') and ':' in line: # For targeted captions
            current_caption += "\n" + line

        elif line.startswith('Business Impact') and ':' in line: # For targeted captions
            current_caption += "\n" + line

        elif line.startswith('Variant') and '(' in line and ')' in line and ':' in line: # For A/B test captions strategy
            if current_caption:
                captions.append({
                    'text': current_caption.strip(),
                    'engagement_score': current_score, # Score might not be present for all styles
                    'word_count': len(current_caption.split()),
                    'character_count': len(current_caption)
                })
            parts = line.split(':', 1)
            current_caption = parts[1].strip() if len(parts) > 1 else ""
            current_score = None # Reset score

        elif current_caption and line and not (line.startswith('Engagement Score') or line.startswith('Target Appeal') or line.startswith('Business Impact') or line.startswith('Variant') or line.startswith('Caption')):
            current_caption += " " + line # Append lines to the current caption

    # Add the last caption if anything was built
    if current_caption:
        captions.append({
            'text': current_caption.strip(),
            'engagement_score': current_score,
            'word_count': len(current_caption.split()),
            'character_count': len(current_caption)
        })

    return captions

def generate_targeted_captions(image, target_audience, business_goals):
    targeted_prompt = f"""
    Analyze this food delivery image and create 3 Instagram captions optimized for:

    Target Audience: {target_audience}
    Business Goals: {business_goals}

    Requirements:
    1. Speak directly to the target audience's interests and pain points
    2. Align with business goals while maximizing engagement
    3. Use language and tone that resonates with this specific audience
    4. Include relevant hashtags for this demographic
    5. Add CTAs that support the business goals
    6. Create urgency and desire specific to this audience

    Make each caption feel personally crafted for this audience while driving the desired business outcomes.

    Format as:
    Caption 1: [caption]
    Target Appeal: [why this appeals to the audience]
    Business Impact: [how this supports business goals]
    """
    response = model.generate_content([targeted_prompt, image])
    return response.text

def generate_ab_test_captions(image, num_variants=5):
    ab_test_prompt = f"""
    Create {num_variants} distinctly different Instagram captions for this food delivery image.
    Each caption should test different engagement strategies:

    1. Emotional Appeal - Focus on feelings and comfort
    2. Urgency/Scarcity - Create FOMO and immediate action
    3. Social Proof - Emphasize popularity and reviews
    4. Question/Interactive - Encourage comments and engagement
    5. Humor/Personality - Use wit and brand personality

    For each caption, explain the strategy being tested.

    Format as:
    Variant 1 (Strategy): [caption]
    Variant 2 (Strategy): [caption]
    etc.
    """
    response = model.generate_content([ab_test_prompt, image])
    return response.text


def lambda_handler(event, context):
    # Retrieve Gemini API key from environment variable (set via Secrets Manager)
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        print("GEMINI_API_KEY not found in environment variables.")
        return {
            'statusCode': 500,
            'headers': { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
            'body': json.dumps({'message': 'Gemini API key not configured.'})
        }
    genai.configure(api_key=gemini_api_key)

    try:
        body = json.loads(event['body'])
        image_s3_url = body.get('image_s3_url')
        style = body.get('style', 'high_engagement')
        custom_prompt = body.get('custom_prompt')
        target_audience = body.get('target_audience')
        business_goals = body.get('business_goals')
        num_variants = body.get('num_variants', 3)

        if not image_s3_url:
            return {
                'statusCode': 400,
                'headers': { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
                'body': json.dumps({'message': 'Missing image_s3_url in request body.'})
            }

        # Download image from S3 URL
        image_response = requests.get(image_s3_url)
        image_response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        image_bytes = image_response.content
        image = Image.open(io.BytesIO(image_bytes))

        # Determine which prompt to use
        if custom_prompt:
            prompt = custom_prompt
            response = model.generate_content([prompt, image])
            response_text = response.text
        elif style == 'targeted':
            response_text = generate_targeted_captions(image, target_audience, business_goals)
        elif style == 'A/B Test':
            response_text = generate_ab_test_captions(image, num_variants)
        else:
            prompt = engagement_prompts.get(style, engagement_prompts['high_engagement'])
            response = model.generate_content([prompt, image])
            response_text = response.text


        captions = _parse_captions(response_text)

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Captions generated successfully',
                'captions': captions,
                'original_response': response_text,
                'style_used': style
            })
        }
    except Exception as e:
        print(f"Error generating captions: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': f'Internal server error: {str(e)}'})
        }

