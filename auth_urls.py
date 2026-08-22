import requests
import streamlit as st
import uuid
import base64
import os
import hashlib
from db_engine import get_supabase_admin_client
import tweepy

# Twitter aur baaki platforms ke auth state ko save karne ke liye admin database connection
supabase_admin = get_supabase_admin_client()

# ==============================================================
# 🧠 THE NEW BAGGAGE COUNTER (GLOBAL STATE GENERATOR)
# ==============================================================
def create_global_state(platform_name):
    """
    Yeh function user ka email aur ek unique ticket banata hai, 
    usko Database mein save karta hai, aur ticket wapas bhejta hai.
    """
    user_email = st.session_state.get("user_email")
    
    # Ek unique ticket generate karo (e.g., youtube_8f3a9b)
    unique_ticket = f"{platform_name}_{uuid.uuid4().hex[:8]}"
    
    if user_email:
        try:
            # Ticket ko database mein save kar do
            supabase_admin.table("global_auth_states").insert({
                "state_id": unique_ticket,
                "creator_handle": user_email
            }).execute()
        except Exception as e:
            print(f"[DB ERROR] Could not save global state: {e}")
            
    return unique_ticket

# ==============================================================
# LINKEDIN OAUTH FUNCTION
# ==============================================================
def get_linkedin_oauth_url():
    client_id = st.secrets.get("LINKEDIN_CLIENT_ID", "")
    
    if not client_id:
        return "#error_missing_linkedin_client_id"

    redirect_uri = "https://creator-ai-manager-tgrh5ifkgfqme6kdomcvxb.streamlit.app/" 
    
    scopes = ["openid", "profile", "email", "w_member_social"]
    scope_str = "%20".join(scopes)
    
    # 🚀 SMART TICKET GENERATOR
    state = create_global_state("linkedin")
    
    auth_url = f"https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&state={state}&scope={scope_str}"
    
    return auth_url

# ==============================================================
# META THREADS OAUTH FUNCTION
# ==============================================================
def get_threads_oauth_url():
    # 🚀 HACK: Bypass st.secrets aur seedha ID hardcode kar diya
    client_id = "2128519801042338" 

    redirect_uri = "https://creator-ai-manager-tgrh5ifkgfqme6kdomcvxb.streamlit.app/" 
    
    scopes = ["threads_basic", "threads_content_publish"]
    scope_str = ",".join(scopes)
    
    state = create_global_state("thread")
    
    auth_url = f"https://threads.net/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&scope={scope_str}&response_type=code&state={state}"
    
    return auth_url

# ==============================================================
# FACEBOOK / META OAUTH FUNCTION
# ==============================================================
def get_facebook_oauth_url():
    client_id = st.secrets.get("META_APP_ID", "")
    if not client_id:
        return "#error_missing_fb_client_id"

    redirect_uri = "https://creator-ai-manager-tgrh5ifkgfqme6kdomcvxb.streamlit.app/"
    
    scopes = [
        "public_profile",
        "pages_show_list",
        "pages_read_engagement",
        "business_management",
        "instagram_basic",
        "instagram_manage_insights",
        "instagram_content_publish"
    ]
    scope_str = ",".join(scopes)
    
    # 🚀 SMART TICKET GENERATOR
    state = create_global_state("facebook")
    
    auth_url = f"https://www.facebook.com/v20.0/dialog/oauth?client_id={client_id}&redirect_uri={redirect_uri}&scope={scope_str}&response_type=code&state={state}&auth_type=rerequest"
    
    return auth_url

# ==============================================================
# YOUTUBE OAUTH FUNCTION
# ==============================================================
def get_youtube_oauth_url():
    client_id = st.secrets.get("YOUTUBE_CLIENT_ID", "")
    
    if not client_id:
        return "#error_missing_yt_client_id"

    redirect_uri = "https://creator-ai-manager-tgrh5ifkgfqme6kdomcvxb.streamlit.app/" 
    
    scopes = [
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/youtube.upload"
    ]
    scope_str = " ".join(scopes)
    
    # 🚀 SMART TICKET GENERATOR
    state = create_global_state("youtube")
    
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope={scope_str}&access_type=offline&prompt=consent&state={state}"
    
    return auth_url

# ==============================================================
# TWITTER PKCE GENERATOR
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
    """OAuth 1.0a URL banata hai taaki Token + Secret dono mil sakein"""
    CALLBACK_URL = "https://creator-ai-manager-tgrh5ifkgfqme6kdomcvxb.streamlit.app/"
    
    oauth1_user_handler = tweepy.OAuth1UserHandler(
        st.secrets["TWITTER_API_KEY"],
        st.secrets["TWITTER_API_SECRET"],
        callback=CALLBACK_URL
    )
    
    auth_url = oauth1_user_handler.get_authorization_url()
    
    st.session_state['tw_request_token'] = oauth1_user_handler.request_token['oauth_token']
    st.session_state['tw_request_secret'] = oauth1_user_handler.request_token['oauth_token_secret']
    
    return auth_url

# ==============================================================
# ACCESS TOKEN EXCHANGERS
# ==============================================================
def get_meta_access_token(auth_code):
    """Kachhe Auth Code ko Meta API par bhej kar asli Access Token laata hai."""
    client_id = st.secrets.get("META_APP_ID", "")
    client_secret = st.secrets.get("META_APP_SECRET", "") 
    redirect_uri = "https://creator-ai-manager-tgrh5ifkgfqme6kdomcvxb.streamlit.app/" 
    
    url = f"https://graph.facebook.com/v18.0/oauth/access_token?client_id={client_id}&redirect_uri={redirect_uri}&client_secret={client_secret}&code={auth_code}"
    
    try:
        response = requests.get(url)
        data = response.json()
        if "access_token" in data:
            return data["access_token"]
        else:
            print(f"[META TOKEN ERROR] API rejected code: {data}")
            return None
    except Exception as e:
        print(f"[META TOKEN EXCEPTION] {str(e)}")
        return None

def get_youtube_access_token(auth_code):
    """Kachhe Auth Code ko Google ke server par bhej kar asli Access Token laata hai."""
    client_id = st.secrets.get("YOUTUBE_CLIENT_ID", "")
    client_secret = st.secrets.get("YOUTUBE_CLIENT_SECRET", "") 
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
            return f"GOOGLE_ERROR: {response.text}" 
    except Exception as e:
        return f"SYSTEM_ERROR: {str(e)}"
    
def get_threads_access_token(auth_code):
    url = "https://graph.threads.net/oauth/access_token"
    clean_code = auth_code.replace("#_=_", "")
    
    payload = {
        "client_id": "2128519801042338", # Tumhara Hardcoded ID
        "client_secret": st.secrets["THREADS_APP_SECRET"],
        "grant_type": "authorization_code",
        "redirect_uri": "https://creator-ai-manager-tgrh5ifkgfqme6kdomcvxb.streamlit.app/", 
        "code": clean_code
    }
    
    try:
        # STEP 1: Get Short-Lived Token (1 Hour)
        response = requests.post(url, data=payload).json()
        
        if "access_token" in response:
            short_lived_token = response["access_token"]
            
            # 🚀 STEP 2: Swap it for a Long-Lived Token (60 Days)
            exchange_url = "https://graph.threads.net/access_token"
            exchange_params = {
                "grant_type": "th_exchange_token",
                "client_secret": st.secrets["THREADS_APP_SECRET"],
                "access_token": short_lived_token
            }
            
            long_lived_res = requests.get(exchange_url, params=exchange_params).json()
            
            if "access_token" in long_lived_res:
                print("✅ BOOM! 60-Day Long-Lived Threads Token Generated!")
                return long_lived_res["access_token"]
            else:
                # Agar exchange fail hua toh backup ke liye short token de do
                return short_lived_token 
        else:
            st.error(f"🔍 META ERROR DETAILS: {response}") 
            return None
            
    except Exception as e:
        st.error(f"🚨 REQUEST CRASHED: {e}")
        return None