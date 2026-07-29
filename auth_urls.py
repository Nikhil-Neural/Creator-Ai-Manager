import requests
import streamlit as st
import uuid
import base64
import os
import hashlib
from db_engine import get_supabase_admin_client

# Twitter auth state ko save karne ke liye admin database connection
supabase_admin = get_supabase_admin_client()

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
    
    state = "linkedin_" + str(uuid.uuid4())[:8]
    
    auth_url = f"https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&state={state}&scope={scope_str}"
    
    return auth_url

# ==============================================================
# META THREADS OAUTH FUNCTION
# ==============================================================
def get_threads_oauth_url():
    client_id = st.secrets.get("THREADS_APP_ID", "")
    
    if not client_id:
        return "#error_missing_threads_client_id"

    redirect_uri = "https://creator-ai-manager-tgrh5ifkgfqme6kdomcvxb.streamlit.app/" 
    
    scopes = ["threads_basic", "threads_content_publish"]
    scope_str = ",".join(scopes)
    
    auth_url = f"https://threads.net/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&scope={scope_str}&response_type=code&state=threads"
    
    return auth_url

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
        "instagram_manage_insights"
    ]
    scope_str = ",".join(scopes)
    
    auth_url = f"https://www.facebook.com/v20.0/dialog/oauth?client_id={client_id}&redirect_uri={redirect_uri}&scope={scope_str}&response_type=code&state=facebook&auth_type=rerequest"
    
    return auth_url

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
    
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope={scope_str}&access_type=offline&prompt=consent&state=youtube"
    
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
    CLIENT_ID = st.secrets.get("TWITTER_CLIENT_ID", "") 
    REDIRECT_URI = "https://creator-ai-manager-tgrh5ifkgfqme6kdomcvxb.streamlit.app/"
    
    code_verifier, code_challenge = generate_pkce_pair() 
    state = str(uuid.uuid4())
    
    response = supabase_admin.table("twitter_auth_states").insert({
        "state": state,
        "code_verifier": code_verifier
    }).execute()
    
    scopes = "tweet.read users.read tweet.write offline.access"
    encoded_scopes = scopes.replace(" ", "%20")
    tw_login_link = f"https://twitter.com/i/oauth2/authorize?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&state={state}&code_challenge={code_challenge}&code_challenge_method=S256&scope={encoded_scopes}"
    
    return tw_login_link
# 🔐 META TOKEN EXCHANGE OVEN (FUNCTION A)
def get_meta_access_token(auth_code):
    """
    Kachhe Auth Code ko Meta API par bhej kar asli Access Token laata hai.
    """
    client_id = st.secrets.get("META_APP_ID", "")
    client_secret = st.secrets.get("META_APP_SECRET", "") # ⚠️ YEH NAYA SECRET CHAHIYE HOGA
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
    """
    Kachhe Auth Code ko Google ke server par bhej kar asli Access Token laata hai.
    """
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
            # 🛑 ERROR KO CHHUPANA NAHI HAI, SEEDHA BHEJNA HAI
            return f"GOOGLE_ERROR: {response.text}" 
    except Exception as e:
        return f"SYSTEM_ERROR: {str(e)}"