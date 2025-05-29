import streamlit as st
import requests
import json
from datetime import datetime, time, timezone
import base64
import io
from PIL import Image
import calendar # NEW: For month and year selection

# --- API Endpoints (REPLACE WITH YOUR ACTUAL API GATEWAY ENDPOINTS) ---
# Existing Image Endpoints
UPLOAD_IMAGE_API_URL = "https://l63kkw2lv5.execute-api.ap-southeast-2.amazonaws.com/prod/upload_image_lambda"
GENERATE_CAPTION_API_URL = "https://r7frxw7h53.execute-api.ap-southeast-2.amazonaws.com/prod/generate_caption_lambda"  # For images

# NEW Video Endpoints (assuming you might have separate Lambda for video upload)
UPLOAD_VIDEO_API_URL = "YOUR_API_GATEWAY_URL/upload-video" # Make sure this points to your GCS-aware video upload lambda
GENERATE_VIDEO_CAPTION_API_URL = "YOUR_API_GATEWAY_URL/generate-video-caption"

# Common Scheduling and Listing Endpoints
SCHEDULE_POST_API_URL = "https://dr0po98y5a.execute-api.ap-southeast-2.amazonaws.com/prod/schedule_post_lambda"
GET_SCHEDULED_POSTS_API_URL = "https://u9m9l59p9k.execute-api.ap-southeast-2.amazonaws.com/prod/get_schedule_post_lambda"

# NEW: Calendar Generation Endpoint
GENERATE_CALENDAR_API_URL = "YOUR_API_GATEWAY_URL/generate-calendar" # You'll define this later

st.set_page_config(layout="wide", page_title="AI Social Media Assistant")
try:
    image = Image.open('logohog.jpg')
    col1, col2, col3 = st.columns([7, 1, 7])
    with col2:
        st.image(image, width=60)
except FileNotFoundError:
    st.error("Error: 'logohog.jpg' not found. Please check the file path.") # Corrected image file name
st.title("📸 AI Social Media Assistant 🎥")

# --- Session State Initialization ---
if 'uploaded_image_s3_url' not in st.session_state:
    st.session_state['uploaded_image_s3_url'] = None
if 'uploaded_video_s3_url' not in st.session_state:
    st.session_state['uploaded_video_s3_url'] = None
if 'current_media_type' not in st.session_state:
    st.session_state['current_media_type'] = None
if 'generated_captions' not in st.session_state:
    st.session_state['generated_captions'] = []
if 'selected_caption_text' not in st.session_state:
    st.session_state['selected_caption_text'] = ""
if 'caption_style' not in st.session_state:
    st.session_state['caption_style'] = 'high_engagement'
if 'generated_calendar' not in st.session_state: # NEW: To store generated calendar
    st.session_state['generated_calendar'] = None


# --- Navigation ---
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Post Scheduler", "Content Calendar"])

if page == "Post Scheduler":
    # --- Media Upload Section ---
    st.header("1. Upload Your Media (Image or Video)")

    col1_upload, col2_upload = st.columns(2)

    with col1_upload:
        uploaded_image_file = st.file_uploader(
            "Upload an Image",
            type=["png", "jpg", "jpeg", "gif"],
            key="image_uploader"
        )
        if uploaded_image_file is not None:
            # Ensure only one type of media is active at a time
            if st.session_state['uploaded_video_s3_url']:
                st.session_state['uploaded_video_s3_url'] = None
                st.session_state['current_media_type'] = None # Reset media type

            if st.button("Upload Image"):
                with st.spinner("Uploading image..."):
                    files = {'file': uploaded_image_file.getvalue()}
                    try:
                        response = requests.post(UPLOAD_IMAGE_API_URL, files=files)
                        if response.status_code == 200:
                            s3_url = response.json().get('image_s3_url')
                            st.session_state['uploaded_image_s3_url'] = s3_url
                            st.session_state['current_media_type'] = 'image'
                            st.success(f"Image uploaded! S3 URL: {s3_url}")
                            st.image(s3_url, caption="Uploaded Image", use_column_width=True)
                        else:
                            st.error(f"Error uploading image: {response.text}")
                    except Exception as e:
                        st.error(f"Network error during image upload: {e}")

    with col2_upload:  # Video Upload
        uploaded_video_file = st.file_uploader(
            "Upload a Video",
            type=["mp4", "mov", "avi", "webm"],  # Common video formats
            key="video_uploader"
        )
        if uploaded_video_file is not None:
            # Ensure only one type of media is active at a time
            if st.session_state['uploaded_image_s3_url']:
                st.session_state['uploaded_image_s3_url'] = None
                st.session_state['current_media_type'] = None # Reset media type

            if st.button("Upload Video"):
                with st.spinner("Uploading video..."):
                    try:
                        video_bytes = uploaded_video_file.getvalue()
                        video_data_b64 = base64.b64encode(video_bytes).decode('utf-8')

                        payload = {
                            "video_data_b64": video_data_b64,
                            "file_name": uploaded_video_file.name
                        }
                        headers = {"Content-Type": "application/json"}

                        response = requests.post(UPLOAD_VIDEO_API_URL, json=payload, headers=headers)

                        if response.status_code == 200:
                            # Assuming your video upload lambda returns a GCS URL now
                            gcs_url = response.json().get('video_gcs_url') # Changed key to reflect GCS
                            st.session_state['uploaded_video_s3_url'] = gcs_url # Store in same variable, but it's GCS
                            st.session_state['current_media_type'] = 'video'
                            st.success(f"Video uploaded! GCS URL: {gcs_url}")
                            st.video(gcs_url)
                        else:
                            st.error(f"Error uploading video: {response.text}")
                    except Exception as e:
                        st.error(f"Network error during video upload: {e}")

    # --- Caption Generation Section ---
    st.header("2. Generate Social Media Captions")

    # Display uploaded media
    if st.session_state['current_media_type'] == 'image' and st.session_state['uploaded_image_s3_url']:
        st.image(st.session_state['uploaded_image_s3_url'], caption="Currently Selected Image", use_column_width=True)
    elif st.session_state['current_media_type'] == 'video' and st.session_state['uploaded_video_s3_url']:
        st.video(st.session_state['uploaded_video_s3_url'])
    else:
        st.info("Please upload an image or video above to generate captions.")

    if st.session_state['uploaded_image_s3_url'] or st.session_state['uploaded_video_s3_url']:

        caption_style = st.selectbox(
            "Choose Caption Style:",
            ('high_engagement', 'story_style', 'viral_potential', 'targeted', 'A/B Test', 'custom'),
            key="caption_style",
            index=['high_engagement', 'story_style', 'viral_potential', 'targeted', 'A/B Test', 'custom'].index(
                st.session_state['caption_style'])
        )

        custom_prompt = None
        target_audience = None
        business_goals = None
        num_variants = 3

        if caption_style == 'custom':
            custom_prompt = st.text_area("Enter Custom Prompt:", "Generate 3 captions for this media, focusing on...",
                                         height=100)
        elif caption_style == 'targeted':
            target_audience = st.text_input("Target Audience (e.g., 'young entrepreneurs', 'foodies'):")
            business_goals = st.text_input("Business Goals (e.g., 'drive website traffic', 'increase brand awareness'):")
        elif caption_style == 'A/B Test':
            num_variants = st.slider("Number of Caption Variants (for A/B Test):", 2, 5, 3)

        if st.button("Generate Captions"):
            if st.session_state['current_media_type'] == 'image' and st.session_state['uploaded_image_s3_url']:
                api_url_to_call = GENERATE_CAPTION_API_URL
                payload_media_key = "image_s3_url"
                media_url_to_send = st.session_state['uploaded_image_s3_url']
            elif st.session_state['current_media_type'] == 'video' and st.session_state['uploaded_video_s3_url']:
                api_url_to_call = GENERATE_VIDEO_CAPTION_API_URL
                payload_media_key = "video_gcs_url" # Changed to reflect GCS for video
                media_url_to_send = st.session_state['uploaded_video_s3_url'] # This holds the GCS URL now
            else:
                st.warning("Please upload an image or video first.")
                st.stop()

            payload = {
                payload_media_key: media_url_to_send,
                "style": caption_style
            }
            if custom_prompt:
                payload["custom_prompt"] = custom_prompt
            if target_audience:
                payload["target_audience"] = target_audience
            if business_goals:
                payload["business_goals"] = business_goals
            if caption_style == 'A/B Test':
                payload["num_variants"] = num_variants

            with st.spinner("Generating captions with AI..."):
                try:
                    response = requests.post(api_url_to_call, json=payload)
                    if response.status_code == 200:
                        st.session_state['generated_captions'] = response.json().get('captions', [])
                        if not st.session_state['generated_captions']:
                            st.warning("AI generated no captions. Try a different style or prompt.")
                        else:
                            st.success("Captions generated!")
                    else:
                        st.error(f"Error generating captions: {response.text}")
                        st.session_state['generated_captions'] = []
                except Exception as e:
                    st.error(f"Network error during caption generation: {e}")
                    st.session_state['generated_captions'] = []

        # Display generated captions for selection and editing
        if st.session_state['generated_captions']:
            st.subheader("Generated Captions:")
            caption_options = [
                f"Engagement Score: {c['engagement_score']} - {c['text']}" if c.get('engagement_score') else c['text'] for c
                in st.session_state['generated_captions']]

            selected_caption_display = st.radio(
                "Choose a caption for your post:",
                caption_options,
                key="selected_caption_radio"
            )

            initial_caption_for_editing = ""
            for c in st.session_state['generated_captions']:
                if (f"Engagement Score: {c['engagement_score']} - {c['text']}" == selected_caption_display or
                        c['text'] == selected_caption_display):
                    initial_caption_for_editing = c['text']
                    break

            st.session_state['selected_caption_text'] = initial_caption_for_editing

            st.subheader("Edit Selected Caption (Optional):")
            st.session_state['selected_caption_text'] = st.text_area(
                "Modify your caption here:",
                value=st.session_state['selected_caption_text'],
                height=150,
                key="edited_caption_text_area"
            )

    # --- Schedule Post Section ---
    st.header("3. Schedule Your Post")

    if st.session_state['selected_caption_text'] and (
            st.session_state['uploaded_image_s3_url'] or st.session_state['uploaded_video_s3_url']):

        st.write(f"**Selected Caption:** {st.session_state['selected_caption_text']}")

        media_url_to_schedule = None
        media_type_to_schedule = None

        if st.session_state['current_media_type'] == 'image' and st.session_state['uploaded_image_s3_url']:
            media_url_to_schedule = st.session_state['uploaded_image_s3_url']
            media_type_to_schedule = 'image'
        elif st.session_state['current_media_type'] == 'video' and st.session_state['uploaded_video_s3_url']:
            media_url_to_schedule = st.session_state['uploaded_video_s3_url'] # This holds GCS URL
            media_type_to_schedule = 'video'
        else:
            st.warning("Please upload an image or video and select a caption first.")
            st.stop()

        platform = st.selectbox(
            "Choose Platform:",
            ('Instagram', 'Facebook'),
            key="platform_select"
        )

        col_date, col_time = st.columns(2)
        with col_date:
            scheduled_date = st.date_input("Schedule Date:", datetime.now().date(), key="schedule_date")
        with col_time:
            scheduled_time = st.time_input("Schedule Time (UTC):", time(10, 0), key="schedule_time")

        if st.button("Schedule Post"):
            try:
                scheduled_datetime_utc = datetime.combine(scheduled_date, scheduled_time, tzinfo=timezone.utc).isoformat()

                schedule_payload = {
                    "media_url": media_url_to_schedule,  # Generic media URL (S3 for image, GCS for video)
                    "media_type": media_type_to_schedule,  # Type of media
                    "caption": st.session_state['selected_caption_text'],
                    "platform": platform,
                    "scheduled_time_utc": scheduled_datetime_utc,
                    "user_id": "demo_user_123"
                }

                with st.spinner("Scheduling post..."):
                    response = requests.post(SCHEDULE_POST_API_URL, json=schedule_payload)
                    if response.status_code == 200:
                        st.success("Post scheduled successfully!")
                    else:
                        st.error(f"Error scheduling post: {response.text}")
            except Exception as e:
                st.error(f"Network error during scheduling: {e}")

    else:
        st.info("Upload media and generate/select a caption to schedule a post.")

    st.markdown("---")

    # --- View Scheduled Posts Section ---
    st.header("4. View Scheduled Posts")

    if st.button("Refresh Scheduled Posts"):
        with st.spinner("Fetching scheduled posts..."):
            try:
                response = requests.get(GET_SCHEDULED_POSTS_API_URL, params={'user_id': 'demo_user_123'})
                if response.status_code == 200:
                    scheduled_posts = response.json().get('posts', [])
                    if scheduled_posts:
                        st.dataframe(scheduled_posts)
                    else:
                        st.info("No scheduled posts found.")
                else:
                    st.error(f"Error fetching scheduled posts: {response.text}")
            except Exception as e:
                st.error(f"Network error during fetching scheduled posts: {e}")

elif page == "Content Calendar":
    st.title("📅 AI-Generated Content Calendar")
    st.write("Generate a monthly content plan based on your preferences using AI.")

    current_year = datetime.now().year
    current_month = datetime.now().month

    selected_month = st.selectbox(
        "Select Month:",
        options=range(1, 13),
        format_func=lambda x: calendar.month_name[x],
        index=current_month - 1,
        key="calendar_month_select"
    )

    selected_year = st.selectbox(
        "Select Year:",
        options=range(current_year - 2, current_year + 3), # E.g., current year - 2 to current year + 2
        index=2, # Puts current year in the middle if range is 5 years
        key="calendar_year_select"
    )

    business_description = st.text_area(
        "Describe your business/brand (e.g., 'sustainable fashion boutique', 'tech startup for productivity'):",
        height=100,
        key="calendar_business_desc"
    )

    target_audience_calendar = st.text_area(
        "Describe your target audience (e.g., 'Gen Z interested in eco-friendly products', 'small business owners'):",
        height=70,
        key="calendar_target_audience"
    )

    content_themes = st.text_area(
        "Key content themes to include (comma-separated, e.g., 'behind-the-scenes', 'customer testimonials', 'product launches', 'seasonal promotions'):",
        height=70,
        key="calendar_content_themes"
    )

    post_frequency = st.selectbox(
        "Desired Post Frequency:",
        ('Daily', '3 times a week', 'Twice a week', 'Weekly'),
        key="calendar_post_frequency"
    )

    if st.button("Generate Calendar Plan"):
        if not business_description or not target_audience_calendar or not content_themes:
            st.warning("Please provide a description for your business, target audience, and content themes.")
        else:
            calendar_payload = {
                "month": selected_month,
                "year": selected_year,
                "business_description": business_description,
                "target_audience": target_audience_calendar,
                "content_themes": content_themes,
                "post_frequency": post_frequency
            }
            with st.spinner(f"Generating content calendar for {calendar.month_name[selected_month]} {selected_year}..."):
                try:
                    response = requests.post(GENERATE_CALENDAR_API_URL, json=calendar_payload)
                    if response.status_code == 200:
                        st.session_state['generated_calendar'] = response.json().get('calendar_plan')
                        if st.session_state['generated_calendar']:
                            st.subheader(f"Content Calendar for {calendar.month_name[selected_month]} {selected_year}:")
                            # Display as markdown for better readability of bullet points etc.
                            st.markdown(st.session_state['generated_calendar'])
                        else:
                            st.warning("AI could not generate a calendar plan. Please refine your inputs.")
                    else:
                        st.error(f"Error generating calendar: {response.text}")
                        st.session_state['generated_calendar'] = None
                except Exception as e:
                    st.error(f"Network error during calendar generation: {e}")
                    st.session_state['generated_calendar'] = None

    if st.session_state['generated_calendar']:
        st.subheader("Generated Calendar Preview:")
        st.markdown(st.session_state['generated_calendar'])
