import os
import time
import requests
import tempfile
import tweepy
from datetime import datetime, timezone
import streamlit as st
from supabase import create_client, Client

# Google API Imports
import googleapiclient.discovery
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

# 1. Supabase Connection Setup
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_SERVICE_KEY"] 
supabase: Client = create_client(url, key)

def execute_twitter_thread(twitter_credentials, thread_text, video_url):
    """
    Telegram URL se video download karke Twitter par seamless thread post karta hai.
    """
    try:
        print("🚀 Starting Twitter Execution Pipeline...")

        # 1. SETUP TWITTER CLIENTS (Dono APIs zaroori hain)
        # Client (v2) - Tweet aur thread post karne ke liye
        client = tweepy.Client(
            consumer_key=twitter_credentials['api_key'],
            consumer_secret=twitter_credentials['api_secret'],
            access_token=twitter_credentials['access_token'],
            access_token_secret=twitter_credentials['access_token_secret']
        )
        
        # API (v1.1) - Sirf Video/Image upload karne ke liye
        auth = tweepy.OAuth1UserHandler(
            twitter_credentials['api_key'], 
            twitter_credentials['api_secret'],
            twitter_credentials['access_token'], 
            twitter_credentials['access_token_secret']
        )
        api = tweepy.API(auth)

        media_id = None

        # 2. DOWNLOAD VIDEO FROM TELEGRAM & UPLOAD TO TWITTER
        if video_url:
            print(f"📥 Downloading video from Telegram node: {video_url[:30]}...")
            # Temp file banayenge taaki server ka storage full na ho
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
                response = requests.get(video_url, stream=True)
                response.raise_for_status() # Agar link tuta ho toh error de dega
                for chunk in response.iter_content(chunk_size=8192):
                    tmp_file.write(chunk)
                tmp_file_path = tmp_file.name
            
            print("📤 Uploading binary chunk to Twitter Servers...")
            # Twitter par video upload ('tweet_video' category zaroori hai)
            media = api.media_upload(tmp_file_path, media_category='tweet_video')
            media_id = media.media_id_string
            
            # Safai - Temp file ko delete kar do
            os.remove(tmp_file_path)
            print("✅ Video Uploaded! Media ID:", media_id)

        # 3. SMART THREAD SPLITTING
        # AI generally tweets ke beech mein do lines ka gap (\n\n) deta hai
        # Hum usko alag-alag strings mein tod lenge
        raw_tweets = [t.strip() for t in thread_text.split('\n\n') if t.strip()]
        
        if not raw_tweets:
            return False, "Thread text is completely empty."

        # 4. POST THE THREAD (EK KE NEECHE EK)
        previous_tweet_id = None
        
        for index, tweet_content in enumerate(raw_tweets):
            print(f"🐦 Posting Tweet {index + 1}/{len(raw_tweets)}...")
            
            # Pehla Tweet (Isme Video Atttached hoga)
            if index == 0:
                kwargs = {"text": tweet_content[:280]} # Safety boundary
                if media_id:
                    kwargs["media_ids"] = [media_id]
                
                response = client.create_tweet(**kwargs)
                previous_tweet_id = response.data['id']
                
            # Baaki ke Tweets (Isme previous tweet ka ID link hoga jisse chain banegi)
            else:
                response = client.create_tweet(
                    text=tweet_content[:280],
                    in_reply_to_tweet_id=previous_tweet_id
                )
                previous_tweet_id = response.data['id']

        return True, f"✅ Thread successfully published! Root ID: {previous_tweet_id}"

    except Exception as e:
        error_msg = f"❌ Twitter Execution Failed: {str(e)}"
        print(error_msg)
        return False, error_msg

# 🔄 NAYA BADLAV: Ab hum parameter mein 'user_refresh_token' le rahe hain
def upload_to_youtube(video_path, title, description, user_refresh_token):
    """YouTube API ke through actual video upload logic"""
    
    # 🔄 NAYA BADLAV: Ab ye kisi fixed secret se nahi balki user ke personal token se connect hoga
    creds = Credentials(
        None,
        refresh_token=user_refresh_token, 
        token_uri="https://oauth2.googleapis.com/token",
        client_id=st.secrets["GOOGLE_CLIENT_ID"],
        client_secret=st.secrets["GOOGLE_CLIENT_SECRET"]
    )
    
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)
    
    # YouTube Video Metadata (Title, Description, Tags)
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["Shorts", "AI", "CreatorOS"],
            "categoryId": "28" # 28 = Science & Technology
        },
        "status": {
            "privacyStatus": "private", 
            "selfDeclaredMadeForKids": False
        }
    }
    
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    
    response = request.execute()
    return response.get("id")

def process_queue():
    """Database check karta hai aur pending videos upload karta hai"""
    current_utc_time = datetime.now(timezone.utc).isoformat()
    print(f"[{datetime.now()}] 🔍 Checking database for pending videos scheduled up to now...")
    
    try:
        response = supabase.table("master_scheduler_queue") \
            .select("*") \
            .eq("status", "pending") \
            .lte("scheduled_time", current_utc_time) \
            .execute()
        tasks = response.data
    except Exception as e:
        print(f"Database error: {e}")
        return

    if not tasks:
        print("📭 No pending videos found. All caught up!")
        return

    for task in tasks:
        platforms = task.get('target_platforms', [])
        if "youtube" not in [p.lower() for p in platforms]:
            continue

        print(f"\n🚀 Processing Task ID: {task['id']} for YouTube...")
        temp_vid_path = ""
        
        try:
            vid_url = task['video_url']
            meta = task['metadata_payload']
            creator_email = task['creator_handle'] 
            
            # 🔄 NAYA BADLAV: Supabase se is specific user ka YouTube Refresh Token nikalna
            # NOTE: Agar tumhare 'creator_profiles' table mein column ka naam alag hai, toh 'youtube_token' ko change kar lena.
            profile_res = supabase.table("creator_profiles").select("youtube_token").eq("creator_handle", creator_email).execute()
            
            if not profile_res.data or not profile_res.data[0].get("youtube_token"):
                raise ValueError(f"No YouTube refresh token found in database for user: {creator_email}")
                
            user_specific_token = profile_res.data[0]["youtube_token"]

            print("📥 Downloading video from Telegram vault...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_vid:
                r = requests.get(vid_url, stream=True)
                for chunk in r.iter_content(chunk_size=8192):
                    temp_vid.write(chunk)
                temp_vid_path = temp_vid.name
            
            print("☁️ Uploading to YouTube servers...")
            yt_title = meta.get("video_title", "Creator OS Generated Video")
            yt_desc = meta.get("youtube_description", "")
            
            # 🔄 NAYA BADLAV: Function mein user ka specific token pass kar rahe hain
            yt_id = upload_to_youtube(temp_vid_path, yt_title, yt_desc, user_specific_token)
            print(f"✅ Success! YouTube Video ID: {yt_id}")
            
            supabase.table("master_scheduler_queue").delete().eq("id", task["id"]).execute()
            print("🗄️ Database status updated to 'published'.")
            
        except Exception as e:
            print(f"❌ Error processing task {task['id']}: {str(e)}")
            supabase.table("master_scheduler_queue").update({"status": "failed"}).eq("id", task["id"]).execute()
            
        finally:
            if os.path.exists(temp_vid_path):
                os.remove(temp_vid_path)
                print("🧹 Temporary files cleaned up.")

if __name__ == "__main__":
    print("🚀 Creator OS Background Worker started! Polling database every 60 seconds...")
    while True:
        try:
            process_queue()
        except Exception as e:
            print(f"⚠️ Unexpected error in main loop: {e}")
        time.sleep(60)