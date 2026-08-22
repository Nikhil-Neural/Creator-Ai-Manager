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

        client = tweepy.Client(
            consumer_key=twitter_credentials['api_key'],
            consumer_secret=twitter_credentials['api_secret'],
            access_token=twitter_credentials['access_token'],
            access_token_secret=twitter_credentials['access_token_secret']
        )
        
        auth = tweepy.OAuth1UserHandler(
            twitter_credentials['api_key'], 
            twitter_credentials['api_secret'],
            twitter_credentials['access_token'], 
            twitter_credentials['access_token_secret']
        )
        api = tweepy.API(auth)

        media_id = None

        if video_url:
            print(f"📥 Downloading video from Telegram node: {video_url[:30]}...")
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
                response = requests.get(video_url, stream=True, timeout=60)
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=8192):
                    tmp_file.write(chunk)
                tmp_file_path = tmp_file.name
            
            print("📤 Uploading binary chunk to Twitter Servers...")
            media = api.media_upload(tmp_file_path, media_category='tweet_video')
            media_id = media.media_id_string
            
            os.remove(tmp_file_path)
            print("✅ Video Uploaded! Media ID:", media_id)

        raw_tweets = [t.strip() for t in thread_text.split('\n\n') if t.strip()]
        if not raw_tweets:
            return False, "Thread text is completely empty."

        previous_tweet_id = None
        for index, tweet_content in enumerate(raw_tweets):
            print(f"🐦 Posting Tweet {index + 1}/{len(raw_tweets)}...")
            if index == 0:
                kwargs = {"text": tweet_content[:280]}
                if media_id:
                    kwargs["media_ids"] = [media_id]
                response = client.create_tweet(**kwargs)
                previous_tweet_id = response.data['id']
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

def upload_to_youtube(video_path, title, description, user_refresh_token):
    """YouTube API ke through actual video upload logic"""
    creds = Credentials(
        None,
        refresh_token=user_refresh_token, 
        token_uri="https://oauth2.googleapis.com/token",
        client_id=st.secrets["GOOGLE_CLIENT_ID"],
        client_secret=st.secrets["GOOGLE_CLIENT_SECRET"]
    )
    
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)
    
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["Shorts", "AI", "CreatorOS"],
            "categoryId": "28"
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

def upload_to_instagram(video_url, caption, access_token):
    """Meta Graph API v20.0 integration for Instagram Reels."""
    base_url = "https://graph.facebook.com/v20.0"

    try:
        pages_url = f"{base_url}/me/accounts?access_token={access_token}"
        pages_res = requests.get(pages_url, timeout=30).json()

        if "error" in pages_res:
            return False, f"Meta Auth Error: {pages_res['error']['message']}"
        if not pages_res.get("data"):
            return False, "No Facebook Pages found linked to this account."

        ig_user_id = None
        for page in pages_res["data"]:
            page_id = page["id"]
            ig_req = requests.get(f"{base_url}/{page_id}?fields=instagram_business_account&access_token={access_token}", timeout=30).json()
            if "instagram_business_account" in ig_req:
                ig_user_id = ig_req["instagram_business_account"]["id"]
                break

        if not ig_user_id:
            return False, "No Instagram Professional Account linked to your Facebook Pages."

        print(f"📦 Creating Instagram Container for ID: {ig_user_id}...")
        container_url = f"{base_url}/{ig_user_id}/media"
        container_payload = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": access_token
        }
        container_res = requests.post(container_url, data=container_payload, timeout=30).json()

        if "error" in container_res:
            return False, f"Container Error: {container_res['error']['message']}"

        creation_id = container_res.get("id")
        print(f"⏳ Container created (ID: {creation_id}). Waiting for Meta to process video...")

        status_url = f"{base_url}/{creation_id}?fields=status_code&access_token={access_token}"
        max_attempts = 15
        for attempt in range(max_attempts):
            time.sleep(10)
            status_res = requests.get(status_url, timeout=30).json()
            if "error" in status_res:
                return False, f"Status Check Error: {status_res['error']['message']}"

            status = status_res.get("status_code")
            print(f"🔄 Meta Processing Status: {status} (Attempt {attempt+1}/{max_attempts})")

            if status == "FINISHED":
                break
            elif status == "ERROR":
                return False, "Meta failed to process the video internally."

        print("🚀 Meta processing complete! Publishing Reel now...")
        publish_url = f"{base_url}/{ig_user_id}/media_publish"
        publish_payload = {
            "creation_id": creation_id,
            "access_token": access_token
        }
        publish_res = requests.post(publish_url, data=publish_payload, timeout=30).json()

        if "error" in publish_res:
            return False, f"Publishing Error: {publish_res['error']['message']}"

        return True, f"Instagram Reel successfully published! Post ID: {publish_res.get('id')}"

    except Exception as e:
        return False, f"Unexpected Meta Logic Error: {str(e)}"

def upload_to_facebook(video_url, caption, user_access_token):
    """Meta Graph API v20.0 integration for Facebook Pages."""
    base_url = "https://graph.facebook.com/v20.0"

    try:
        pages_url = f"{base_url}/me/accounts?access_token={user_access_token}"
        pages_res = requests.get(pages_url, timeout=30).json()

        if "error" in pages_res:
            return False, f"Meta Auth Error: {pages_res['error']['message']}"
        if not pages_res.get("data"):
            return False, "No Facebook Pages found linked to this account."

        page_data = pages_res["data"][0]
        page_id = page_data["id"]
        page_token = page_data["access_token"]
        page_name = page_data["name"]

        print(f"📘 Authenticated Facebook Page: {page_name} (ID: {page_id})")
        print(f"📤 Uploading & Publishing video to Facebook Page: {page_name}...")
        video_post_url = f"{base_url}/{page_id}/videos"
        
        payload = {
            "file_url": video_url,
            "description": caption,
            "access_token": page_token
        }
        
        publish_res = requests.post(video_post_url, data=payload, timeout=60).json()

        if "error" in publish_res:
            return False, f"Facebook Publish Error: {publish_res['error']['message']}"

        video_id = publish_res.get("id")
        return True, f"Facebook Video successfully published! Video ID: {video_id}"

    except Exception as e:
        return False, f"Unexpected Facebook Logic Error: {str(e)}"

# 🧵 MASTER THREADS ENGINE (Chain/Chreading Enabled)
# 🧵 MASTER THREADS ENGINE (Chain/Chreading Enabled)
def upload_to_threads(video_url, thread_text, access_token):
    """
    Threads Graph API Integration for chained posts (Twitter/X Style).
    API Endpoint: graph.threads.net/v1.0
    """
    base_url = "https://graph.threads.net/v1.0"
    
    try:
        raw_posts = [t.strip() for t in thread_text.split('\n\n') if t.strip()]
        if not raw_posts:
            return False, "Threads text is empty."

        # Fetch Threads User ID
        me_res = requests.get(f"{base_url}/me?fields=id,username&access_token={access_token}", timeout=30).json()
        if "error" in me_res:
            return False, f"Threads Auth Error: {me_res['error'].get('message', 'Unknown')}"
        threads_user_id = me_res.get("id")
        print(f"🧵 Authenticated Threads User: @{me_res.get('username')} (ID: {threads_user_id})")

        previous_post_id = None

        for index, post_content in enumerate(raw_posts):
            print(f"🧵 Building Thread part {index + 1}/{len(raw_posts)}...")
            
            container_payload = {
                "text": post_content[:500],
                "access_token": access_token
            }

            # Pehla item video ke sath
            if index == 0 and video_url:
                container_payload["media_type"] = "VIDEO"
                container_payload["video_url"] = video_url
            else:
                container_payload["media_type"] = "TEXT"
                if previous_post_id:
                    container_payload["reply_to_id"] = previous_post_id

            # 🛡️ SAFE CONTAINER CREATION
            container_req = requests.post(f"{base_url}/{threads_user_id}/threads", data=container_payload, timeout=30)
            try:
                container_res = container_req.json()
            except Exception:
                return False, f"Meta crashed during Container build! Raw Server Response: {container_req.text}"
                
            if "error" in container_res:
                return False, f"Threads Container Error: {container_res['error'].get('message', 'Unknown')}"
            
            creation_id = container_res.get("id")

            # Video Processing Status Polling (Sirf Video wale container ke liye)
            if index == 0 and video_url:
                print(f"⏳ Waiting for Threads to encode video (ID: {creation_id})...")
                status_url = f"{base_url}/{creation_id}?fields=status,error_message&access_token={access_token}"
                
                is_finished = False
                for attempt in range(15):
                    time.sleep(10)
                    status_res = requests.get(status_url, timeout=30).json()
                    status = status_res.get("status")
                    print(f"🔄 Threads Processing Status: {status} (Attempt {attempt+1}/15)")
                    
                    if status == "FINISHED":
                        is_finished = True
                        break
                    elif status == "ERROR":
                        err_detail = status_res.get("error_message", "Encoding failed")
                        return False, f"Threads Video Encoding Failed: {err_detail}"
                
                if not is_finished:
                    return False, "Threads video processing timed out after 2.5 minutes."

            # 🛡️ SAFE PUBLISH CREATION
            print(f"🚀 Publishing Thread part {index + 1}...")
            publish_payload = {
                "creation_id": creation_id,
                "access_token": access_token
            }
            publish_req = requests.post(f"{base_url}/{threads_user_id}/threads_publish", data=publish_payload, timeout=30)
            
            try:
                publish_res = publish_req.json()
            except Exception:
                return False, f"Meta crashed during Publish! Raw Server Response: {publish_req.text}"

            if "error" in publish_res:
                return False, f"Threads Publish Error: {publish_res['error'].get('message', 'Unknown')}"
            
            previous_post_id = publish_res.get("id")
            print(f"✅ Published Thread part {index+1}! Post ID: {previous_post_id}")
            
            # 🚀 THE FIX: Meta ko global database sync karne ke liye extra time dena
            print("⏳ Giving Meta time to index this post before replying...")
            time.sleep(15) 

        return True, f"✅ Full Threads Chain published successfully! Root ID: {previous_post_id}"

    except Exception as e:
        return False, f"Unexpected Threads Error: {str(e)}"

def process_queue():
    """Database check karta hai aur pending videos upload karta hai"""
    current_utc_time = datetime.now(timezone.utc).isoformat()
    print(f"[{datetime.now()}] 🔍 Checking database for pending videos scheduled up to now...")
    
    try:
        response = supabase.table("master_scheduler_queue") \
            .select("*") \
            .in_("status", ["Pending", "pending"]) \
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
        platforms = [p.lower() for p in task.get('target_platforms', [])]
        print(f"\n🚀 Processing Task ID: {task['id']} for platforms: {platforms}")
        
        try:
            vid_url = task['video_url']
            meta = task['metadata_payload']
            creator_email = task['creator_handle']
            
            # --- YOUTUBE LOGIC ---
            if "youtube" in platforms:
                print("📺 Starting YouTube sequence...")
                temp_vid_path = ""
                profile_res = supabase.table("creator_profiles").select("youtube_token").eq("creator_handle", creator_email).execute()
                
                if not profile_res.data or not profile_res.data[0].get("youtube_token"):
                    print(f"⚠️ Skipping YT: No YouTube refresh token found for {creator_email}")
                else:
                    user_specific_token = profile_res.data[0]["youtube_token"]
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_vid:
                        r = requests.get(vid_url, stream=True, timeout=60)
                        for chunk in r.iter_content(chunk_size=8192):
                            temp_vid.write(chunk)
                        temp_vid_path = temp_vid.name
                    
                    yt_title = meta.get("video_title", "Creator OS Generated Video")
                    yt_desc = meta.get("youtube_description", "")
                    
                    yt_id = upload_to_youtube(temp_vid_path, yt_title, yt_desc, user_specific_token)
                    print(f"✅ Success! YouTube Video ID: {yt_id}")
                    
                    if os.path.exists(temp_vid_path):
                        os.remove(temp_vid_path)

            # --- TWITTER LOGIC ---
            if "twitter" in platforms:
                print("🐦 Starting Twitter sequence...")
                tw_profile_res = supabase.table("creator_profiles").select("twitter_token, twitter_access_secret").eq("creator_handle", creator_email).execute()
                
                if not tw_profile_res.data or not tw_profile_res.data[0].get("twitter_token"):
                    print(f"⚠️ Skipping Twitter: No connected X account found for {creator_email}")
                else:
                    user_tokens = tw_profile_res.data[0]
                    twitter_credentials = {
                        "api_key": st.secrets["TWITTER_API_KEY"],
                        "api_secret": st.secrets["TWITTER_API_SECRET"],
                        "access_token": user_tokens.get("twitter_token"),
                        "access_token_secret": user_tokens.get("twitter_access_secret")
                    }
                    thread_text = meta.get("twitter_thread_text", "")
                    success, msg = execute_twitter_thread(twitter_credentials, thread_text, vid_url)
                    
                    if success:
                        print(f"✅ {msg}")
                    else:
                        print(f"❌ {msg}")
                        raise Exception(f"Twitter Execution Failed: {msg}")

            # --- META (INSTAGRAM) LOGIC ---
            if "instagram" in platforms or "meta" in platforms:
                print("♾️ Starting Meta (Instagram) sequence...")
                profile_res = supabase.table("creator_profiles").select("instagram_token").eq("creator_handle", creator_email).execute()
                
                if not profile_res.data or not profile_res.data[0].get("instagram_token"):
                    print(f"⚠️ Skipping Meta: No valid Meta token found for {creator_email}")
                else:
                    ig_token = profile_res.data[0]["instagram_token"]
                    ig_caption = meta.get("instagram_caption", "Powered by AI Creator OS 🚀")
                    success, msg = upload_to_instagram(vid_url, ig_caption, ig_token)
                    
                    if success:
                        print(f"✅ {msg}")
                    else:
                        print(f"❌ {msg}")
                        raise Exception(f"Meta Execution Failed: {msg}")

            # --- FACEBOOK LOGIC ---
            if "facebook" in platforms:
                print("📘 Starting Facebook sequence...")
                profile_res = supabase.table("creator_profiles").select("facebook_token").eq("creator_handle", creator_email).execute()
                
                if not profile_res.data or not profile_res.data[0].get("facebook_token"):
                    print(f"⚠️ Skipping FB: No valid Facebook token found for {creator_email}")
                else:
                    fb_token = profile_res.data[0]["facebook_token"]
                    fb_caption = meta.get("facebook_post_text", "Powered by AI Creator OS 🚀")
                    success, msg = upload_to_facebook(vid_url, fb_caption, fb_token)
                    
                    if success:
                        print(f"✅ {msg}")
                    else:
                        print(f"❌ {msg}")
                        raise Exception(f"Facebook Execution Failed: {msg}")

            # --- THREADS LOGIC (Clean Independent Block) ---
            if "threads" in platforms:
                print("🧵 Starting Threads sequence...")
                profile_res = supabase.table("creator_profiles").select("threads_token").eq("creator_handle", creator_email).execute()
                
                if not profile_res.data or not profile_res.data[0].get("threads_token"):
                    print(f"⚠️ Skipping Threads: No valid token found for {creator_email}")
                else:
                    th_token = profile_res.data[0]["threads_token"]
                    th_caption = meta.get("threads_content", "Powered by AI Creator OS 🚀")
                    success, msg = upload_to_threads(vid_url, th_caption, th_token)
                    
                    if success:
                        print(f"✅ {msg}")
                    else:
                        print(f"❌ {msg}")
                        raise Exception(f"Threads Execution Failed: {msg}")

            # Task successfully processed -> Remove from queue
            supabase.table("master_scheduler_queue").delete().eq("id", task["id"]).execute()
            print("🗄️ Task deleted from queue (successfully published).")
            
        except Exception as e:
            print(f"❌ Error processing task {task['id']}: {str(e)}")
            supabase.table("master_scheduler_queue").update({"status": "Failed"}).eq("id", task["id"]).execute()

if __name__ == "__main__":
    print("🚀 Creator OS Background Worker started! Polling database every 60 seconds...")
    while True:
        try:
            process_queue()
        except Exception as e:
            print(f"⚠️ Unexpected error in main loop: {e}")
        time.sleep(60)