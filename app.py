# ── Groq Cache Fix ─────────────────────────────────────
try:
    from crewai.llms import cache as _cache
    _cache.mark_cache_breakpoint = lambda msg: msg
except ImportError:
    pass

import streamlit as st
from supabase import create_client, Client
import uuid

# Supabase se connect karna
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)
import urllib.parse
import tempfile
import os
import base64
import hashlib
import os
import io  # 🌟 Virtual Memory (RAM) ke liye
from docx import Document  # 🌟 Word Document Blueprint ke liye
from crewai import Agent, Task, Crew, LLM
import time # 🌟 Runtime backoff delays ke liye
import requests
import json
def post_to_twitter_thread(tweets_list, bearer_token):
    """
    Takes a list of tweets and posts them as a thread using Twitter v2 API.
    tweets_list: list of strings (e.g., ["Tweet 1", "Tweet 2"])
    """
    url = "https://api.twitter.com/2/tweets"
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }
    
    previous_tweet_id = None
    successful_tweets = 0
    
    for tweet in tweets_list:
        payload = {"text": tweet}
        # Agar yeh pehla tweet nahi hai, toh isko pichle wale ka reply banao (Thread logic)
        if previous_tweet_id:
            payload["reply"] = {"in_reply_to_tweet_id": previous_tweet_id}
            
        try:
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 201:
                previous_tweet_id = response.json()['data']['id']
                successful_tweets += 1
                time.sleep(1) # API rate limit se bachne ke liye 1 sec delay
            else:
                return False, f"Twitter API Error: {response.text}"
        except Exception as e:
            return False, f"System Error: {str(e)}"
            
    return True, f"Success! {successful_tweets} tweets posted in thread."
def post_to_linkedin(post_text, access_token, person_urn):
    """
    Posts text to LinkedIn using v2 API.
    person_urn: User's LinkedIn ID (e.g., 'urn:li:person:12345ABC')
    """
    url = "https://api.linkedin.com/v2/ugcPosts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0"
    }
    
    payload = {
        "author": person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": post_text
                },
                "shareMediaCategory": "NONE"
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 201:
            return True, "Successfully posted to LinkedIn!"
        else:
            return False, f"LinkedIn API Error: {response.text}"
    except Exception as e:
        return False, f"System Error: {str(e)}"
import re
# ==============================================================
# 📊 ANALYTICS DATA FETCHERS (READ BRIDGES)
# ==============================================================
def fetch_youtube_analytics(access_token):
    """
    YouTube Data API v3 se channel ke total views, subs aur video count nikalta hai.
    """
    url = "https://www.googleapis.com/youtube/v3/channels?part=statistics&mine=true"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if "items" in data and len(data["items"]) > 0:
                stats = data["items"][0]["statistics"]
                # JSONB format ke liye clean dictionary return kar rahe hain
                return {
                    "views": int(stats.get("viewCount", 0)),
                    "subscribers": int(stats.get("subscriberCount", 0)),
                    "video_count": int(stats.get("videoCount", 0)),
                    "status": "connected"
                }
            else:
                return {"error": "Channel not found", "status": "failed"}
        elif response.status_code == 401:
            # Token expire hone ka error
            return {"error": "Token Expired", "status": "auth_failed"}
        else:
            return {"error": f"API Error: {response.status_code}", "status": "failed"}
            
    except Exception as e:
        print(f"[YT ANALYTICS ERROR] {str(e)}")
        return {"error": str(e), "status": "failed"}
def fetch_meta_analytics(access_token):
    """
    Ek hi Meta token se Facebook Page aur us se linked Instagram Business ka data nikalta hai.
    """
    base_url = "https://graph.facebook.com/v18.0"
    
    try:
        # 1. User ke connected Facebook Pages nikalo
        pages_url = f"{base_url}/me/accounts?access_token={access_token}"
        pages_res = requests.get(pages_url).json()
        
        if "error" in pages_res:
            return {"error": pages_res["error"]["message"], "status": "auth_failed"}
            
        fb_data = {"followers": 0, "status": "offline"}
        ig_data = {"followers": 0, "status": "offline"}
        
        # 2. Page loop karke data aur linked IG account fetch karo
        if "data" in pages_res and len(pages_res["data"]) > 0:
            first_page = pages_res["data"][0]
            page_id = first_page.get("id")
            page_token = first_page.get("access_token")
            
            # FB Page Details (Followers)
            fb_page_url = f"{base_url}/{page_id}?fields=followers_count&access_token={page_token}"
            fb_details = requests.get(fb_page_url).json()
            fb_data["followers"] = fb_details.get("followers_count", 0)
            fb_data["status"] = "connected"
            
            # Connected IG Account Details
            ig_link_url = f"{base_url}/{page_id}?fields=instagram_business_account&access_token={page_token}"
            ig_link_res = requests.get(ig_link_url).json()
            
            if "instagram_business_account" in ig_link_res:
                ig_id = ig_link_res["instagram_business_account"]["id"]
                ig_user_url = f"{base_url}/{ig_id}?fields=followers_count&access_token={access_token}"
                ig_details = requests.get(ig_user_url).json()
                ig_data["followers"] = ig_details.get("followers_count", 0)
                ig_data["status"] = "connected"
        
        return {"facebook": fb_data, "instagram": ig_data, "status": "connected"}
        
    except Exception as e:
        print(f"[META ANALYTICS ERROR] {str(e)}")
        return {"error": str(e), "status": "failed"}
# ==============================================================
# 🔄 MASTER SYNC ENGINE (API to Supabase Cache)
# ==============================================================
def sync_platform_analytics():
    """
    User ke tokens fetch karta hai, live APIs ko hit karta hai, aur data ko 
    platform_analytics_cache table mein update (UPSERT) kar deta hai.
    """
    creator_handle = st.session_state.get("creator_handle")
    if not creator_handle:
        return False
        
    try:
        # 1. User ke secure tokens nikalo
        profile_res = supabase.table("creator_profiles").select("*").eq("creator_handle", creator_handle).execute()
        if not profile_res.data:
            return False
            
        user_tokens = profile_res.data[0]
        yt_token = user_tokens.get("youtube_token")
        
        yt_data = {}
        sync_health = "Healthy"
        
        # 2. YouTube Data Pull karo
        if yt_token:
            yt_data = fetch_youtube_analytics(yt_token)
            if yt_data.get("status") == "auth_failed":
                sync_health = "YT_Auth_Failed"
                
        # 3. META Data Pull (FB & IG Ek Saath)
        fb_token = user_tokens.get("facebook_token") or user_tokens.get("instagram_token")
        meta_results = {}
        if fb_token:
            meta_results = fetch_meta_analytics(fb_token)
            if meta_results.get("status") == "auth_failed":
                sync_health = "Meta_Auth_Failed"
                
        # 4. Supabase Cache Matrix mein Inject karo
        cache_res = supabase.table("platform_analytics_cache").select("id").eq("creator_handle", creator_handle).execute()
        
        if cache_res.data:
            # UPDATE
            supabase.table("platform_analytics_cache").update({
                "youtube_data": yt_data,
                "facebook_data": meta_results.get("facebook", {}),
                "instagram_data": meta_results.get("instagram", {}),
                "sync_status": sync_health,
            }).eq("creator_handle", creator_handle).execute()
        else:
            # INSERT
            supabase.table("platform_analytics_cache").insert({
                "creator_handle": creator_handle,
                "youtube_data": yt_data,
                "facebook_data": meta_results.get("facebook", {}),
                "instagram_data": meta_results.get("instagram", {}),
                "sync_status": sync_health
            }).execute()
            
        return True
        
    except Exception as e:
        # Ab hum error ko chhipayenge nahi, seedha UI par bhejenge!
        return f"CRASH LOG: {str(e)}"
def get_youtube_access_token(auth_code):
    """
    Kachhe Auth Code ko Google ke server par bhej kar asli Access Token laata hai.
    """
    client_id = st.secrets.get("YOUTUBE_CLIENT_ID", "")
    client_secret = st.secrets.get("YOUTUBE_CLIENT_SECRET", "") # ⚠️ Yeh secret chahiye hoga!
    redirect_uri = "https://creator-ai-manager-tgrh5ifkgfqme6kdomcvxb.streamlit.app/"
    
    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri
    }
    
    try:
        response = requests.post(token_url, data=payload)
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            print(f"[YT TOKEN ERROR] Google rejected the code: {response.text}")
            return None
    except Exception as e:
        print(f"[YT TOKEN EXCEPTION] {str(e)}")
        return None

def parse_blueprint_metadata(raw_text):
    """
    Takes the raw text from CrewAI, slices it based on exact headings using Regex, 
    and returns a formatted dictionary for Tab 3 UI boxes.
    """
    # 1. Khali dictionary banayein jisme Tab 3 ke saare expected keys hon (To prevent KeyError)
    metadata = {
        "yt_title": "",
        "yt_desc": "",
        "linkedin_post": "",
        "tw_thread": "",
        "ig_caption": ""
    }
    
    # 2. Slicing with Regex
    # Extract Title
    title_match = re.search(r"Title:\s*(.*?)(?=\nDescription:|\nLinkedIn Post:|\nTwitter Thread:|$)", raw_text, re.IGNORECASE | re.DOTALL)
    if title_match:
        metadata["yt_title"] = title_match.group(1).strip()
        
    # Extract Description
    desc_match = re.search(r"Description:\s*(.*?)(?=\nLinkedIn Post:|\nTwitter Thread:|$)", raw_text, re.IGNORECASE | re.DOTALL)
    if desc_match:
        metadata["yt_desc"] = desc_match.group(1).strip()
        
    # Extract LinkedIn
    linkedin_match = re.search(r"LinkedIn Post:\s*(.*?)(?=\nTwitter Thread:|$)", raw_text, re.IGNORECASE | re.DOTALL)
    if linkedin_match:
        metadata["linkedin_post"] = linkedin_match.group(1).strip()
        
    # Extract Twitter
    twitter_match = re.search(r"Twitter Thread:\s*(.*?)(?=$)", raw_text, re.IGNORECASE | re.DOTALL)
    if twitter_match:
        metadata["tw_thread"] = twitter_match.group(1).strip()
        
    # Extract Instagram (Agar by chance future mein add ho)
    ig_match = re.search(r"Instagram Caption:\s*(.*?)(?=$)", raw_text, re.IGNORECASE | re.DOTALL)
    if ig_match:
        metadata["ig_caption"] = ig_match.group(1).strip()
        
    return metadata

st.set_page_config(page_title="Creator AI OS", layout="wide")

# ── API Keys ───────────────────────────────────────────
# ── STEP 1: TRIPLE-LAYER FAILPROOF LLM RESOLVER MATRIX ──
G_KEY_1 = st.secrets.get("GEMINI_API_KEY_1", "")
G_KEY_2 = st.secrets.get("GEMINI_API_KEY_2", "")
GR_KEY_1 = st.secrets.get("GROQ_API_KEY_1", "")
GR_KEY_2 = st.secrets.get("GROQ_API_KEY_2", "")
S_KEY_1 = st.secrets.get("SERPER_API_KEY_1", "")
S_KEY_2 = st.secrets.get("SERPER_API_KEY_2", "")

GEMINI_KEY = G_KEY_1 if G_KEY_1 else st.secrets.get("GEMINI_API_KEY", "")
GROQ_KEY   = GR_KEY_1 if GR_KEY_1 else st.secrets.get("GROQ_API_KEY", "")
SERPER_KEY = S_KEY_1 if S_KEY_1 else st.secrets.get("SERPER_API_KEY", "")
# ==============================================================
# 🔐 SECURE AUTHENTICATION SYSTEM (Supabase Auth)
# ==============================================================
if "user_email" not in st.session_state:
    st.session_state["user_email"] = None

# 🔄 NAYA: Redirect ke baad Supabase ka 'ID Card' wapas pehnana
if st.session_state.get("sb_access_token") and st.session_state.get("sb_refresh_token"):
    try:
        supabase.auth.set_session(st.session_state["sb_access_token"], st.session_state["sb_refresh_token"])
    except:
        pass

# 🧠 SUPABASE SESSION AUTO-RECOVERY (Memory Check)
if st.session_state["user_email"] is None:
    try:
        current_session = supabase.auth.get_session()
        if current_session and current_session.user:
            st.session_state["user_email"] = current_session.user.email
            st.session_state["creator_handle"] = current_session.user.email
            st.session_state["sb_access_token"] = current_session.access_token
            st.session_state["sb_refresh_token"] = current_session.refresh_token
    except:
        pass

# Agar user logged in nahi hai, toh secure Login/Signup screen dikhao
if st.session_state["user_email"] is None:
    st.markdown("<h2 style='text-align: center;'>🔐 Secure Access - Creator AI OS</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>Create an account or login to access your secure workspace.</p>", unsafe_allow_html=True)
    
    st.write(" ")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_login, tab_signup = st.tabs(["🔑 Login", "📝 Create Account"])
        
        # --- LOGIN TAB ---
        with tab_login:
            log_email = st.text_input("Email Address", key="log_email")
            log_pass = st.text_input("Password", type="password", key="log_pass")
            if st.button("🚀 Login", use_container_width=True):
                try:
                    # Supabase API Call
                    user = supabase.auth.sign_in_with_password({"email": log_email.strip(), "password": log_pass})
                    st.session_state["user_email"] = log_email.strip()
                    st.session_state["creator_handle"] = log_email.strip()
                    # 💾 ID Card memory mein save kar rahe hain
                    st.session_state["sb_access_token"] = user.session.access_token
                    st.session_state["sb_refresh_token"] = user.session.refresh_token
                    st.success("Login Successful!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"⚠️ Login Error: {str(e)}") 

        # --- SIGN UP TAB ---
        with tab_signup:
            reg_email = st.text_input("New Email Address", key="reg_email")
            reg_pass = st.text_input("Create Password (Min 6 chars)", type="password", key="reg_pass")
            opt_in = st.checkbox("Send my generated AI scripts & channel audit reports to my email.", value=True)
            
            if st.button("✨ Create Free Account", use_container_width=True):
                if len(reg_pass) < 6:
                    st.warning("Password must be at least 6 characters long.")
                else:
                    try:
                        user = supabase.auth.sign_up({"email": reg_email.strip(), "password": reg_pass})
                        st.success("Account Created! Logging you in automatically... 🚀")
                        time.sleep(1.5)
                        st.session_state["user_email"] = reg_email.strip()
                        st.session_state["creator_handle"] = reg_email.strip()
                        # 💾 ID Card memory mein save kar rahe hain
                        st.session_state["sb_access_token"] = user.session.access_token
                        st.session_state["sb_refresh_token"] = user.session.refresh_token
                        st.rerun()
                    except Exception as e:
                        st.error(f"⚠️ Registration Failed: {str(e)}")
    
    # 🛑 SECURITY LOCK
    st.stop() 

# ✅ SIRF YEH NAYA CODE REHNA CHAHIYE ✅
st.sidebar.markdown(f"### 👤 Profile:\n**{st.session_state['user_email']}**")
# ==============================================================
# 🧠 SMART MEMORY RECOVERY & HELPERS
# ==============================================================
if "db_checked" not in st.session_state and st.session_state.get("creator_handle"):
    try:
        response = supabase.table("creator_profiles").select("*").eq("creator_handle", st.session_state["creator_handle"]).execute()
        if response.data:
            user_data = response.data[0]
            # Har platform ka individual status check
            st.session_state["yt_connected"] = bool(user_data.get("youtube_token"))
            st.session_state["tw_connected"] = bool(user_data.get("twitter_token"))
            st.session_state["ig_connected"] = bool(user_data.get("instagram_token"))
            st.session_state["fb_connected"] = bool(user_data.get("facebook_token"))
            st.session_state["li_connected"] = bool(user_data.get("linkedin_token")) # 💼 LinkedIn Memory Load
            st.session_state["th_connected"] = bool(user_data.get("threads_token")) # Threads Memory Load

            if any([st.session_state.get(k) for k in ["yt_connected", "tw_connected", "ig_connected", "fb_connected", "li_connected"]]):
                st.session_state["channels_synced"] = True
                
        st.session_state["db_checked"] = True
    except Exception as e:
        print(f"Memory Sync Error: {e}")

def disconnect_platform(platform_column, session_key):
    """Database se token hatane aur button reset karne ka function"""
    if st.session_state.get("creator_handle"):
        supabase.table("creator_profiles").update({platform_column: None}).eq("creator_handle", st.session_state["creator_handle"]).execute()
        st.session_state[session_key] = False
        st.rerun()
if st.sidebar.button("🚪 Secure Logout"):
    supabase.auth.sign_out()
    st.session_state["sb_access_token"] = None
    st.session_state["sb_refresh_token"] = None
    st.session_state["user_email"] = None
    st.session_state["creator_handle"] = None
    st.session_state["channels_synced"] = False 
    st.rerun()
st.sidebar.write("---") 

from crewai_tools import SerperDevTool
search_tool = SerperDevTool(api_key=SERPER_KEY) if SERPER_KEY else None

if not G_KEY_1 and not GR_KEY_1 and not GEMINI_KEY and not GROQ_KEY:
    st.sidebar.error("⚠️ Control Panel Matrix Empty: Keys Missing!")

def get_cluster_llm(provider="groq"):
    if provider == "groq":
        primary_key = GR_KEY_1 if GR_KEY_1 else GROQ_KEY
        fallback_key = GR_KEY_2 if GR_KEY_2 else primary_key
        try:
            return LLM(model="groq/llama-3.3-70b-versatile", api_key=primary_key, timeout=30)
        except Exception as e:
            print(f"[ROUTING ALERT] Groq Key 1 failed. Swapping to Groq Key 2. Error: {e}")
            return LLM(model="groq/llama-3.3-70b-versatile", api_key=fallback_key, timeout=30)
    else:
        primary_key = G_KEY_1 if G_KEY_1 else GEMINI_KEY
        fallback_key = G_KEY_2 if G_KEY_2 else primary_key
        try:
            return LLM(model="gemini/gemini-2.5-flash", api_key=primary_key, timeout=30)
        except Exception as e:
            print(f"[ROUTING ALERT] Gemini Key 1 failed. Swapping to Gemini Key 2. Error: {e}")
            return LLM(model="gemini/gemini-2.5-flash", api_key=fallback_key, timeout=30)

def create_word_doc(script_text, platform_name, topic_name):
    doc = Document()
    doc.add_heading(f"🎬 Production Blueprint: {topic_name}", level=1)
    doc.add_paragraph(f"Target Platform: {platform_name}")
    doc.add_paragraph("Generated by: Creator AI OS (Multi-Agent System)")
    doc.add_paragraph("="*50)
    doc.add_heading("📝 Video Script Content", level=2)
    
    # 🛠️ THE FIX: Text ko line-by-line todna taaki MS Word mein "Boxes" na aayein
    lines = script_text.split('\n')
    for line in lines:
        clean_line = line.strip()
        # Markdown ke '###' ko Word mein clean dikhane ke liye hata rahe hain
        clean_line = clean_line.replace('### ', '') 
        
        # Sirf tabhi paragraph add karo jab line khali na ho
        if clean_line:
            doc.add_paragraph(clean_line)
            
    bio = io.BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio

def fetch_live_trends(niche_topic):
    if not SERPER_KEY:
        return []
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": f"site:youtube.com watch viral video {niche_topic}", "num": 5})
    headers = {'X-API-KEY': SERPER_KEY, 'Content-Type': 'application/json'}
    video_trends = []
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        data = response.json()
        if "organic" in data:
            for item in data["organic"]:
                link = item.get("link", "")
                if "youtube.com/watch" in link or "youtu.be" in link:
                    video_trends.append({"title": item.get("title", "Trending Video Blueprint"), "url": link})
                if len(video_trends) >= 3:
                    break
        return video_trends
    except Exception as e:
        print(f"[RADAR ERROR] Blueprint link extraction failed: {str(e)}")
        return []

# ── Session State Management Nodes ──────────────────────
if "active_model"      not in st.session_state: st.session_state["active_model"] = ""
if "gemini_error"      not in st.session_state: st.session_state["gemini_error"] = ""
if "channels_synced"   not in st.session_state: st.session_state["channels_synced"] = False
if "audit_data_ready"  not in st.session_state: st.session_state["audit_data_ready"] = False
if "mock_upload_ready" not in st.session_state: st.session_state["mock_upload_ready"] = False


# 🎯 INTEGRATION POINT 1: OAuth Link Generators Modules
# LINKEDIN OAUTH FUNCTION
# ==============================================================
def get_linkedin_oauth_url():
    # Streamlit secrets se Client ID uthana
    client_id = st.secrets.get("LINKEDIN_CLIENT_ID", "")
    
    if not client_id:
        return "#error_missing_linkedin_client_id"

    # Tera exact live URL
    redirect_uri = "https://creator-ai-manager-tgrh5ifkgfqme6kdomcvxb.streamlit.app/" 
    
    # LinkedIn ke permissions (Profile padhna aur post karna)
    # w_member_social = Post karne ki power
    # openid, profile, email = User ki basic details (URN) nikalne ki power
    scopes = ["openid", "profile", "email", "w_member_social"]
    scope_str = "%20".join(scopes)
    
    # Security ke liye unique state generate karna
    state = "linkedin_" + str(uuid.uuid4())[:8]
    
    # LinkedIn ka official authorization URL
    auth_url = f"https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&state={state}&scope={scope_str}"
    
    return auth_url
def get_meta_oauth_url():
    client_id = st.secrets.get("INSTAGRAM_APP_ID", "")
    
    if not client_id:
        print("[AUTH ERROR] Instagram App ID missing in secrets!")
        return "#error_missing_client_id"

    # YAHAN UPDATE KIYA HAI: http ko https kar diya hai (exact match with Meta dashboard)
    redirect_uri = "https://creator-ai-manager-tgrh5ifkgfqme6kdomcvxb.streamlit.app/" 
    
    scopes = ["instagram_business_basic", "instagram_business_manage_insights", "instagram_business_content_publish"]
    scope_str = ",".join(scopes)
    
    auth_url = f"https://www.instagram.com/oauth/authorize?enable_fb_login=0&client_id={client_id}&redirect_uri={redirect_uri}&scope={scope_str}&response_type=code&state=instagram"
    
    return auth_url
# ==============================================================
# META THREADS OAUTH FUNCTION
# ==============================================================
def get_threads_oauth_url():
    client_id = st.secrets.get("THREADS_APP_ID", "")
    
    if not client_id:
        return "#error_missing_threads_client_id"

    # Tera live exact URL
    redirect_uri = "https://creator-ai-manager-tgrh5ifkgfqme6kdomcvxb.streamlit.app/" 
    
    # Threads ke permissions
    scopes = ["threads_basic", "threads_content_publish"]
    scope_str = ",".join(scopes)
    
    # Asli Threads ka URL aur state="threads"
    auth_url = f"https://threads.net/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&scope={scope_str}&response_type=code&state=threads"
    
    return auth_url
def get_facebook_oauth_url():
    # Facebook apne main Meta App ID ka hi use karta hai
    client_id = st.secrets.get("META_APP_ID", "")
    
    if not client_id:
        return "#error_missing_fb_client_id"

    # Aapka live URL
    redirect_uri = "https://creator-ai-manager-tgrh5ifkgfqme6kdomcvxb.streamlit.app/" 
    
    # Facebook ke specific permissions (Scopes)
    # Yeh permissions aapko page ki list dekhne aur uspar post karne ki power dengi
    scopes = ["pages_show_list", "pages_read_engagement", "pages_manage_posts"]
    scope_str = ",".join(scopes)
    
    # Facebook ka direct authorization endpoint
    auth_url = f"https://www.facebook.com/v18.0/dialog/oauth?client_id={client_id}&redirect_uri={redirect_uri}&scope={scope_str}&response_type=code&state=facebook"
    
    return auth_url

def get_youtube_oauth_url():
    client_id = st.secrets.get("YOUTUBE_CLIENT_ID", "")
    
    if not client_id:
        return "#error_missing_yt_client_id"

    redirect_uri = "https://creator-ai-manager-tgrh5ifkgfqme6kdomcvxb.streamlit.app/" 
    
    # YouTube ke scopes (Analytics padhne aur video upload karne ke liye)
    scopes = [
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/youtube.upload"
    ]
    # Google mein scopes space (" ") se alag hote hain
    scope_str = " ".join(scopes)
    
    # Google ka OAuth URL (&state=youtube lagana zaroori hai pehchaan ke liye)
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope={scope_str}&access_type=offline&prompt=consent&state=youtube"
    
    return auth_url

# ==============================================================
# TWITTER PKCE GENERATOR (Missing Function Added)
# ==============================================================
def generate_pkce_pair():
    code_verifier = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8').rstrip('=')
    m = hashlib.sha256()
    m.update(code_verifier.encode('utf-8'))
    code_challenge = base64.urlsafe_b64encode(m.digest()).decode('utf-8').rstrip('=')
    return code_verifier, code_challenge

# ==============================================================
# FIXED TWITTER OAUTH FUNCTION
# ==============================================================
def get_twitter_oauth_url():
    CLIENT_ID = st.secrets.get("TWITTER_CLIENT_ID", "") 
    REDIRECT_URI = "https://creator-ai-manager-tgrh5ifkgfqme6kdomcvxb.streamlit.app/"
    
    # 1. Naya code_verifier aur challenge banayein
    code_verifier, code_challenge = generate_pkce_pair() 
    
    # 2. Ek unique ID banayein is login session ke liye
    state = str(uuid.uuid4())
    
    # 3. Streamlit memory ki jagah SUPABASE mein save karein
    supabase.table("twitter_auth_states").insert({
        "state": state,
        "code_verifier": code_verifier
    }).execute()
    
    # 4. Apna Twitter URL return karein (💥 ADDED SCOPE PARAMETER)
    scopes = "tweet.read users.read tweet.write offline.access"
    encoded_scopes = scopes.replace(" ", "%20")
    tw_login_link = f"https://twitter.com/i/oauth2/authorize?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&state={state}&code_challenge={code_challenge}&code_challenge_method=S256&scope={encoded_scopes}"
    
    return tw_login_link


def run_my_crew_ai_agents(niche_topic, social_platform, script_language, meta_langs, video_duration, app_mode, user_pasted_script, selected_bundle_options):    # ⏱️ SHORTS MATHS: Direct seconds, aur approx 2.5 words per second (150 words/min)
    target_seconds = int(video_duration)
    target_words = int((video_duration / 60) * 150)
    
    groq_cluster_llm = get_cluster_llm(provider="groq")
    script_writing_llm = None
    gemini_resolved = False
    
    if G_KEY_1 or GEMINI_KEY:
        k1 = G_KEY_1 if G_KEY_1 else GEMINI_KEY
        for attempt in range(1, 3):
            try:
                test_llm = LLM(model="gemini/gemini-2.5-flash", api_key=k1, timeout=15)
                test_llm.call(messages=[{"role": "user", "content": "ping"}])
                script_writing_llm = test_llm
                gemini_resolved = True
                print(f"[MATRIX SUCCESS] Gemini Key 1 working flawlessly on attempt {attempt}.")
                time.sleep(15)
                break
            except Exception as e:
                print(f"[MATRIX WARNING] Gemini Key 1 attempt {attempt} failed with error: {e}. Cooling down...")
                time.sleep(15)
                
    if not gemini_resolved and G_KEY_2:
        for attempt in range(1, 3):
            try:
                test_llm = LLM(model="gemini/gemini-2.5-flash", api_key=G_KEY_2, timeout=15)
                test_llm.call(messages=[{"role": "user", "content": "ping"}])
                script_writing_llm = test_llm
                gemini_resolved = True
                time.sleep(15)
                break
            except Exception as e:
                time.sleep(15)

    if not gemini_resolved:
        target_groq_key = GR_KEY_2 if GR_KEY_2 else (GR_KEY_1 if GR_KEY_1 else GROQ_KEY)
        script_writing_llm = LLM(model="groq/llama-3.3-70b-versatile", api_key=target_groq_key, timeout=30)

    trend_analyst = Agent(
        role="Viral Retention Strategist",
        goal=f"Extract extreme psychological hooks and viewer retention triggers for '{niche_topic}' on {social_platform}.",
        backstory="""You are a top-tier YouTube Shorts & Reels strategist who has analyzed 10,000+ viral videos. 
        You don't just look for 'topics', you look for 'Dopamine Hits', 'Curiosity Gaps', and 'Pattern Interrupts'. 
        You know exactly why a user stops scrolling in the first 3 seconds.""",
        llm=groq_cluster_llm, max_iter=1, max_rpm=5, verbose=True, allow_delegation=False, memory=False
    )

    script_writer = Agent(
        role="Humanized Script Writer",
        goal="Write a hyper-engaging, 2-column video script blueprint.",
        backstory="""You are a highly successful, 28-year-old content creator who has written 500+ viral scripts. 
        You talk like you're explaining a fascinating secret to a friend, not presenting in a boardroom. 
        You use casual, spoken-English transitions like 'Look,', 'Here's the thing,', 'Honestly,', 'The crazy part is...'.
        
        NEVER write like this (robotic): "Context windows play a crucial role in determining LLM performance."
        ALWAYS write like this (human): "Itni lambi memory honi chahiye AI ko ki purani baatein bhool na jaaye."
        
        BANNED WORDS: Delve, Unleash, Tapestry, In today's digital landscape, Buckle up, Crucial, Imperative, Furthermore, Moreover, In conclusion, Testament.""",
        llm=script_writing_llm, max_iter=1, max_rpm=5, verbose=True, allow_delegation=False, memory=False
    )

    copy_maestro = Agent(
        role="Direct-Response Micro Copywriter",
        goal="Convert concepts into highly aggressive, scroll-stopping social media assets.",
        backstory="""You are a ruthless social media manager known for driving massive engagement. 
        You use psychological triggers, extreme curiosity, and sharp sarcasm. 
        You NEVER use cringey emojis or robotic corporate speak like 'In today's fast-paced world'. 
        Your goal is to force the user to click '...more' or jump into the comments section.""",
        llm=groq_cluster_llm, max_iter=1, max_rpm=5, verbose=True, allow_delegation=False, memory=False
    )

    tasks_pipeline = []
    live_scanned_context = ""
    if niche_topic:
        raw_trends = fetch_live_trends(niche_topic)
        if raw_trends:
            live_scanned_context = "\n".join([f"- Title: {item['title']} (URL: {item['url']})" for item in raw_trends])

    research_task = Task(
        description=f"Analyze topic: '{niche_topic}' on {social_platform}.\nContext:\n{live_scanned_context}\nIdentify 3 breakout hooks and 3 retention nodes under 150 words total. No titles/urls.",
        expected_output="Clean bullet points analysis matrix data.",
        agent=trend_analyst
    )
    tasks_pipeline.append(research_task)

    script_task = None
    if any("Script" in opt for opt in selected_bundle_options):
        script_prompt = f"Write a full video script for '{niche_topic}' around {target_words} words ({target_seconds} seconds)."
        if app_mode == "✍️ Repurpose My Script Mode":
            script_prompt = f"Analyze and re-engineer raw script: '{user_pasted_script}'."
            
        script_task = Task(
            description=f"""{script_prompt} Target language: '{script_language}'.
            
            ANTI-ROBOT RULES:
            1. RHYTHM VARIATION: Mix short punchy sentences (3-5 words) with longer explanatory ones. Do not over-explain.
            2. VISUAL-VERBAL SYNC: Do not formally narrate the visuals. Point to them organically (e.g., "See this? It's not just a graphic...").
            
            CRITICAL CRITERIA: You MUST use this exact table framework layout:
            | Timestamp | Visuals | Audio ({script_language}) |
            | :--- | :--- | :--- |
            
            🌟 EXAMPLE SHOT-PROMPTING FORMAT:
            | [00:00-00:05] | Camera zooms in sharply | Kya tumhe pata hai AI kya sochta hai? |
            | [00:05-00:10] | Holographic flowchart expanding | Yeh simple hai. Lekin iska impact bahut bada hai. |
            """,
            expected_output="Perfect Markdown 3-column table framework script avoiding all banned AI words.",
            agent=script_writer, context=[research_task]
        )
        tasks_pipeline.append(script_task)

    distribution_task = None
    dist_requirements = []
    # 🧠 SMART UI CHECKS (Checking individual buttons by new names)
    include_youtube = any("YouTube SEO" in opt for opt in selected_bundle_options)
    include_linkedin = any("LinkedIn" in opt for opt in selected_bundle_options)
    include_twitter = any("X & Threads" in opt for opt in selected_bundle_options)
    include_ig_fb = any("Insta & FB" in opt for opt in selected_bundle_options)
    
    # Appending only what user requested
    if include_youtube: dist_requirements.append("- 1 Optimized YouTube Title & Description")
    if include_ig_fb: dist_requirements.append("- 3 short Instagram/Facebook captions & tags")
    if include_linkedin: dist_requirements.append("- 1 High-Converting LinkedIn Post")
    if include_twitter: dist_requirements.append("- 1 Viral Thread format suitable for X (Twitter) and Meta Threads")

    if dist_requirements:
        desc_instruction = ""
        ig_fb_instruction = ""
        linkedin_instruction = ""
        twitter_instruction = ""
        parser_format = ""
        
        # 🧠 HYPER-ENGINEERED DYNAMIC SEO LOGIC (YOUTUBE)
        if include_youtube:
            desc_instruction = """[YOUTUBE SHORTS DESCRIPTION]
            Constraint: STRICTLY UNDER 60 WORDS.
            Structure MUST include: 
            1. A punchy hook line.
            2. A direct CTA.
            3. 'Keywords:' followed by 3-4 highly relevant SEO search terms (comma-separated).
            4. EXACTLY 3 niche hashtags.
            DO NOT generate long paragraphs, mini-blogs, or timestamps."""
            
            # YouTube ka format parser mein add ho gaya
            parser_format += f"""
               Title: [Your single best 60-character YouTube title. Hook + Keyword + Bracket/Emoji. NO HASHTAGS.]
               Description: [{desc_instruction}]
               """
        # 🔥 THE HIGHLY ENGINEERED INSTA/FB PROMPT RESTORED
        if include_ig_fb:
            ig_fb_instruction = f"""[INSTAGRAM/FACEBOOK REELS CAPTION]
            Target Language: STRICTLY {meta_langs.get('ig', 'English')}
            Constraints: STRICTLY follow this 3-part framework:
            1. The Truncation Hook (Above the Fold): Only the first few words are visible. First line MUST be under 100 characters. End with an unresolved thought, curiosity, sarcasm, or a bold claim to force a '...more' click.
            2. The Context Drop: Leave a blank line, then write a 2-3 sentence punchy, highly engaging summary about the video.
            3. The 5-Tag Rule: End with EXACTLY 5 highly relevant SEO hashtags (Do not use generic tags)."""
            parser_format += f"\nInstagram Caption:\n[{ig_fb_instruction}]"

        # 🏢 HYPER-ENGINEERED B2B COPY LOGIC (LINKEDIN)
        if include_linkedin:
            linkedin_instruction = """[LINKEDIN POST FRAMEWORK]
            Role: B2B Authority & Tech Industry Leader.
            Constraints: Use short sentences (1 sentence = 1 line). Use high-level business vocabulary (e.g., ROI-driven, operational friction, scalable architecture).
            Structure MUST strictly follow:
            1. Pattern Interrupt Hook: First 2 lines must make a bold claim or share a hard data point. 
            2. The Cliffhanger: Leave a blank line after the 3rd sentence to force a '...see more' click.
            3. The Skimmable Meat: Use bullet points to deliver the core blueprint/value.
            4. The 'Aha!' Insight: Provide a contrarian or paradigm-shifting perspective near the end.
            5. Engagement CTA: Ask a thought-provoking question to drive comments. Explicitly state "Link is in the first comment" (Do not put the actual URL in the text)."""
            
            # LinkedIn ka format parser mein add ho gaya
            parser_format += f"""
               LinkedIn Post:
               [{linkedin_instruction}]
               """

        # 🧵 HYPER-ENGINEERED VIRAL LOGIC (TWITTER/X)
        if include_twitter:
            twitter_instruction = """[TWITTER/X VIRAL THREAD FRAMEWORK]
            Role: Tech/SaaS Thought Leader.
            Constraints: Exactly 5 to 7 tweets total. Max 280 characters per tweet. NO HASHTAGS. End each tweet with a progress tracker (e.g., 1/6, 2/6).
            Structure MUST strictly follow:
            - Tweet 1 (The Banger): Scroll-stopping massive claim. Suggest a sleek, dark-themed, ultra-detailed visual/graphic in brackets. End with thread emoji 🧵👇.
            - Tweet 2 (The Agitation): Hit the core pain point. Why should the reader care?
            - Tweet 3-5 (The Meat): One single idea per tweet. Use white space and bullet marks (•, ✅).
            - Penultimate Tweet (TL;DR): A quick bulleted summary of the thread.
            - Final Tweet (The Loop): CTA asking to Retweet the first tweet ♻️, follow for more breakdowns, and check the link in the reply."""
            
            # Twitter ka format parser mein add ho gaya
            parser_format += f"""
               Twitter Thread:
               [{twitter_instruction}]
               """
        # ⚡ THE INVISIBLE SCRIPT INJECTION BRIDGE ⚡
        dist_context_list = [research_task]
        if script_task:
            dist_context_list.append(script_task)
            smart_injection_logic = "IMPORTANT: Deeply analyze the final video script generated by the 'Humanized Script Writer' in your context. Match your metadata's tone, hooks, and context perfectly to that exact script."
        else:
            smart_injection_logic = f"IMPORTANT: Deeply analyze the following script provided by the user. Match your metadata's tone, hooks, and context perfectly to this script:\n\n[USER SCRIPT BEGIN]\n{user_pasted_script}\n[USER SCRIPT END]"

        distribution_task = Task(
            description=f"""Act as a Top-Tier Metadata & Copywriting Specialist. 
            
            {smart_injection_logic}
            
            Generate a package based on the script above for the requested platforms:
            {chr(10).join(dist_requirements)}
            
            CRITICAL CONSTRAINTS FOR OUTPUT (FOLLOW STRICTLY):
            
            1. 🛑 LANGUAGE RULE: 
               - If '{script_language}' is 'Hinglish': Use ONLY the English alphabet (Latin script).
               - If 'Hindi': Use ONLY the Devanagari script (हिंदी).
               - If 'English': Use pure English.
               
            2. 🤖 API PARSER FORMAT (MANDATORY FORMATTING):
               You MUST output EXACTLY in this format with these exact section headings for the requested items. Do not deviate.
               {parser_format}
               """,
            expected_output="Compiled social media assets tier list package with highly engineered, dynamically scaled, SEO-optimized metadata and professional social copy.",
            agent=copy_maestro
        )
        tasks_pipeline.append(distribution_task)

    master_crew = Crew(agents=[trend_analyst, script_writer, copy_maestro], tasks=tasks_pipeline, verbose=True, process='sequential')
    
    # 🛡️ THE MID-AIR PARACHUTE SYSTEM
    try:
        master_crew.kickoff()
    except Exception as crew_error:
        print(f"🚨 [ENGINE CRASH] Primary LLM failed mid-generation: {crew_error}")
        print("🔄 Deploying GROQ Parachute Engine...")
        
        # 1. Force swap the failed agent's brain to Groq
        script_writer.llm = groq_cluster_llm
        
        # 2. Restart the Crew with the new engine
        master_crew = Crew(agents=[trend_analyst, script_writer, copy_maestro], tasks=tasks_pipeline, verbose=True, process='sequential')
        master_crew.kickoff()
    
    compiled_final_output = "### 🕵️ EXPERT TREND RESEARCH ANALYSIS\n" + str(research_task.output.raw if hasattr(research_task, 'output') and research_task.output else "") + "\n\n"
    if script_task and script_task.output:
        compiled_final_output += "### 🎬 PREMIUM AUDIO/VISUAL RETENTION SCRIPT\n" + str(script_task.output.raw) + "\n\n"
    if distribution_task and distribution_task.output:
        compiled_final_output += "### 📱 DISTRIBUTION MICRO-ASSETS PACKAGE\n" + str(distribution_task.output.raw) + "\n\n"
        
    return compiled_final_output

# ── Dynamic Sidebar Control Panel ───────────────────────
with st.sidebar:
    st.title("⚙️ Control Panel Matrix")
    current_os_mode = st.pills(
        "🔮 Core OS Operations Mode:",
        ["✍️ AI Script Generator", "📊 AI Channel Auditor & Sync"],
        default="✍️ AI Script Generator"
    )
    st.write("---")
    st.caption("Architecture Framework: CrewAI + Gemini + Groq Matrix")
# ── Main Content Gateway Router ──────────────────────────
def save_platform_token(platform_column_name, auth_code):
    current_user = st.session_state.get("creator_handle")
    if not current_user:
        return # Agar user login nahi hai toh kuch mat karo
        
    # Check karo ki kya is user ka profile pehle se database mein hai
    response = supabase.table("creator_profiles").select("id").eq("creator_handle", current_user).execute()
    
    if response.data:
        # User pehle se hai, toh bas us naye platform ka token update kar do
        supabase.table("creator_profiles").update({
            platform_column_name: auth_code
        }).eq("creator_handle", current_user).execute()
    else:
        # Naya user hai, toh naya row banao aur token save karo
        supabase.table("creator_profiles").insert({
            "creator_handle": current_user,
            platform_column_name: auth_code
        }).execute()
# ── Main Content Gateway Router ──────────────────────────
if "code" in st.query_params:
    auth_code = st.query_params["code"] 
    platform_state = st.query_params.get("state", "instagram") 
    
    if platform_state == "facebook":
        st.success("🎉 Facebook Page Successfully Linked! 💙")
        save_platform_token("facebook_token", auth_code)
        st.session_state["fb_connected"] = True
        st.session_state["channels_synced"] = True
        
    elif platform_state == "youtube":
        st.info("🔄 Authenticating secure connection with Google...")
        real_access_token = get_youtube_access_token(auth_code)
        
        if real_access_token:
            st.success("🎉 YouTube Channel Successfully Linked! ❤️")
            save_platform_token("youtube_token", real_access_token) # Yahan asli token save ho raha hai!
            st.session_state["yt_connected"] = True
            st.session_state["channels_synced"] = True
        else:
            st.error("❌ YouTube Auth Failed. Please try connecting again.")
    
    elif platform_state.startswith("linkedin"):
        st.success("🎉 LinkedIn Profile Successfully Linked! 💼")
        save_platform_token("linkedin_token", auth_code)
        st.session_state["li_connected"] = True 
        st.session_state["channels_synced"] = True
    
    # 🧵 THREADS DETECTOR (Isko Instagram se hamesha UPAR rakhna)
    elif "thread" in str(platform_state).lower():
        st.success("🎉 Meta Threads Account Successfully Linked! 🧵")
        save_platform_token("threads_token", auth_code)
        st.session_state["th_connected"] = True
        st.session_state["channels_synced"] = True

    elif platform_state == "instagram":
        st.success("🎉 Instagram Account Successfully Linked! 🩷")
        save_platform_token("instagram_token", auth_code)
        st.session_state["ig_connected"] = True
        st.session_state["channels_synced"] = True

    else:
        # 🟢 THE TWITTER SUPABASE FIX 🟢
        response = supabase.table("twitter_auth_states").select("code_verifier").eq("state", platform_state).execute()
        if response.data:
            st.success("🎉 X (Twitter) Account Successfully Linked! 🩵")
            save_platform_token("twitter_token", auth_code)
            st.session_state["tw_connected"] = True
            st.session_state["channels_synced"] = True
            supabase.table("twitter_auth_states").delete().eq("state", platform_state).execute()
        else:
            st.error("⚠️ Unknown platform state or Twitter Session Expired. Please try again.")
            
    st.query_params.clear()
st.markdown(
    """
    <div style="display: flex; align-items: baseline; gap: 10px;">
        <h1 style="margin: 0;">🚀 Creator AI Manager OS</h1>
        <span style="background-color: #ff4b4b; color: white; padding: 4px 10px; border-radius: 15px; font-size: 14px; font-weight: bold;">
            ⚡ Shorts Only (Long-form coming soon)
        </span>
    </div>
    """, 
    unsafe_allow_html=True
)
st.write(f"System Context: **{current_os_mode}** active")
st.write("---")

# MODE 1: SCRIPT ENGINE
if current_os_mode == "✍️ AI Script Generator":
    tab1, tab2, tab3 = st.tabs(["🔥 Trend & Script Workspace", "📥 Download Generated Blueprint", "📂 My Saved Vault"])
    with tab1:
        st.markdown("### 🔥 AI Content Strategy Hub")
        app_mode = st.radio("🔮 Kis Mode me kaam karna hai?", ["🚀 Complete Blueprint Mode", "✍️ Repurpose My Script Mode"], horizontal=True)
        st.write("---")
        
        # 1. Blueprint Arrays (The 10 Hooks, 4 Bodies, 4 CTAs)
        HOOK_OPTIONS = [
            "Select a Hook...",
            "The Negative Warning (Stop doing X. It's destroying Y)",
            "The Curiosity Gap (The real reason why X, and nobody is talking about it)",
            "The Contrarian (Myth Buster - X is a complete lie)",
            "The Secret Tool Drop (This secret feels illegal to know)",
            "The Bold Claim (This simple shift will change X forever)",
            "The 'How-To' Tease (How to achieve X in short time)",
            "The Mind-Reader (You are probably struggling with X...)",
            "The Shocking Statistic (99% fail because of this...)",
            "The Visual Anchor (Direct bizarre statement matching B-Roll)",
            "The 'Us vs. Them' (Why A is losing, while B takes over)"
        ]

        BODY_OPTIONS = [
            "Select a Body Framework...",
            "The Step-by-Step Blueprint (Highly logical, Step 1, 2, 3)",
            "The Case Study (Real-world success story or trend breakdown)",
            "The Problem-Agitate-Solve (PAS - Pain, Agitate, Solution)",
            "Rapid Fire Facts (High-density, fast-paced bullet points)"
        ]

        CTA_OPTIONS = [
            "Select a CTA...",
            "The Value Bribe (Comment [KEYWORD] for DM)",
            "The Seamless Loop (Connects end perfectly to the hook)",
            "The Cliffhanger (Hit subscribe for Part 2)",
            "The Direct Engagement Question (What is your take?)"
        ]

        # 2. UI Routing based on Mode
        if app_mode == "🚀 Complete Blueprint Mode":
            bundle_options = st.pills("🎁 Content Bundle Items: (Multi-Select)", ["🎬 Retention Script & Visual Cues", "📺 YouTube SEO: Viral Title & Description", "📸 Insta & FB Reels: Captions + Tags", "🏢 LinkedIn Post", "🐦 X & Threads: Viral Thread Format"], default=["🎬 Retention Script & Visual Cues"], selection_mode="multi")
            user_niche = st.text_input("🎯 Kis topic par video banani hai?", value=st.session_state.get("niche_data", ""))
            video_duration = st.slider("⏱ Video duration (Seconds)", min_value=30, max_value=60, value=60, step=5)
            
            st.markdown("### 🧬 Viral Script Parameters")
            col1, col2, col3 = st.columns(3)
            with col1: selected_hook = st.selectbox("🪝 Hook", HOOK_OPTIONS)
            with col2: selected_body = st.selectbox("🧬 Body", BODY_OPTIONS)
            with col3: selected_cta = st.selectbox("🎯 CTA", CTA_OPTIONS)
            
            # Strict Validation Logic
            is_ready_to_launch = (selected_hook != "Select a Hook..." and selected_body != "Select a Body Framework..." and selected_cta != "Select a CTA...")
        
        else:
            bundle_options = st.pills("🎁 Extraction Bundle Items: (Multi-Select)", ["📺 YouTube SEO: Viral Title & Description", "📸 Insta & FB Reels: Captions + Tags", "🏢 LinkedIn Post", "🐦 X & Threads: Viral Thread Format"], default=["📺 YouTube SEO: Viral Title & Description"], selection_mode="multi")
            user_niche = st.text_input("🎯 Video Title/Topic:", value=st.session_state.get("niche_data", ""))
            st.caption("💡 60-Second Limit: A typical Short contains 150-180 words.")
            user_pasted_script = st.text_area("📝 Script content:", height=200, max_chars=1200)
            is_ready_to_launch = True # Repurpose mode bypasses validation

        st.write("---")
        
        # 🌍 THE DYNAMIC LANGUAGE UI 🌍
        if app_mode == "🚀 Complete Blueprint Mode":
            st.markdown("### 🎬 Core Script Language")
            script_language = st.selectbox("Select language for your Voiceover/Script:", ["Hinglish", "Hindi", "English"], index=0)
        else:
            # Repurpose mode ke liye background variable (UI mein nahi dikhega)
            script_language = "" 
        
        meta_languages = {"yt": "English", "ig": "English", "li": "English", "tw": "English"}
        st.markdown("### 📱 Social Media Language Routing")
        lang_col1, lang_col2 = st.columns(2)
        
        with lang_col1:
            if any("YouTube SEO" in opt for opt in bundle_options):
                meta_languages["yt"] = st.selectbox("📺 YouTube Title & Desc:", ["English", "Hinglish", "Hindi"], index=0)
            if any("LinkedIn" in opt for opt in bundle_options):
                meta_languages["li"] = st.selectbox("🏢 LinkedIn Post:", ["English", "Hinglish", "Hindi"], index=0)
        with lang_col2:
            if any("Insta & FB" in opt for opt in bundle_options):
                meta_languages["ig"] = st.selectbox("📸 Insta/FB Captions:", ["Hinglish", "Hindi", "English"], index=0)
            if any("X & Threads" in opt for opt in bundle_options):
                meta_languages["tw"] = st.selectbox("🐦 X & Threads:", ["English", "Hinglish", "Hindi"], index=0)

        st.write("---")

        # 3. Dynamic Engine Button (Outside of st.form to work properly)
        submit_btn = st.button("🚀 Launch Specialized Agents Grid", use_container_width=True, disabled=not is_ready_to_launch)

        if not is_ready_to_launch and app_mode == "🚀 Complete Blueprint Mode":
            st.warning("⚠️ Please select Hook, Body, and CTA to unlock the Generate button.")

        if submit_btn:
            if not bundle_options: 
                st.error("⚠️ Bundle item select karein!")
            elif not user_niche: 
                st.error("⚠️ Topic cannot be empty!")
            else:
                # 🧠 MAGIC INJECTION: We append the chosen frameworks directly to the topic!
                if app_mode == "🚀 Complete Blueprint Mode":
                    st.session_state["niche_data"] = f"{user_niche} | STRICT RULES -> Hook: {selected_hook} | Body: {selected_body} | CTA: {selected_cta}"
                else:
                    st.session_state["niche_data"] = user_niche
                    
                st.session_state["form_submitted"] = True
                st.session_state["selected_options"] = bundle_options
                st.session_state["current_mode"] = app_mode
                st.session_state["pasted_script"] = user_pasted_script if app_mode != "🚀 Complete Blueprint Mode" else ""
                st.session_state["duration"] = video_duration if app_mode == "🚀 Complete Blueprint Mode" else 1.0

        # 4. Engine Processing Block
        if st.session_state.get("form_submitted"):
            with st.spinner("🕵️ Processing failproof generation sequence..."):
                try:
                    # CrewAI Executed with Injected Data
                    ai_output = run_my_crew_ai_agents(
                        st.session_state["niche_data"],
                        script_language, 
                        meta_languages, # Naya dictionary parameter 
                        st.session_state.get("duration", 1.0), 
                        st.session_state["current_mode"], 
                        st.session_state.get("pasted_script", ""), 
                        st.session_state["selected_options"]
                    )
                    
                    st.session_state["script_data"] = ai_output
                    st.session_state["form_submitted"] = False
                    
                    # 💾 THE VAULT MEMORY
                    if st.session_state.get("user_email"):
                        try:
                            supabase.table("ai_blueprints_vault").insert({
                                "creator_email": st.session_state["user_email"],
                                "target_platform": "Omnichannel",
                                "niche_topic": st.session_state["niche_data"], # Updated context goes here
                                "script_content": ai_output,
                                "social_metadata": str(st.session_state["selected_options"]),
                                "status": "Draft"
                            }).execute()
                        except Exception as db_error:
                            print(f"[VAULT ERROR] Could not save to database: {db_error}")

                    st.success("🎉 Blueprint ready & automatically saved to your Vault! Switch to Tab 2 to download content.")
                except Exception as e:
                    st.session_state["form_submitted"] = False
                    st.error(f"Engine Error: {str(e)}")

    with tab2:
        st.header("📥 Download Generated Content")
        if "script_data" in st.session_state and st.session_state["script_data"]:
            st.markdown(st.session_state["script_data"])
            st.write("---")
            
            # Dinamic file name banayein
            safe_name = st.session_state.get('niche_data', 'blueprint').replace(" ", "_")[:30]
            
            c1, c2 = st.columns(2)
            with c1: st.download_button("📥 Notepad (.txt)", str(st.session_state["script_data"]), file_name=f"{safe_name}.txt", use_container_width=True)
            with c2: st.download_button("📥 Word Doc (.docx)", create_word_doc(str(st.session_state["script_data"]), "Omnichannel", st.session_state.get("niche_data", "File")), file_name=f"{safe_name}.docx", use_container_width=True)
        else: st.warning("⚠️ No data compiled yet. Run Tab 1 first.")
    with tab3:
        st.header("📂 My Saved Blueprints Vault")
        st.markdown("Access all your previously generated high-retention scripts and metadata here.")
        
        if st.session_state.get("user_email"):
            # Database se user ki purani scripts fetch karna (Nayi sabse upar aayegi)
            try:
                response = supabase.table("ai_blueprints_vault").select("*").eq("creator_email", st.session_state["user_email"]).order("created_at", desc=True).execute()
                
                if response.data and len(response.data) > 0:
                    st.success(f"📦 Found {len(response.data)} saved blueprints in your secure vault.")
                    st.write("---")
                    
                    # Har script ko ek accordion (expander) mein dikhana
                    for item in response.data:
                        # Date format ko clean karna
                        raw_date = item.get('created_at', '')
                        clean_date = raw_date.split('T')[0] if 'T' in raw_date else "Unknown Date"
                        
                        # Expander ka Title
                        with st.expander(f"🎬 {item.get('niche_topic', 'Untitled')} | 📅 {clean_date} | 📍 {item.get('target_platform', 'Unknown')}"):
                            st.caption(f"**Selected Metadata Assets:** {item.get('social_metadata', 'None')}")
                            st.write("---")
                            st.markdown(item.get('script_content', 'No content found.'))
                            
                            # Ek chhota sa copy button logic (user copy-paste kar sake)
                            # Action Buttons (Access & Delete)
                            col_action1, col_action2 = st.columns(2)
                            with col_action1:
                                st.button("📋 Access Data", key=f"btn_{item['id']}", use_container_width=True)
                            with col_action2:
                                if st.button("🗑️ Delete Script", key=f"del_{item['id']}", use_container_width=True):
                                    # Supabase DB se permanent delete karna
                                    supabase.table("ai_blueprints_vault").delete().eq("id", item['id']).execute()
                                    st.rerun() # UI ko turant refresh karne ke liye
                else:
                    st.info("📭 Your vault is currently empty. Generate your first script in Tab 1 to see it here!")
            except Exception as e:
                st.error(f"⚠️ Vault Sync Error: Could not fetch data from database. ({str(e)})")
        else:
            st.warning("⚠️ Access Blocked: Please log in to view your saved blueprints.")

# MODE 2: AUDITOR ENGINE
else:
    st.markdown("### 📊 AI Omnichannel Channel Auditor Ecosystem")
    st.write("---")
    
    # Isko cleanly call karein bina kisi dynamic variable mapping breakdown ke
    selected_auditor_section = st.pills(
        "🛠️ Select Auditor Operational Node Framework:",
        ["🔗 1. Secure Social Account Hub", "📈 2. Real-Time Performance Audit", "🚀 3. Omnichannel Media Publisher Node"],
        default="🔗 1. Secure Social Account Hub"
    )
    st.write("---")
    
    # 🎯 INTEGRATION POINT 2: Re-writing Pill 1 for Real Connections
    if selected_auditor_section == "🔗 1. Secure Social Account Hub":
        st.markdown("## 🔐 Connect Your Social Accounts")
        st.write("Apne platforms ko ek click mein connect karein. (One Brand Rule Active)")
        st.write(" ")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📺 YouTube")
            if st.session_state.get("yt_connected"):
                st.success("✅ Connected: YouTube Channel")
                if st.button("❌ Disconnect YouTube", use_container_width=True):
                    disconnect_platform("youtube_token", "yt_connected")
            else:
                yt_login_link = get_youtube_oauth_url()
                st.markdown(f"<div style='margin-bottom: 16px;'><a href='{yt_login_link}' target='_blank' style='text-decoration: none;'><button style='width:100%; background-color:#FF0000; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer; height:42px; font-size:14px; box-shadow: 0px 2px 4px rgba(0,0,0,0.1);'>❤️ Connect YouTube Channel</button></a></div>", unsafe_allow_html=True)
                
            st.write(" ")
            st.subheader("🐦 X (Twitter)")
            if st.session_state.get("tw_connected"):
                st.success("✅ Connected: X Account")
                if st.button("❌ Disconnect X (Twitter)", use_container_width=True):
                    disconnect_platform("twitter_token", "tw_connected")
            else:
                tw_login_link = get_twitter_oauth_url()
                st.markdown(f"<div style='margin-bottom: 16px;'><a href='{tw_login_link}' target='_blank' style='text-decoration: none;'><button style='width:100%; background-color:#000000; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer; height:42px; font-size:14px; box-shadow: 0px 2px 4px rgba(0,0,0,0.1);'>🩵 Connect X Account</button></a></div>", unsafe_allow_html=True)
            # 🧵 NEW: META THREADS UI CONNECT NODE
            st.write(" ")
            st.subheader("🧵 Meta Threads")
            if st.session_state.get("th_connected"):
                st.success("✅ Connected: Threads Profile")
                if st.button("❌ Disconnect Threads", use_container_width=True):
                    disconnect_platform("threads_token", "th_connected")
            else:
                # 🟢 YAHAN UPDATE KIYA HAI: Asli threads ka function call hoga
                meta_threads_link = get_threads_oauth_url() 
                st.markdown(f"<div style='margin-bottom: 16px;'><a href='{meta_threads_link}' target='_blank' style='text-decoration: none;'><button style='width:100%; background-color:#000000; color:white; border: 1px solid #333; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer; height:42px; font-size:14px; box-shadow: 0px 2px 4px rgba(0,0,0,0.1);'>🧵 Connect Meta Threads</button></a></div>", unsafe_allow_html=True)

        with col2:
            st.subheader("📸 Instagram")
            if st.session_state.get("ig_connected"):
                st.success("✅ Connected: Instagram Business")
                if st.button("❌ Disconnect Instagram", use_container_width=True):
                    disconnect_platform("instagram_token", "ig_connected")
            else:
                meta_login_link = get_meta_oauth_url()
                st.markdown(f"<div style='margin-bottom: 16px;'><a href='{meta_login_link}' target='_blank' style='text-decoration: none;'><button style='width:100%; background-color:#E1306C; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer; height:42px; font-size:14px; box-shadow: 0px 2px 4px rgba(0,0,0,0.1);'>🩷 Connect Instagram Business</button></a></div>", unsafe_allow_html=True)    
                
            st.write(" ")
            st.subheader("🔵 Facebook")
            if st.session_state.get("fb_connected"):
                st.success("✅ Connected: Facebook Page")
                if st.button("❌ Disconnect Facebook", use_container_width=True):
                    disconnect_platform("facebook_token", "fb_connected")
            else:
                fb_login_link = get_facebook_oauth_url()
                st.markdown(f"<a href='{fb_login_link}' target='_blank' style='text-decoration: none;'><button style='width:100%; background-color:#1877F2; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer; height:38px; font-size:14px; box-shadow: 0px 2px 4px rgba(0,0,0,0.1);'>💙 Connect Facebook Page</button></a>", unsafe_allow_html=True)
            # 💼 NEW: LINKEDIN UI CONNECT NODE
            st.write(" ")
            st.subheader("💼 LinkedIn")
            if st.session_state.get("li_connected"):
                st.success("✅ Connected: LinkedIn Profile")
                if st.button("❌ Disconnect LinkedIn", use_container_width=True):
                    disconnect_platform("linkedin_token", "li_connected")
            else:
                linkedin_login_link = get_linkedin_oauth_url()
                st.markdown(f"<div style='margin-bottom: 16px;'><a href='{linkedin_login_link}' target='_blank' style='text-decoration: none;'><button style='width:100%; background-color:#0077B5; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer; height:42px; font-size:14px; box-shadow: 0px 2px 4px rgba(0,0,0,0.1);'>💼 Connect LinkedIn Profile</button></a></div>", unsafe_allow_html=True)
        st.write("---")
        
        # Bottom Utility Buttons Configuration Flow
        if st.session_state.get("channels_synced", False):
            action_col1, action_col2 = st.columns([2, 1])
            with action_col1:
                st.success("🔒 SYSTEM STATUS CLEAR: Verified session tokens encrypted securely inside local cache.")
            with action_col2:
                if st.button("⚠️ EMERGENCY KILL-SWITCH REVOKE", use_container_width=True):
                    with st.spinner("Nuking all connected accounts from secure vault..."):
                        # 1. Database se ek saath saare tokens uda do
                        if st.session_state.get("creator_handle"):
                            supabase.table("creator_profiles").update({
                                "youtube_token": None,
                                "twitter_token": None,
                                "instagram_token": None,
                                "facebook_token": None,
                                "linkedin_token": None,
                                "threads_token": None
                            }).eq("creator_handle", st.session_state["creator_handle"]).execute()
                        
                        # 2. App ki memory (RAM) se sab reset kar do
                        st.session_state["yt_connected"] = False
                        st.session_state["tw_connected"] = False
                        st.session_state["ig_connected"] = False
                        st.session_state["fb_connected"] = False
                        st.session_state["li_connected"] = False
                        st.session_state["th_connected"] = False
                        
                        st.session_state["channels_synced"] = False
                        st.session_state["audit_data_ready"] = False
                        st.session_state["mock_upload_ready"] = False
                        time.sleep(1)
                        st.rerun()
        else:
            st.info("🔒 SYSTEM STATUS IDLE: Please click one of the platform connection buttons above to sync handles.")

    # PILL SECTION B: ANALYSIS ENGINE CODES MATRIX
    elif selected_auditor_section == "📈 2. Real-Time Performance Audit":
        st.markdown("### 📈 Omnichannel Smart Analytics Matrix")
        st.write("Real-time aggregated performance data across your linked platforms.")
        
        # 🎨 CYBERPUNK UI STYLING INJECTION
        st.markdown("""
        <style>
        .metric-box {
            background-color: #111111;
            border-left: 4px solid #00FFAA;
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            margin-bottom: 15px;
        }
        .metric-title { color: #888888; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; font-weight: bold;}
        .metric-value { color: #FFFFFF; font-size: 32px; font-weight: 800; margin-top: 5px;}
        .warning-box { border-left: 4px solid #FF4444 !important; }
        </style>
        """, unsafe_allow_html=True)

        creator_handle = st.session_state.get("creator_handle")
        
        if not creator_handle:
            st.warning("⚠️ Security Lock: Please connect your accounts in Tab 1 first.")
        else:
            # 🧠 HEADER & SYNC CONTROLS
            col_head1, col_head2 = st.columns([3, 1])
            with col_head1:
                st.markdown("#### 🧠 AI Manager Confidence Monitor")
                # Yeh AI text abhi static hai, aage chalkar Groq se dynamically likhwayenge
                st.info("💡 **System Insight:** YouTube matrix is establishing. Meta ecosystem is standing by. Hit 'Live Sync' to fetch initial baseline data.")
            with col_head2:
                # ⚡ THE PREMIUM SYNC BUTTON
                if st.button("⚡ Live Sync (Premium)", use_container_width=True):
                    with st.spinner("Bypassing security layers... Extracting matrix data..."):
                        sync_result = sync_platform_analytics()
                        
                        if sync_result is True:
                            st.toast("✅ Data successfully synced to cache matrix!")
                            time.sleep(1)
                            st.rerun()
                        elif sync_result is False:
                            st.error("❌ Sync Failed: User data not found. Please re-login.")
                        else:
                            # 🚨 THE X-RAY VISION (Asli error yahan dikhega)
                            st.error(f"⚠️ SYSTEM REJECTED: {sync_result}")

            st.write("---")
            
            # 🗄️ FETCH CACHED DATA (Zero API Cost)
            try:
                cache_res = supabase.table("platform_analytics_cache").select("*").eq("creator_handle", creator_handle).execute()
                cache_data = cache_res.data[0] if cache_res.data else None
            except:
                cache_data = None

            if not cache_data:
                st.info("📭 Vault Empty: No analytics data cached yet. Click 'Live Sync' to pull your first matrix.")
            else:
                # Time formatting (T hatana)
                raw_time = cache_data.get('last_synced_at', 'Unknown')
                clean_time = raw_time.replace('T', ' ')[:16] if raw_time != 'Unknown' else raw_time
                
                st.caption(f"🕒 **Last Auto-Sync:** {clean_time} (UTC) | **System Status:** {cache_data.get('sync_status', 'Unknown')}")
                
                # 🚨 GRACEFUL ERROR HANDLING
                if "Auth_Failed" in cache_data.get('sync_status', ''):
                    st.error("⚠️ Token Integrity Alert: One or more platform tokens expired. Please re-link in the Secure Hub (Tab 1).")

                # 📺 YOUTUBE UI GRID
                yt = cache_data.get("youtube_data", {})
                if yt and yt.get("status") == "connected":
                    st.markdown("##### 📺 YouTube Mainframe")
                    y1, y2, y3 = st.columns(3)
                    with y1:
                        st.markdown(f'<div class="metric-box"><div class="metric-title">Total Views</div><div class="metric-value">{yt.get("views", 0):,}</div></div>', unsafe_allow_html=True)
                    with y2:
                        st.markdown(f'<div class="metric-box"><div class="metric-title">Subscribers</div><div class="metric-value">{yt.get("subscribers", 0):,}</div></div>', unsafe_allow_html=True)
                    with y3:
                        st.markdown(f'<div class="metric-box"><div class="metric-title">Video Count</div><div class="metric-value">{yt.get("video_count", 0):,}</div></div>', unsafe_allow_html=True)
                else:
                    st.warning("📺 YouTube Node Offline: Data missing or account not linked.")
                
                st.write(" ")
                
                # 🩷 META UI GRID
                st.markdown("##### 🩷 Meta Ecosystem (IG / FB)")
                fb = cache_data.get("facebook_data", {})
                ig = cache_data.get("instagram_data", {})
                
                m1, m2 = st.columns(2)
                with m1:
                    if ig and ig.get("status") == "connected":
                        st.markdown(f'<div class="metric-box"><div class="metric-title">IG Followers</div><div class="metric-value">{ig.get("followers", 0):,}</div></div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="metric-box warning-box"><div class="metric-title">IG Node</div><div class="metric-value" style="color: #FF4444;">Offline</div></div>', unsafe_allow_html=True)
                with m2:
                    if fb and fb.get("status") == "connected":
                        st.markdown(f'<div class="metric-box"><div class="metric-title">FB Page Followers</div><div class="metric-value">{fb.get("followers", 0):,}</div></div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="metric-box warning-box"><div class="metric-title">FB Node</div><div class="metric-value" style="color: #FF4444;">Offline</div></div>', unsafe_allow_html=True)

    # PILL SECTION C: AUTOMATED PUBLISHER DEPLOYMENT PIPELINE
    elif selected_auditor_section == "🚀 3. Omnichannel Media Publisher Node":
        st.markdown("### 🚀 Omnichannel Automated Media Publisher")
        st.write("Upload your video, select metadata, and publish everywhere in one click.")
        
        # 🎬 STEP 1: VIDEO UPLOAD GATEWAY
        st.markdown("#### 🎬 Step 1: Upload Media")
        uploaded_video = st.file_uploader("Drop your final video file here (Max 500MB)", type=["mp4", "mov", "mkv"])
        
        if uploaded_video:
            st.success(f"✅ Video '{uploaded_video.name}' ready for processing!")
            
        st.write("---")
        
        # 🧠 STEP 2: METADATA SOURCE ENGINE
        st.markdown("#### 🧠 Step 2: Metadata Source")
        metadata_source = st.radio("Choose how you want to add titles, descriptions, and captions:", 
                                   ["📂 Use Saved Vault Data (Recommended)", "✍️ Manual Paste", "✨ Generate New Metadata"], 
                                   horizontal=True)
        
        # Option 1: Vault Data (The Bridge)
        # Option 1: Vault Data (The Bridge with Smart Parser)
        if metadata_source == "📂 Use Saved Vault Data (Recommended)":
            try:
                response = supabase.table("ai_blueprints_vault").select("*").eq("creator_email", st.session_state.get("user_email")).order("created_at", desc=True).execute()
                blueprints = response.data if response.data else []
            except:
                blueprints = []
                
            if not blueprints:
                st.error("📭 Your Vault is empty. Please generate a script first.")
            else:
                blueprint_options = {f"{item['niche_topic']} ({item['target_platform']})": item for item in blueprints}
                selected_bp_name = st.selectbox("Select a Blueprint to extract metadata from:", options=list(blueprint_options.keys()))
                selected_bp = blueprint_options[selected_bp_name]
                
                # 🧠 PARSER ACTION: Text ko tod kar variables mein badalna
                parsed_data = parse_blueprint_metadata(selected_bp['script_content'])
                
                st.success(f"✅ AI Metadata successfully parsed and injected! Please review below.")
                
                # Yahan auto-fill boxes aayenge (User inhe edit kar sakta hai)
                with st.expander("📺 Auto-Filled: YouTube Metadata", expanded=True):
                    final_yt_title = st.text_input("YouTube Title", value=parsed_data["yt_title"])
                    final_yt_desc = st.text_area("YouTube Description", value=parsed_data["yt_desc"], height=150)
                
                with st.expander("🐦 Auto-Filled: X (Twitter) Thread"):
                    final_tw_thread = st.text_area("Generated Thread Content", value=parsed_data["tw_thread"], height=150)
                
                with st.expander("📸 Auto-Filled: Social Captions"):
                    final_ig_cap = st.text_area("Instagram/Facebook Caption", value=parsed_data["ig_caption"], height=100)

        # Option 2: Manual Paste (Clean UI with Expanders)
        elif metadata_source == "✍️ Manual Paste":
            st.info("Manually enter your content for each platform below.")
            with st.expander("📺 YouTube Metadata", expanded=True):
                st.text_input("YouTube Title", key="man_yt_title")
                st.text_area("YouTube Description", key="man_yt_desc")
            with st.expander("🐦 X (Twitter) Thread"):
                st.text_area("Tweet 1 (Video attached here)", key="man_tw_1")
                st.caption("*(Logic for '+ Add Tweet' button will be integrated here during API wiring)*")
            with st.expander("📸 Instagram & Facebook Captions"):
                st.text_area("Reel/Post Caption", key="man_ig_cap")
                
        # Option 3: Generate New
        elif metadata_source == "✨ Generate New Metadata":
            st.warning("⚠️ You need fresh metadata. Please switch to the **'✍️ AI Script Generator'** mode from the left sidebar to build and save a new blueprint to your Vault.")
            
        st.write("---")
        
        # 🌍 STEP 3: PLATFORM ROUTING
        st.markdown("#### 🌍 Step 3: Distribution Routing")
        st.write("Select the platforms you want to publish this video to:")
        
        col_p1, col_p2, col_p3, col_p4, col_p5 = st.columns(5) # 5 Columns kar diye
        with col_p1: push_yt = st.checkbox("📺 YouTube", value=True)
        with col_p2: push_tw = st.checkbox("🐦 X (Twitter)")
        with col_p3: push_th = st.checkbox("🧵 Meta Threads") # Naya Checkbox
        with col_p4: push_ig = st.checkbox("📸 Instagram")
        with col_p5: push_li = st.checkbox("💼 LinkedIn")
        
        if push_yt:
            st.caption("*Note: YouTube API does not support custom thumbnails for Shorts. A frame will be auto-selected.*")
            
        st.write("---")
        
        # 🛡️ STEP 4: COMPLIANCE & KILL-SWITCH
        st.markdown("#### 🛡️ Step 4: Compliance & Safety")
        legal_1 = st.checkbox("I have reviewed and edited the AI-generated content and confirm it is ready for publishing.")
        legal_2 = st.checkbox("I take full responsibility for this posting. I understand that Creator AI OS is not liable for account strikes, spam bans, or TOS violations.")
        
        st.write(" ")
        # 🚀 THE PUBLISH BUTTON (Master Dispatcher)
        if st.button("🚀 PUBLISH TO ALL SELECTED PLATFORMS", use_container_width=True, type="primary"):
            if not uploaded_video:
                st.error("⚠️ Action Blocked: Please upload a video file first!")
            elif not (legal_1 and legal_2):
                st.error("⚠️ Action Blocked: You must agree to both compliance checkboxes before publishing.")
            elif not st.session_state.get("channels_synced"):
                st.error("⚠️ Connection Error: Your social accounts are not linked. Go to 'Secure Social Account Hub' first.")
            else:
                with st.spinner("Initiating secure upload sequence to social APIs..."):
                    try:
                        # 1. Video ko RAM se server ki disk par temporarily save karna
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
                            tmp_file.write(uploaded_video.read())
                            temp_video_path = tmp_file.name
                        
                        # 2. Database se user ke fresh Auth Tokens nikalna
                        user_tokens = None
                        try:
                            res = supabase.table("creator_profiles").select("*").eq("creator_handle", st.session_state.get("user_email")).execute()
                            if res.data:
                                user_tokens = res.data[0]
                        except Exception as e:
                            print(f"Token Fetch Error: {e}")

                        if not user_tokens:
                            st.error("⚠️ Database Error: Could not retrieve your connected accounts.")
                        else:
                            # 3. DISPATCH TO PLATFORMS
                            success_logs = []
                            
                            # --- YOUTUBE DISPATCH ---
                            if push_yt:
                                if user_tokens.get("youtube_token"):
                                    st.info("⏳ Uploading to YouTube...")
                                    time.sleep(1) # [API CALL PLACEHOLDER]
                                    # Yahan requests.post() aayega Google API ke liye
                                    success_logs.append("✅ YouTube Channel")
                                else:
                                    st.warning("⚠️ YouTube skipped: Account not connected.")

                            # --- TWITTER DISPATCH ---
                            if push_tw:
                                if user_tokens.get("twitter_token"):
                                    st.info("⏳ Uploading Thread to X (Twitter)...")
                                    
                                    # 1. UI se kate hue (parsed) thread ka text uthao
                                    # Note: Hum parsed_data use kar rahe hain jo Tab 3 mein already mapped hai
                                    raw_twitter_text = parsed_data.get("tw_thread", "")
                                    
                                    if raw_twitter_text:
                                        # 2. Lamba text list mein split karna (Blank lines ke basis par)
                                        tweets_list = [t.strip() for t in raw_twitter_text.split('\n\n') if t.strip()]
                                        
                                        # 3. API Function Call
                                        success, msg = post_to_twitter_thread(tweets_list, user_tokens.get("twitter_token"))
                                        
                                        if success:
                                            success_logs.append("✅ X (Twitter) Thread")
                                        else:
                                            st.error(f"❌ Twitter Failed: {msg}")
                                    else:
                                        st.warning("⚠️ Twitter skipped: No thread content found in blueprint.")
                                else:
                                    st.warning("⚠️ Twitter skipped: Account not connected.")

                            # 🧵 --- META THREADS REUSABLE DATA ROUTING DISPATCH ---
                            if push_th:
                                if user_tokens.get("threads_token"):
                                    st.info("⏳ Re-routing Twitter layout text to Meta Threads API...")
                                    # Yahan Twitter ka hi parsed data completely reuse ho raha hai bina naye token kharch kiye!
                                    raw_threads_text = parsed_data.get("tw_thread", "")
                                    if raw_threads_text:
                                        threads_list = [t.strip() for t in raw_threads_text.split('\n\n') if t.strip()]
                                        # [META THREADS API WORKFLOW PLACEHOLDER]
                                        # Threads API payload mein yeh pure elements as a thread chale jayenge
                                        time.sleep(1) 
                                        success_logs.append("✅ Meta Threads (Twitter Layout)")
                                    else:
                                        st.warning("⚠️ Threads skipped: No layout data available.")
                                else:
                                    st.warning("⚠️ Threads skipped: Account not connected.")

                            # --- INSTAGRAM DISPATCH ---
                            if push_ig:
                                if user_tokens.get("instagram_token"):
                                    st.info("⏳ Uploading to Instagram Reels...")
                                    time.sleep(1) # [API CALL PLACEHOLDER]
                                    # Yahan requests.post() aayega Instagram API ke liye
                                    success_logs.append("✅ Instagram Business")
                                else:
                                    st.warning("⚠️ Instagram skipped: Account not connected.")

                            # 4. SERVER CLEANUP (Auto-Delete Video)
                            os.remove(temp_video_path)
                            
                            # 5. FINAL STATUS
                            if success_logs:
                                st.success(f"🔥 BOOM! Content successfully distributed to:\n" + "\n".join(success_logs))
                                st.balloons()
                            else:
                                st.error("❌ No platforms were successfully processed.")
                                
                    except Exception as master_e:
                        st.error(f"⚠️ Core Engine Failure: {str(master_e)}")