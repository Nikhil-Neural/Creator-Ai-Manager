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

def upload_to_youtube(video_path, title, description):
    """YouTube API ke through actual video upload logic"""
    # Auto-generate fresh access token using your saved refresh token
    creds = Credentials(
        None,
        refresh_token=st.secrets["YOUTUBE_REFRESH_TOKEN"],
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
            "privacyStatus": "private", # Testing ke liye pehle 'private' rakhte hain. Baad mein 'public' kar lenge!
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
    
    # 2. Database se pending YouTube tasks uthana (RLS bypass ke liye supabase client admin role pe hona chahiye)
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

    # 3. Har pending task ko process karna
    for task in tasks:
        # Platform check (Sirf YouTube process karega abhi)
        # Note: Hum array (JSON) se strictly platform match kar rahe hain
        platforms = task.get('target_platforms', [])
        if "youtube" not in [p.lower() for p in platforms]:
            continue

        print(f"\n🚀 Processing Task ID: {task['id']} for YouTube...")
        temp_vid_path = ""
        
        try:
            vid_url = task['video_url']
            meta = task['metadata_payload']
            
            # Step A: Telegram se file ko temporarily download karna (Server memory mein)
            print("📥 Downloading video from Telegram vault...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_vid:
                r = requests.get(vid_url, stream=True)
                for chunk in r.iter_content(chunk_size=8192):
                    temp_vid.write(chunk)
                temp_vid_path = temp_vid.name
            
            # Step B: YouTube par upload marna
            print("☁️ Uploading to YouTube servers...")
            yt_title = meta.get("video_title", "Creator OS Generated Video")
            yt_desc = meta.get("youtube_description", "")
            
            yt_id = upload_to_youtube(temp_vid_path, yt_title, yt_desc)
            print(f"✅ Success! YouTube Video ID: {yt_id}")
            
            # Step C: Database mein status update karna (Taki dobara upload na ho)
            supabase.table("master_scheduler_queue").delete().eq("id", task["id"]).execute()
            print("🗄️ Database status updated to 'published'.")
            
        except Exception as e:
            print(f"❌ Error processing task {task['id']}: {str(e)}")
            # Agar fail ho jaye toh database ko bata do
            supabase.table("master_scheduler_queue").update({"status": "failed"}).eq("id", task["id"]).execute()
            
        finally:
            # Step D: Kachra saaf karna (Temporary video file delete karna)
            if os.path.exists(temp_vid_path):
                os.remove(temp_vid_path)
                print("🧹 Temporary files cleaned up.")

if __name__ == "__main__":
    print("🚀 Creator OS Background Worker started! Polling database every 60 seconds...")
    
    # Ye 'while True' loop script ko hamesha zinda rakhega
    while True:
        try:
            process_queue()
        except Exception as e:
            print(f"⚠️ Unexpected error in main loop: {e}")
            
        # Har check ke baad 60 seconds (1 minute) ka rest lo, fir dobara check karo
        # Tum isko 300 (5 minutes) bhi kar sakte ho database bachaane ke liye
        time.sleep(60)