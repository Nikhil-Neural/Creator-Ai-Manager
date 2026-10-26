import os
import time
import requests
import tempfile
import tweepy
import streamlit as st
from supabase import create_client, Client
from storage_engine import generate_presigned_url
from datetime import datetime, timezone, timedelta
# Google API Imports
import googleapiclient.discovery
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload


# 1. Single production database connection. Configure SUPABASE_URL and
# SUPABASE_SERVICE_KEY in Streamlit secrets for the deployed app.
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_SERVICE_KEY"]

supabase: Client = create_client(url, key)

# Real publishing is enabled by default. Do not set this to True in production.
DRY_RUN = False
SUPPORTED_PLATFORMS = {"youtube", "twitter", "instagram", "meta", "facebook", "threads", "linkedin"}

def has_uncertain_publish_state(platform_statuses):
    """True if any platform may have accepted a publish request without confirmation."""
    if not isinstance(platform_statuses, dict):
        return False
    uncertain = {"publishing", "outcome_unknown"}
    return any(
        isinstance(status, str) and status.strip().lower() in uncertain
        for status in platform_statuses.values()
    )

def finalize_exhausted_task(task_id, retry_count, platform_statuses, error_message):
    """
    Mark retries-exhausted task as Permanent_Fail.
    Delete only when no platform is published or uncertain.
    Keep partial-success rows for audit.
    """
    try:
        permanent_result = (
            supabase.table("master_scheduler_queue")
            .update({
                "status": "Permanent_Fail",
                "platform_statuses": platform_statuses,
                "retry_count": retry_count,
                "last_error": str(error_message)[:5000],
            })
            .eq("id", task_id)
            .eq("status", "Processing")
            .select("id")
            .execute()
        )

        if not permanent_result.data:
            print(
                f"🚨 Permanent_Fail not confirmed for task {task_id}. "
                "Row retained; manual DB check required."
            )
            return

        print(f"✅ Task {task_id} marked Permanent_Fail.")

        # Never delete if any platform's publish outcome is uncertain.
        if has_uncertain_publish_state(platform_statuses):
            print(
                f"🛑 Task {task_id} has uncertain publish state. "
                "Retaining row for review."
            )
            return

        # Preserve the audit record if any platform succeeded.
        statuses = (
            platform_statuses
            if isinstance(platform_statuses, dict)
            else {}
        )
        published = any(
            isinstance(status, str)
            and status.strip().lower() in {"published", "success"}
            for status in statuses.values()
        )

        if published:
            print(
                f"📋 Task {task_id} partially published. "
                "Permanent_Fail row retained for audit."
            )
            return

        # Delete only after Permanent_Fail was confirmed and no
        # platform is published or uncertain.
        delete_result = (
            supabase.table("master_scheduler_queue")
            .delete()
            .eq("id", task_id)
            .eq("status", "Permanent_Fail")
            .eq("retry_count", retry_count)
            .select("id")
            .execute()
        )

        if delete_result.data:
            print(
                f"🗑️ Exhausted task {task_id} deleted from queue."
            )
        else:
            print(
                f"⚠️ Cleanup not confirmed for task {task_id}. "
                "Check the database manually."
            )

    except Exception as e:
        print(
            f"🚨 Could not finalize task {task_id}: {e}. "
            "Check database state manually."
        )

def download_video_safe(vid_url, max_size_mb=250):
    """
    R2/Network se safely video download karta hai 250MB limit ke sath.
    """
    max_bytes = max_size_mb * 1024 * 1024
    downloaded_bytes = 0
    
    temp_vid = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    temp_vid_path = temp_vid.name
    
    try:
        r = requests.get(vid_url, stream=True, timeout=60)
        r.raise_for_status()
        
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                downloaded_bytes += len(chunk)
                if downloaded_bytes > max_bytes:
                    temp_vid.close()
                    os.remove(temp_vid_path)
                    raise Exception(f"Download size exceeded {max_size_mb}MB limit.")
                temp_vid.write(chunk)
                
        temp_vid.close()
        return temp_vid_path
    except Exception as e:
        if os.path.exists(temp_vid_path):
            os.remove(temp_vid_path)
        raise e

def execute_twitter_thread(twitter_credentials, thread_text, video_url):
    
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
        tmp_file_path = None

        if video_url:
            print("📥 Downloading video for Twitter...")
            try:
                # 🚨 FIX: Purana requests.get block deleted. Direct safe downloader use kiya hai.
                tmp_file_path = download_video_safe(video_url)
                
                print("📤 Uploading binary chunk to Twitter Servers...")
                media = api.media_upload(tmp_file_path, media_category='tweet_video')
                media_id = media.media_id_string
                print("✅ Video Uploaded! Media ID:", media_id)
            finally:
                if tmp_file_path and os.path.exists(tmp_file_path):
                    os.remove(tmp_file_path)
                    print("🧹 Temporary Twitter video file cleaned up.")

        # [Iske aage ka thread posting wala code (raw_tweets loop) same rahega...]

        raw_tweets = [t.strip() for t in thread_text.split('\n\n') if t.strip()]
        if not raw_tweets:
            return False, "Thread text is completely empty."

        previous_tweet_id = None
        
        for index, tweet_content in enumerate(raw_tweets):
            print(f"Posting tweet {index + 1}/{len(raw_tweets)}...")

            try:
                if index == 0:
                    kwargs = {"text": tweet_content[:280]}
                    if media_id:
                        kwargs["media_ids"] = [media_id]

                    response = client.create_tweet(**kwargs)
                else:
                    response = client.create_tweet(
                        text=tweet_content[:280],
                        in_reply_to_tweet_id=previous_tweet_id
                    )

                previous_tweet_id = response.data["id"]

            except Exception as e:
                raise PublishOutcomeUnknown(
                    f"X/Twitter thread post {index + 1}/{len(raw_tweets)} "
                    "may have been published, or earlier posts may already be live. "
                    "Automatic retry is unsafe; manual review required. "
                    f"Details: {e}"
                ) from e


        return True, f"✅ Thread successfully published! Root ID: {previous_tweet_id}"

    except PublishOutcomeUnknown:
        raise

    except Exception as e:
        error_msg = f"❌ Twitter Execution Failed: {str(e)}"
        print(error_msg)
        return False, error_msg

def upload_to_youtube(video_path, meta, user_refresh_token):
    """
    YouTube API v3 Upload Engine with Advanced Payload Controls.
    """
    creds = Credentials(
        None,
        refresh_token=user_refresh_token, 
        token_uri="https://oauth2.googleapis.com/token",
        client_id=st.secrets["GOOGLE_CLIENT_ID"],
        client_secret=st.secrets["GOOGLE_CLIENT_SECRET"]
    )
    
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)
    
    # ⚙️ EXTRACTING ADVANCED METADATA
    title = meta.get("video_title", "Creator OS Generated Video")
    description = meta.get("youtube_description", "")
    is_kids = meta.get("yt_is_kids", False) # False by default
    show_likes = meta.get("yt_show_likes", True) # False hides likes
    video_lang = meta.get("yt_language", "en-US") # Language Code
    privacy = meta.get("yt_privacy", "private") # public, private, or unlisted
    
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["Shorts", "AI", "CreatorOS"],
            "categoryId": "28",
            "defaultLanguage": video_lang,
            "defaultAudioLanguage": video_lang
        },
        "status": {
            "privacyStatus": privacy, 
            "selfDeclaredMadeForKids": is_kids,
            "publicStatsViewable": show_likes  # True = Show Likes, False = Hide Likes
        }
    }
    
    
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    try:
        response = request.execute()
    except Exception as e:
        # The upload outcome may be unknown. Do not blindly retry.
        raise PublishOutcomeUnknown(
            f"YouTube upload outcome could not be confirmed: {e}"
        ) from e

    video_id = response.get("id") if isinstance(response, dict) else None

    if not video_id:
        raise PublishOutcomeUnknown(
            "YouTube returned no video ID; upload outcome is uncertain."
        )

    
    # 🔗 GENERATE STUDIO REDIRECT LINK
    studio_edit_link = f"https://studio.youtube.com/video/{video_id}/edit"
    print(f"🎬 YouTube Studio Setup Link: {studio_edit_link}")
    
    return video_id

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
        is_finished = False
        for attempt in range(max_attempts):
            time.sleep(10)
            status_res = requests.get(status_url, timeout=30).json()
            if "error" in status_res:
                return False, f"Status Check Error: {status_res['error']['message']}"

            status = status_res.get("status_code")
            print(f"🔄 Meta Processing Status: {status} (Attempt {attempt+1}/{max_attempts})")

            if status == "FINISHED":
                is_finished = True
                break
            elif status == "ERROR":
                return False, "Meta failed to process the video internally."

        if not is_finished:
            return False, "Instagram video processing timed out."

        
        print("🚀 Meta processing complete! Publishing Reel now...")
        publish_url = f"{base_url}/{ig_user_id}/media_publish"
        publish_payload = {
            "creation_id": creation_id,
            "access_token": access_token
        }

        try:
            publish_response = requests.post(
                publish_url,
                data=publish_payload,
                timeout=30
            )
        except requests.RequestException as e:
            raise PublishOutcomeUnknown(
                "Instagram publish request failed or timed out. "
                "The Reel may already be live; automatic retry is unsafe. "
                f"Details: {e}"
            ) from e

        try:
            publish_res = publish_response.json()
        except ValueError as e:
            raise PublishOutcomeUnknown(
                "Instagram publish response was not valid JSON. "
                "The Reel may already be live; manual review required."
            ) from e

        if "error" in publish_res:
            return False, f"Publishing Error: {publish_res['error']['message']}"

        if not publish_res.get("id"):
            raise PublishOutcomeUnknown(
                "Instagram publish response did not contain a post ID. "
                "The Reel may already be live; manual review required."
            )

        return True, f"Instagram Reel successfully published! Post ID: {publish_res['id']}"

    except PublishOutcomeUnknown:
        raise

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
        
        
        try:
            publish_response = requests.post(
                video_post_url,
                data=payload,
                timeout=60
            )
        except requests.RequestException as e:
            raise PublishOutcomeUnknown(
                "Facebook publish request failed or timed out. "
                "The video may already be live; automatic retry is unsafe. "
                f"Details: {e}"
            ) from e

        try:
            publish_res = publish_response.json()
        except ValueError as e:
            raise PublishOutcomeUnknown(
                "Facebook publish response was not valid JSON. "
                "The video may already be live; manual review required."
            ) from e

        if "error" in publish_res:
            return False, f"Facebook Publish Error: {publish_res['error']['message']}"

        video_id = publish_res.get("id")
        if not video_id:
            raise PublishOutcomeUnknown(
                "Facebook publish response did not contain a video ID. "
                "The video may already be live; manual review required."
            )

        return True, f"Facebook Video successfully published! Video ID: {video_id}"

    except PublishOutcomeUnknown:
        raise

    except Exception as e:
        return False, f"Unexpected Facebook Logic Error: {str(e)}"


# 🧵 MASTER THREADS ENGINE (Chain/Chreading Enabled) - FULLY CLEANED
def upload_to_threads(video_url, thread_text, access_token):
    """
    Threads Graph API Integration for chained posts.
    With Meta Sync Ping Verification & JSON Payload parsing.
    """
    base_url = "https://graph.threads.net/v1.0"
    
    published_any = False
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
            
            # 🛡️ THE JSON FIX: Payload
            container_payload = {
                "text": post_content[:490]
            }

            if index == 0 and video_url:
                container_payload["media_type"] = "VIDEO"
                container_payload["video_url"] = video_url
            else:
                container_payload["media_type"] = "TEXT"
                if previous_post_id:
                    container_payload["reply_to_id"] = str(previous_post_id)

            # 🚀 Token URL Query Parameter
            auth_params = {"access_token": access_token}

            # Container Creation with JSON
            container_res = None
            for retry in range(3):
                container_req = requests.post(f"{base_url}/{threads_user_id}/threads", params=auth_params, json=container_payload, timeout=30)
                try:
                    container_res = container_req.json()
                    if "error" not in container_res:
                        break # Success
                except Exception:
                    pass
                
                print(f"⚠️ Meta API choked on Container. Retrying {retry+1}/3 in 20s...")
                time.sleep(20)
                    
            
            if not container_res or "error" in container_res:
                err_msg = (
                    container_res.get("error", {}).get("message", "Unknown")
                    if container_res else container_req.text
                )

                if published_any:
                    raise PublishOutcomeUnknown(
                        f"Threads chain is partially published. "
                        f"Part {index + 1} container failed after retries. "
                        f"Previous posts may already be live. "
                        f"Do not retry automatically. Details: {err_msg}"
                    )

                return False, (
                    f"Threads Container Failed after 3 retries: {err_msg}"
                )

            
            creation_id = container_res.get("id")

            # Video Processing Status Polling
            if index == 0 and video_url:
                print(f"⏳ Waiting for Threads to encode video (ID: {creation_id})...")
                status_url = f"{base_url}/{creation_id}?fields=status,error_message&access_token={access_token}"
                
                is_finished = False
                for attempt in range(20): 
                    time.sleep(15)
                    status_res = requests.get(status_url, timeout=30).json()
                    status = status_res.get("status")
                    print(f"🔄 Threads Processing Status: {status} (Attempt {attempt+1}/20)")
                    
                    # 🛡️ THE FIX: Accept both statuses
                    if status in ["FINISHED", "PUBLISHED"]:
                        is_finished = True
                        break
                    elif status == "ERROR":
                        err_detail = status_res.get("error_message", "Encoding failed")
                        return False, f"Threads Video Encoding Failed: {err_detail}"
                
                if not is_finished:
                    return False, "Threads video processing timed out."

            
            # Publish — do not blindly retry an uncertain publish request
            print(f"🚀 Publishing Thread part {index + 1}...")

            publish_payload = {
                "creation_id": creation_id
            }

            try:
                publish_req = requests.post(
                    f"{base_url}/{threads_user_id}/threads_publish",
                    params=auth_params,
                    json=publish_payload,
                    timeout=30
                )
                publish_res = publish_req.json()

            except Exception as e:
                raise PublishOutcomeUnknown(
                    f"Threads part {index + 1}: publish outcome unknown. "
                    f"Do not retry automatically. Details: {e}"
                ) from e

            
            if not isinstance(publish_res, dict):
                raise PublishOutcomeUnknown(
                    f"Threads part {index + 1}: invalid publish response. "
                    "Manual review required; do not retry automatically."
                )

            if "error" in publish_res:
                err_msg = publish_res.get("error", {}).get(
                    "message", "Unknown API error"
                )

                if published_any:
                    raise PublishOutcomeUnknown(
                        f"Threads chain is partially published. "
                        f"Part {index + 1} returned a publish error, "
                        f"but earlier posts may already be live. "
                        f"Do not retry automatically. Details: {err_msg}"
                    )

                return False, f"Threads Publish Error: {err_msg}"


            previous_post_id = publish_res.get("id")

            if not previous_post_id:
                raise PublishOutcomeUnknown(
                    f"Threads part {index + 1}: API response did not "
                    "confirm a post ID. Manual review required."
                )

            print(f"✅ Published Thread part {index+1}! Post ID: {previous_post_id}")
            published_any = True
            
            # 🛡️ PING VERIFICATION
            if index < len(raw_posts) - 1:
                print(f"📡 Pinging Meta global servers to verify Post {previous_post_id} is live before replying...")
                verify_url = f"{base_url}/{previous_post_id}?fields=id&access_token={access_token}"
                
                is_live = False
                for ping in range(6): 
                    time.sleep(20) 
                    verify_res = requests.get(verify_url, timeout=30).json()
                    
                    if "id" in verify_res:
                        print("✅ Meta confirmed post is fully indexed! Safe to attach next reply.")
                        is_live = True
                        break
                    else:
                        print(f"🔄 Meta backend still syncing... Waiting ({ping+1}/6)")
                        
                
                if not is_live:
                    raise PublishOutcomeUnknown(
                        f"Threads part {index + 1} was published, "
                        f"but its availability could not be verified. "
                        f"The next reply was not attempted. "
                        f"Manual review required; do not retry automatically."
                    )


        return True, f"✅ Full Threads Chain published successfully! Root ID: {previous_post_id}"

    
    except PublishOutcomeUnknown:
        raise

    except Exception as e:
        if published_any:
            raise PublishOutcomeUnknown(
                f"Threads chain may be partially published. "
                f"An error occurred after a post was confirmed. "
                f"Do not retry automatically. Details: {e}"
            ) from e

        return False, f"Unexpected Threads Error: {str(e)}"

def upload_to_linkedin(video_path, post_text, access_token):
    """
    LinkedIn 3-Step Video Upload & Publish Logic
    """
    headers = {
        'Authorization': f'Bearer {access_token}',
        'X-Restli-Protocol-Version': '2.0.0'
    }
    
    try:
        # STEP 1: Get User URN (Unique Profile ID)
        
        me_http_response = requests.get(
            'https://api.linkedin.com/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=30
        )

        if me_http_response.status_code != 200:
            try:
                error_data = me_http_response.json()
            except ValueError:
                error_data = {}

            error_message = (
                error_data.get("message")
                if isinstance(error_data, dict)
                else None
            ) or me_http_response.text or (
                f"HTTP {me_http_response.status_code}"
            )

            return False, (
                f"LinkedIn profile lookup failed: {error_message}"
            )

        try:
            me_response = me_http_response.json()
        except ValueError:
            return False, "LinkedIn profile lookup returned invalid JSON."

        if not isinstance(me_response, dict) or not me_response.get("sub"):
            return False, (
                "Auth Error: LinkedIn profile response did not contain a valid user ID."
            )

        
        person_urn = f"urn:li:person:{me_response['sub']}"
        print(f"💼 Authenticated LinkedIn User: {person_urn}")
        
        # STEP 2: Register Video Upload
        print("📦 Registering video upload with LinkedIn servers...")
        register_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-video"],
                "owner": person_urn,
                "serviceRelationships": [{"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}]
            }
        }
        
        
        reg_http_response = requests.post(
            register_url,
            headers=headers,
            json=register_payload,
            timeout=30
        )

        if not 200 <= reg_http_response.status_code < 300:
            try:
                error_data = reg_http_response.json()
            except ValueError:
                error_data = {}

            error_message = (
                error_data.get("message")
                if isinstance(error_data, dict)
                else None
            ) or reg_http_response.text or (
                f"HTTP {reg_http_response.status_code}"
            )

            return False, (
                f"Failed to register video: {error_message}"
            )

        try:
            reg_res = reg_http_response.json()
        except ValueError:
            return False, (
                "LinkedIn video registration returned invalid JSON."
            )

        if not isinstance(reg_res, dict) or "value" not in reg_res:
            return False, f"Failed to register video: {reg_res}"

        try:
            upload_mechanism = reg_res["value"]["uploadMechanism"]
            upload_url = upload_mechanism[
                "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
            ]["uploadUrl"]
            asset_urn = reg_res["value"]["asset"]
        except (KeyError, TypeError):
            return False, (
                "LinkedIn video registration response is missing required upload details."
            )

        
        # STEP 3: Upload Binary Video Data
        print(f"📤 Uploading video binary chunks to LinkedIn (Asset: {asset_urn})...")
        with open(video_path, 'rb') as video_file:
            # 🚨 FIX: Added timeout=300 to prevent infinite freeze
            upload_res = requests.post(upload_url, headers={'Authorization': f'Bearer {access_token}'}, data=video_file, timeout=300)
            if upload_res.status_code not in [200, 201]:
                return False, f"Video upload failed (Status {upload_res.status_code}): {upload_res.text}"
                
        # STEP 4: Publish the Final Post
        print("🚀 Compiling and publishing LinkedIn Post...")
        publish_url = "https://api.linkedin.com/v2/ugcPosts"
        publish_payload = {
            "author": person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": post_text},
                    "shareMediaCategory": "VIDEO",
                    "media": [{"status": "READY", "media": asset_urn}]
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
        }
        
        
        try:
            publish_response = requests.post(
                publish_url,
                headers=headers,
                json=publish_payload,
                timeout=60
            )
        except requests.RequestException as e:
            raise PublishOutcomeUnknown(
                "LinkedIn publish request failed or timed out. "
                "The post may already be live; automatic retry is unsafe. "
                f"Details: {e}"
            ) from e

        
        # LinkedIn publish response handling
        if publish_response.status_code == 201:
            linkedin_post_id = publish_response.headers.get("x-restli-id")

            if linkedin_post_id:
                print("LinkedIn post published successfully.")
                return True, f"LinkedIn post published successfully. Post ID: {linkedin_post_id}"

            # HTTP success, but post ID is missing.
            # Do not automatically retry an uncertain publish.
            raise PublishOutcomeUnknown(
                "LinkedIn returned HTTP 201, but x-restli-id was missing."
            )

        
        # Clear client-side rejection: return a normal failure.
        if 400 <= publish_response.status_code < 500:
            try:
                error_data = publish_response.json()
            except ValueError:
                error_data = {}

            error_message = (
                error_data.get("message")
                if isinstance(error_data, dict)
                else None
            )
            error_message = error_message or publish_response.text or (
                f"HTTP {publish_response.status_code}"
            )

            print(f"LinkedIn API rejected the post: {error_message}")
            return False, f"LinkedIn API rejected the post: {error_message}"

        # A server error or unexpected response may leave the publish
        # outcome uncertain. Do not automatically retry blindly.
        raise PublishOutcomeUnknown(
            f"LinkedIn publish outcome is uncertain. "
            f"HTTP status: {publish_response.status_code}"
        )

    except PublishOutcomeUnknown:
        raise

    except Exception as e:
        return False, f"Unexpected LinkedIn Error: {str(e)}"

class InvalidTaskError(ValueError):
    """Task data is invalid and should not be retried automatically."""
    pass


class PlatformStatusSaveError(RuntimeError):
    """Publish may have succeeded, but status persistence was not confirmed."""
    pass

class PublishOutcomeUnknown(RuntimeError):
    """Publish request may have succeeded, but its outcome is unknown."""
    pass


def save_platform_status(task_id, platform_statuses):
    """Save platform progress and verify that the update was confirmed."""
    try:
        result = (
            supabase.table("master_scheduler_queue")
            .update({"platform_statuses": platform_statuses})
            .eq("id", task_id)
            .select("id")
            .execute()
        )

        if not result.data:
            raise PlatformStatusSaveError(
                f"Platform status was not confirmed for task {task_id}"
            )

        return result

    except PlatformStatusSaveError:
        raise
    except Exception as e:
        raise PlatformStatusSaveError(
            f"Could not confirm platform status save for task {task_id}: {e}"
        ) from e


def process_queue():
    """Database check karta hai aur pending videos upload karta hai"""
    current_utc_time = datetime.now(timezone.utc).isoformat()
    print(f"[{datetime.now()}] 🔍 Checking database for pending videos scheduled up to now...")
    
    try:
        response = supabase.table("master_scheduler_queue") \
            .select("*") \
            .in_("status", ["Pending", "pending", "Failed", "failed"]) \
            .or_(f"next_retry_at.is.null,next_retry_at.lte.{current_utc_time}") \
            .lte("scheduled_time", current_utc_time) \
            .execute()
        tasks = response.data
    except Exception as e:
        print(f"Database error: {e}")
        return
    # SAFETY CHECK: Detect stale Processing tasks only.
    # This block does not update or retry any task.
    if DRY_RUN:
        stale_cutoff = (
            datetime.now(timezone.utc) - timedelta(minutes=30)
        ).isoformat()

        try:
            stale_response = (
                supabase.table("master_scheduler_queue")
                .select("id, processing_started_at, target_platforms")
                .in_("status", ["Processing", "processing"])
                .lt("processing_started_at", stale_cutoff)
                .execute()
            )

            stale_tasks = stale_response.data or []

            if not stale_tasks:
                print("🟢 No stale Processing tasks found.")
            else:
                print(
                    f"⚠️ Found {len(stale_tasks)} stale Processing task(s). "
                    "No status changes or retries performed."
                )

                for stale_task in stale_tasks:
                    print(
                        f"⚠️ STALE task={stale_task.get('id')} | "
                        f"started_at={stale_task.get('processing_started_at')} | "
                        f"platforms={stale_task.get('target_platforms')} | "
                        "MANUAL REVIEW REQUIRED"
                    )

        except Exception as e:
            print(f"⚠️ Stale-task check failed: {e}")
    else:
        # Production recovery is deliberately fail-closed: a stale Processing
        # task is moved to Needs_Review, never blindly requeued, because a
        # publish may have succeeded before the worker crashed.
        stale_cutoff = (
            datetime.now(timezone.utc) - timedelta(minutes=30)
        ).isoformat()
        try:
            stale_response = (
                supabase.table("master_scheduler_queue")
                .select("id, processing_started_at, platform_statuses")
                .in_("status", ["Processing", "processing"])
                .lt("processing_started_at", stale_cutoff)
                .execute()
            )
            for stale_task in (stale_response.data or []):
                try:
                    recovery_result = (
                        supabase.table("master_scheduler_queue")
                        .update({
                            "status": "Needs_Review",
                            "last_error": "Stale Processing task (>30 minutes); verify platform publish state before retrying."
                        })
                        .eq("id", stale_task["id"])
                        .in_("status", ["Processing", "processing"])
                        .lt("processing_started_at", stale_cutoff)
                        .select("id")
                        .execute()
                    )
                    if recovery_result.data:
                        print(f"🛑 Stale task {stale_task['id']} moved to Needs_Review; no automatic retry.")
                    else:
                        print(f"ℹ️ Stale task {stale_task.get('id')} changed concurrently; recovery skipped.")
                except Exception as recovery_error:
                    print(f"🚨 Could not recover stale task {stale_task.get('id')}: {recovery_error}. Manual DB review required.")
        except Exception as e:
            print(f"⚠️ Stale-task recovery scan failed: {e}")


    if not tasks:
        print("📭 No pending videos found. All caught up!")
        return

    for task in tasks:
        # SAFETY GATE: dry-run must happen BEFORE the atomic claim/update.
        # This branch is intentionally read-only: no platform APIs, no R2 URL,
        # no queue status changes, no retries, and no deletion.
        if DRY_RUN:
            task_id = task.get("id", "<missing id>")
            raw_platforms = task.get("target_platforms")
            if not isinstance(raw_platforms, list) or not raw_platforms:
                print(f"🧪 DRY-RUN INVALID task={task_id}: target_platforms must be a non-empty list; no changes made.")
                continue

            if any(not isinstance(p, str) or not p.strip() for p in raw_platforms):
                print(f"🧪 DRY-RUN INVALID task={task_id}: target_platforms contains an empty/non-string value; no changes made.")
                continue

            platforms = [p.strip().lower() for p in raw_platforms]
            unsupported = sorted(set(platforms) - SUPPORTED_PLATFORMS)
            if unsupported:
                print(f"🧪 DRY-RUN INVALID task={task_id}: unsupported platform(s)={unsupported}; no changes made.")
                continue

            if not task.get("r2_key"):
                print(f"🧪 DRY-RUN INVALID task={task_id}: missing r2_key; no changes made.")
                continue

            metadata = task.get("metadata_payload")
            if not isinstance(metadata, dict) or not metadata:
                print(f"🧪 DRY-RUN INVALID task={task_id}: metadata_payload must be a non-empty object; no changes made.")
                continue

            if not task.get("creator_handle"):
                print(f"🧪 DRY-RUN INVALID task={task_id}: missing creator_handle; no changes made.")
                continue

            print(
                f"🧪 DRY-RUN OK task={task_id} | platforms={platforms} | "
                f"r2_key=present | metadata_payload=present | creator_handle=present | "
                "queue unchanged; nothing published."
            )
            continue

        # 🚨 FIX 1: TRUE ATOMIC CLAIM
        # Try to claim the task by changing status ONLY if it's still Pending
        
        claim_result = (
            supabase.table("master_scheduler_queue")
            .update({
                "status": "Processing",
                "processing_started_at": datetime.now(timezone.utc).isoformat()
            })
            .eq("id", task["id"])
            .in_("status", ["Pending", "pending", "Failed", "failed"])
            .select("*")
            .execute()
        )

        if not claim_result.data:
            print(
                f"⏩ Task {task['id']} was already claimed "
                "or could not be claimed. Skipping."
            )
            continue

        
        task = claim_result.data[0]

        # Initialize task state before validation so exception handling
        # can safely record the failure.
        
        
        platforms = []
        raw_platform_statuses = task.get("platform_statuses")
        platform_statuses = (
            raw_platform_statuses
            if isinstance(raw_platform_statuses, dict)
            else {}
        )
        has_errors = False

        # Safe defaults for exception handling
        retry_count = 0
        max_retries = 3
        retry_count_incremented = False

        try:
            raw_retry_count = task.get("retry_count")

            if raw_retry_count is None:
                retry_count = 0
            elif (
                isinstance(raw_retry_count, bool)
                or not isinstance(raw_retry_count, int)
                or raw_retry_count < 0
            ):
                raise InvalidTaskError(
                    "retry_count must be a non-negative integer."
                )
            else:
                retry_count = raw_retry_count

            raw_platforms = task.get("target_platforms")

            if (
                raw_platform_statuses is not None
                and not isinstance(raw_platform_statuses, dict)
            ):
                raise InvalidTaskError(
                    "platform_statuses must be a dictionary/object."
                )

            if not isinstance(raw_platforms, list) or not raw_platforms:
                raise InvalidTaskError(
                    "target_platforms must be a non-empty list."
                )

            if any(
                not isinstance(p, str) or not p.strip()
                for p in raw_platforms
            ):
                raise InvalidTaskError(
                    "target_platforms contains an empty or non-string value."
                )

            platforms = [p.strip().lower() for p in raw_platforms]
            unsupported = sorted(set(platforms) - SUPPORTED_PLATFORMS)

            if unsupported:
                raise InvalidTaskError(
                    f"Unsupported platform(s): {unsupported}"
                )

            print(
                f"\n🚀 Processing Task ID: {task['id']} "
                f"for platforms: {platforms}"
            )

            # A persisted in-flight marker means the worker may have crashed
            # after a platform accepted the publish request but before the
            # result was saved. Never repost that platform automatically.
            uncertain_platforms = sorted(
                platform
                for platform in set(platforms)
                if isinstance(platform_statuses.get(platform), str)
                and platform_statuses[platform].strip().lower()
                in {"publishing", "outcome_unknown"}
            )
            if uncertain_platforms:
                raise PublishOutcomeUnknown(
                    "Previous run left an uncertain publish state for "
                    f"{uncertain_platforms}. Verify those platforms manually "
                    "before retrying."
                )

            # Keep the existing r2_key / presigned URL / metadata
            # and platform publishing logic below this line.

        
        
            # 🚨 FIX 1: Fetch r2_key instead of old video_url
            r2_key = task.get("r2_key")
            if not isinstance(r2_key, str) or not r2_key.strip():
                raise InvalidTaskError(
                    "r2_key is missing or invalid."
                )

            metadata = task.get("metadata_payload")
            if not isinstance(metadata, dict) or not metadata:
                raise InvalidTaskError(
                    "metadata_payload must be a non-empty object."
                )

            creator_email = task.get("creator_handle")
            if not isinstance(creator_email, str) or not creator_email.strip():
                raise InvalidTaskError(
                    "creator_handle is missing or invalid."
                )
                
            # 🚨 FIX 2: Generate fresh presigned URL for this specific publishing run (1 hour expiry)
            vid_url = generate_presigned_url(r2_key, expiration=3600)
            if not vid_url:
                raise Exception("Failed to generate presigned URL from Cloudflare R2")
                
            meta = metadata
            
            # --- YOUTUBE LOGIC ---
            if "youtube" in platforms:
                if platform_statuses.get("youtube") == "published":
                    print("⏩ Skipping YouTube (Already published in previous run)")
                else:
                    temp_vid_path = None
                    try:
                        print("📺 Starting YouTube sequence...")
                        profile_res = supabase.table("creator_profiles").select("youtube_token").eq("creator_handle", creator_email).execute()
                        
                        if not profile_res.data or not profile_res.data[0].get("youtube_token"):
                            print(f"⚠️ Skipping YT: No YouTube refresh token found for {creator_email}")
                            platform_statuses["youtube"] = "failed"
                            has_errors = True
                        else:
                            user_specific_token = profile_res.data[0]["youtube_token"]
                            
                            temp_vid_path = download_video_safe(vid_url)
                            platform_statuses["youtube"] = "publishing"
                            save_platform_status(task["id"], platform_statuses)
                            yt_id = upload_to_youtube(temp_vid_path, meta, user_specific_token)
                            print(f"✅ Success! YouTube Video ID: {yt_id}")
                            platform_statuses["youtube"] = "published"
                            save_platform_status(task["id"], platform_statuses)
                    
                    except PlatformStatusSaveError:
                        raise  
                    
                    except PublishOutcomeUnknown:
                        raise

                    except Exception as e:
                        print(f"❌ YouTube Execution Failed: {str(e)}")
                        platform_statuses["youtube"] = "failed"
                        has_errors = True
                    finally:
                        # 🚨 FIX 3: INDEPENDENT TEMP FILE CLEANUP
                        if temp_vid_path and os.path.exists(temp_vid_path):
                            os.remove(temp_vid_path)
                            print("🧹 YouTube temporary file cleaned up.")

            # --- TWITTER LOGIC ---
            if "twitter" in platforms:
                if platform_statuses.get("twitter") == "published":
                    print("⏩ Skipping Twitter (Already published in previous run)")
                else:
                    print("🐦 Starting Twitter sequence...")
                    tw_profile_res = supabase.table("creator_profiles").select("twitter_token, twitter_access_secret").eq("creator_handle", creator_email).execute()
                    
                    if not tw_profile_res.data or not tw_profile_res.data[0].get("twitter_token"):
                        print(f"⚠️ Skipping Twitter: No connected X account found for {creator_email}")
                        platform_statuses["twitter"] = "failed"
                        has_errors = True
                    else:
                        try:
                            user_tokens = tw_profile_res.data[0]
                            twitter_credentials = {
                                "api_key": st.secrets["TWITTER_API_KEY"],
                                "api_secret": st.secrets["TWITTER_API_SECRET"],
                                "access_token": user_tokens.get("twitter_token"),
                                "access_token_secret": user_tokens.get("twitter_access_secret")
                            }
                            thread_text = meta.get("twitter_thread_text", "")
                            
                            platform_statuses["twitter"] = "publishing"
                            save_platform_status(task["id"], platform_statuses)
                            success, msg = execute_twitter_thread(twitter_credentials, thread_text, vid_url)
                            if success:
                                print(f"✅ {msg}")
                                platform_statuses["twitter"] = "published"
                                save_platform_status(task["id"], platform_statuses)
                            else:
                                raise Exception(f"Twitter Execution Failed: {msg}")
                            
                        except PlatformStatusSaveError:
                            raise

                        except PublishOutcomeUnknown:
                            raise

                        except Exception as e:
                            print(f"❌ Twitter Execution Failed: {str(e)}")
                            platform_statuses["twitter"] = "failed"
                            has_errors = True

            # --- META (INSTAGRAM) LOGIC ---
            if "instagram" in platforms or "meta" in platforms:
                if platform_statuses.get("instagram") == "published":
                    print("⏩ Skipping Instagram (Already published in previous run)")
                else:
                    print("♾️ Starting Meta (Instagram) sequence...")
                    profile_res = supabase.table("creator_profiles").select("instagram_token").eq("creator_handle", creator_email).execute()
                    
                    if not profile_res.data or not profile_res.data[0].get("instagram_token"):
                        print(f"⚠️ Skipping Meta: No valid Meta token found")
                        platform_statuses["instagram"] = "failed"
                        has_errors = True
                    else:
                        try:
                            ig_token = profile_res.data[0]["instagram_token"]
                            ig_caption = meta.get("instagram_caption", "Powered by AI Creator OS 🚀")
                            platform_statuses["instagram"] = "publishing"
                            save_platform_status(task["id"], platform_statuses)
                            success, msg = upload_to_instagram(vid_url, ig_caption, ig_token)
                            if success:
                                print(f"✅ {msg}")
                                platform_statuses["instagram"] = "published"
                                save_platform_status(task["id"], platform_statuses)
                            else:
                                raise Exception(f"Meta Execution Failed: {msg}")

                        except PlatformStatusSaveError:
                            raise

                        except PublishOutcomeUnknown:
                            raise

                        except Exception as e:
                            print(f"❌ Meta Execution Failed: {str(e)}")
                            platform_statuses["instagram"] = "failed"
                            has_errors = True

            # --- FACEBOOK LOGIC ---
            if "facebook" in platforms:
                 if platform_statuses.get("facebook") == "published":
                    print("⏩ Skipping Facebook (Already published in previous run)")
                 else:
                    print("📘 Starting Facebook sequence...")
                    profile_res = supabase.table("creator_profiles").select("facebook_token").eq("creator_handle", creator_email).execute()
                    
                    if not profile_res.data or not profile_res.data[0].get("facebook_token"):
                        print(f"⚠️ Skipping FB: No valid Facebook token found")
                        platform_statuses["facebook"] = "failed"
                        has_errors = True
                    else:
                        try:
                            fb_token = profile_res.data[0]["facebook_token"]
                            fb_caption = meta.get("facebook_post_text", "Powered by AI Creator OS 🚀")
                            platform_statuses["facebook"] = "publishing"
                            save_platform_status(task["id"], platform_statuses)
                            success, msg = upload_to_facebook(vid_url, fb_caption, fb_token)
                            if success:
                                print(f"✅ {msg}")
                                platform_statuses["facebook"] = "published"
                                save_platform_status(task["id"], platform_statuses)
                            else:
                                raise Exception(f"Facebook Execution Failed: {msg}")
                        
                        except PlatformStatusSaveError:
                            raise

                        except PublishOutcomeUnknown:
                            raise

                        except Exception as e:
                            print(f"❌ Facebook Execution Failed: {str(e)}")
                            platform_statuses["facebook"] = "failed"
                            has_errors = True

            # --- THREADS LOGIC ---
            if "threads" in platforms:
                 if platform_statuses.get("threads") == "published":
                    print("⏩ Skipping Threads (Already published in previous run)")
                 else:
                    print("🧵 Starting Threads sequence...")
                    profile_res = supabase.table("creator_profiles").select("threads_token").eq("creator_handle", creator_email).execute()
                    
                    if not profile_res.data or not profile_res.data[0].get("threads_token"):
                        print(f"⚠️ Skipping Threads: No valid token found")
                        platform_statuses["threads"] = "failed"
                        has_errors = True
                    else:
                        try:
                            th_token = profile_res.data[0]["threads_token"]
                            th_caption = meta.get("threads_content", "Powered by AI Creator OS 🚀")
                            platform_statuses["threads"] = "publishing"
                            save_platform_status(task["id"], platform_statuses)
                            success, msg = upload_to_threads(vid_url, th_caption, th_token)
                            if success:
                                print(f"✅ {msg}")
                                platform_statuses["threads"] = "published"
                                save_platform_status(task["id"], platform_statuses)
                            else:
                                raise Exception(f"Threads Execution Failed: {msg}")

                        except PublishOutcomeUnknown:
                            raise

                        except PlatformStatusSaveError:
                            raise

                        except Exception as e:
                            print(f"❌ Threads Execution Failed: {str(e)}")
                            platform_statuses["threads"] = "failed"
                            has_errors = True

            # --- LINKEDIN LOGIC ---
            if "linkedin" in platforms:
                if platform_statuses.get("linkedin") == "published":
                    print("⏩ Skipping LinkedIn (Already published)")
                else:
                    temp_vid_path = None
                    try:
                        print("💼 Starting LinkedIn sequence...")
                        profile_res = supabase.table("creator_profiles").select("linkedin_token").eq("creator_handle", creator_email).execute()
                        
                        if not profile_res.data or not profile_res.data[0].get("linkedin_token"):
                            print(f"⚠️ Skipping LinkedIn: No valid token found")
                            platform_statuses["linkedin"] = "failed"
                            has_errors = True
                        else:
                            li_token = profile_res.data[0]["linkedin_token"]
                            li_caption = meta.get("linkedin_post_text", "Powered by AI Creator OS 🚀")
                            
                            temp_vid_path = download_video_safe(vid_url)
                            
                            platform_statuses["linkedin"] = "publishing"
                            save_platform_status(task["id"], platform_statuses)
                            success, msg = upload_to_linkedin(temp_vid_path, li_caption, li_token)
                            if success:
                                print(f"✅ {msg}")
                                platform_statuses["linkedin"] = "published"
                                save_platform_status(task["id"], platform_statuses)
                            else:
                                raise Exception(f"LinkedIn Execution Failed: {msg}")
                            
                    except PlatformStatusSaveError:
                        raise

                    except PublishOutcomeUnknown:
                        raise
                    
                    except Exception as e:
                        print(f"❌ LinkedIn Execution Failed: {str(e)}")
                        platform_statuses["linkedin"] = "failed"
                        has_errors = True
                    finally:
                        # 🚨 FIX 3: INDEPENDENT TEMP FILE CLEANUP
                        if temp_vid_path and os.path.exists(temp_vid_path):
                            os.remove(temp_vid_path)
                            print("🧹 LinkedIn temporary file cleaned up.")

            # 🚨 FIX: EXPONENTIAL BACKOFF SMART RETRY LOGIC
            if has_errors:
                
                if not retry_count_incremented:
                    retry_count += 1
                    retry_count_incremented = True
                if retry_count <= max_retries:
                    # Calculate next retry time
                    if retry_count == 1:
                        delay = timedelta(minutes=15)
                    elif retry_count == 2:
                        delay = timedelta(hours=1)
                    else:
                        delay = timedelta(hours=3)
                        
                    next_retry = (datetime.now(timezone.utc) + delay).isoformat()
                    
                    print(f"⚠️ Partial/Full Failure. Scheduling retry {retry_count}/{max_retries} at {next_retry}")
                    
                    retry_result = (
                        supabase.table("master_scheduler_queue")
                        .update({
                            "status": "Failed",
                            "platform_statuses": platform_statuses,
                            "retry_count": retry_count,
                            "next_retry_at": next_retry
                        })
                        .eq("id", task["id"])
                        .eq("status", "Processing")
                        .select("id")
                        .execute()
                    )

                    if not retry_result.data:
                        print(
                            f"🚨 Retry scheduling could not be confirmed for task "
                            f"{task['id']}. Check the database manually."
                        )
                    else:
                        print(
                            f"✅ Retry scheduled for task {task['id']} "
                            f"at {next_retry}"
                        )

                else:
                    print(
                        f"❌ Max retries ({max_retries}) reached. "
                        "Finalizing failed task."
                    )

                    finalize_exhausted_task(
                        task_id=task["id"],
                        retry_count=retry_count,
                        platform_statuses=platform_statuses,
                        error_message="Maximum retry attempts exhausted.",
                    )
            
            else:
                print(
                    f"✅ Task {task['id']} marked Permanent_Fail."
                )

                try:
                    delete_result = (
                        supabase.table("master_scheduler_queue")
                        .delete()
                        .eq("id", task["id"])
                        .eq("status", "Permanent_Fail")
                        .eq("retry_count", retry_count)
                        .select("id")
                        .execute()
                    )

                    if delete_result.data:
                        print(
                            f"🗑️ Exhausted task {task['id']} "
                            "deleted from queue."
                        )
                    else:
                        print(
                            f"⚠️ Cleanup not confirmed for task "
                            f"{task['id']}; row retained or changed concurrently."
                        )

                except Exception as cleanup_error:
                    print(
                        f"🚨 Cleanup failed for task {task['id']}: "
                        f"{cleanup_error}. Permanent_Fail row retained "
                        "if deletion did not succeed."
                    )



        
        except PublishOutcomeUnknown as e:
            print(
                f"🛑 Task {task['id']}: {e} "
                "Manual review required; automatic retry blocked."
            )

            try:
                review_result = (
                    supabase.table("master_scheduler_queue")
                    .update({
                        "status": "Needs_Review",
                        "platform_statuses": platform_statuses,
                    })
                    .eq("id", task["id"])
                    .eq("status", "Processing")
                    .select("id")
                    .execute()
                )

                if review_result.data:
                    print(
                        f"✅ Task {task['id']} marked Needs_Review. "
                        "Check the affected platform(s) manually before retrying."
                    )
                else:
                    print(
                        f"🚨 Could not confirm Needs_Review for "
                        f"task {task['id']}. Check the database manually."
                    )

            except Exception as review_error:
                print(
                    f"🚨 Failed to save Needs_Review for task "
                    f"{task['id']}: {review_error}. "
                    "Check the database manually; do not assume "
                    "the task status was updated."
                )

        
        except PlatformStatusSaveError as e:
            print(
                f"⚠️ Task {task['id']}: platform status save "
                f"could not be confirmed. Manual review required. "
                f"Details: {e}"
            )

            try:
                review_result = (
                    supabase.table("master_scheduler_queue")
                    .update({
                        "status": "Needs_Review",
                        "platform_statuses": platform_statuses,
                    })
                    .eq("id", task["id"])
                    .eq("status", "Processing")
                    .select("id")
                    .execute()
                )

                if review_result.data:
                    print(
                        f"🛑 Task {task['id']} marked Needs_Review. "
                        "Automatic retry must not proceed."
                    )
                else:
                    print(
                        f"🚨 Could not confirm Needs_Review status "
                        f"for task {task['id']}. Manual DB check required."
                    )

            except Exception as review_error:
                print(
                    f"🚨 Failed to save Needs_Review for task "
                    f"{task['id']}: {review_error}. "
                    "Check the database manually; do not assume "
                    "the task status was updated."
                )
        except InvalidTaskError as e:
            print(
                f"⛔ Invalid task {task['id']}: {e}. "
                "Automatic retry blocked."
            )

            try:
                invalid_result = (
                    supabase.table("master_scheduler_queue")
                    .update({
                        "status": "Permanent_Fail",
                        "platform_statuses": platform_statuses,
                    })
                    .eq("id", task["id"])
                    .eq("status", "Processing")
                    .select("id")
                    .execute()
                )

                if invalid_result.data:
                    print(
                        f"✅ Invalid task {task['id']} marked "
                        "Permanent_Fail. No retry scheduled."
                    )
                else:
                    print(
                        f"🚨 Could not confirm invalid-task status "
                        f"for {task['id']}. Check database manually."
                    )

            except Exception as status_error:
                print(
                    f"🚨 Failed to mark invalid task {task['id']}: "
                    f"{status_error}. Check database manually."
                )        

        
        except Exception as e:
            print(
                f"❌ Critical Error on Task {task['id']}: {str(e)}"
            )

            # A generic exception is not proof that publishing failed. If any
            # platform was marked in-flight/unknown, never schedule an automatic retry.
            if has_uncertain_publish_state(platform_statuses):
                try:
                    review_result = (
                        supabase.table("master_scheduler_queue")
                        .update({
                            "status": "Needs_Review",
                            "platform_statuses": platform_statuses,
                            "last_error": f"Uncertain publish outcome after error: {e}"
                        })
                        .eq("id", task["id"])
                        .eq("status", "Processing")
                        .select("id")
                        .execute()
                    )
                    if review_result.data:
                        print(f"🛑 Task {task['id']} marked Needs_Review; no retry scheduled.")
                    else:
                        print(f"🚨 Could not confirm Needs_Review for task {task['id']}; manual DB check required.")
                except Exception as review_error:
                    print(f"🚨 Could not save Needs_Review for task {task['id']}: {review_error}. Manual DB check required; no retry attempted.")
                continue

            if not retry_count_incremented:
                retry_count += 1
                retry_count_incremented = True


            try:
                if retry_count <= max_retries:
                    if retry_count == 1:
                        delay = timedelta(minutes=15)
                    elif retry_count == 2:
                        delay = timedelta(hours=1)
                    else:
                        delay = timedelta(hours=3)

                    next_retry = (
                        datetime.now(timezone.utc) + delay
                    ).isoformat()

                    retry_result = (
                        supabase.table("master_scheduler_queue")
                        .update({
                            "status": "Failed",
                            "platform_statuses": platform_statuses,
                            "retry_count": retry_count,
                            "next_retry_at": next_retry
                        })
                        .eq("id", task["id"])
                        .eq("status", "Processing")
                        .select("id")
                        .execute()
                    )

                    if retry_result.data:
                        print(
                            f"✅ Retry scheduled for task {task['id']} "
                            f"at {next_retry}"
                        )
                    else:
                        print(
                            f"🚨 Retry update not confirmed for task "
                            f"{task['id']}. Check the database manually."
                        )

                else:
                    finalize_exhausted_task(
                        task_id=task["id"],
                        retry_count=retry_count,
                        platform_statuses=platform_statuses,
                        error_message=f"Maximum retries exhausted after error: {e}",
                    )

            except Exception as retry_error:
                print(
                    f"🚨 Could not save retry/failure state for task "
                    f"{task['id']}: {retry_error}. "
                    "Check the database manually; do not assume "
                    "the task status was updated."
                )

if __name__ == "__main__":
    print("🚀 Creator AI OS Worker started.")
    print("🔄 Checking for due scheduled tasks every 15 seconds.")

    while True:
        try:
            process_queue()
        except KeyboardInterrupt:
            print("\n🛑 Worker stopped by user.")
            break
        except Exception as e:
            print(f"❌ Worker loop error: {e}")

        try:
            time.sleep(15)
        except KeyboardInterrupt:
            print("\n🛑 Worker stopped by user.")
            break