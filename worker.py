import os
import time
import requests
import tempfile
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