# analytics_engine.py
import requests

def _youtube_access_token_from_refresh(refresh_token):
    """Exchange a stored YouTube refresh token for a short-lived access token."""
    import streamlit as st

    client_id = st.secrets.get("YOUTUBE_CLIENT_ID", "")
    client_secret = st.secrets.get("YOUTUBE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return None, "Missing YOUTUBE_CLIENT_ID or YOUTUBE_CLIENT_SECRET in app secrets."

    try:
        response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=15,
        )
        payload = response.json()
        if response.status_code != 200 or not payload.get("access_token"):
            error = payload.get("error_description") or payload.get("error") or f"HTTP {response.status_code}"
            if payload.get("error") == "invalid_grant":
                return None, "YouTube connection expired or was revoked. Please reconnect YouTube."
            return None, f"Google token refresh failed: {error}"
        return payload["access_token"], None
    except requests.RequestException as exc:
        return None, f"Google token refresh request failed: {exc}"
    except ValueError:
        return None, "Google token endpoint returned an unreadable response."


def fetch_youtube_analytics(refresh_token):
    """Fetch channel statistics using the saved refresh token."""
    if not refresh_token:
        return {"error": "YouTube is not connected. Please reconnect.", "status": "auth_failed"}

    access_token, refresh_error = _youtube_access_token_from_refresh(refresh_token)
    if not access_token:
        return {"error": refresh_error or "Could not refresh YouTube credentials.", "status": "auth_failed"}

    url = "https://www.googleapis.com/youtube/v3/channels?part=statistics&mine=true"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data.get("items"):
                stats = data["items"][0].get("statistics", {})
                return {
                    "views": int(stats.get("viewCount", 0)),
                    "subscribers": int(stats.get("subscriberCount", 0)),
                    "video_count": int(stats.get("videoCount", 0)),
                    "status": "connected",
                }
            return {"error": "Channel not found for this Google account.", "status": "failed"}
        if response.status_code == 401:
            return {"error": "YouTube rejected the refreshed access token. Please reconnect YouTube.", "status": "auth_failed"}
        try:
            detail = response.json().get("error", {}).get("message", f"HTTP {response.status_code}")
        except ValueError:
            detail = f"HTTP {response.status_code}"
        return {"error": f"YouTube API error: {detail}", "status": "failed"}
    except requests.RequestException as exc:
        return {"error": str(exc), "status": "failed"}

def fetch_meta_analytics(access_token):
    """
    Correct 3-step chain:
    User Token → Page Token → Instagram Business ID → Analytics
    """
    base_url = "https://graph.facebook.com/v20.0"
    
    fb_data = {"followers": 0, "status": "offline"}
    ig_data = {"followers": 0, "status": "offline"}
    
    try:
        me_res = requests.get(f"{base_url}/me?fields=id,name&access_token={access_token}").json()
        
        if "error" in me_res:
            error_msg = me_res['error']['message']
            return {
                "facebook": {"status": "failed", "error": error_msg},
                "instagram": {"status": "failed", "error": error_msg}
            }
        
        pages_res = requests.get(f"{base_url}/me/accounts?access_token={access_token}").json()
        
        if "data" in pages_res and len(pages_res["data"]) > 0:
            page = pages_res["data"][0]
            page_id = page["id"]
            page_token = page["access_token"]
            page_name = page.get("name", "Your Page")
            
            page_res = requests.get(f"{base_url}/{page_id}?fields=followers_count,fan_count&access_token={page_token}").json()
            
            fb_data = {
                "name": page_name,
                "followers": page_res.get("followers_count", page_res.get("fan_count", 0)),
                "status": "connected"
            }
            
            ig_account_res = requests.get(f"{base_url}/{page_id}?fields=instagram_business_account&access_token={page_token}").json()
            ig_account = ig_account_res.get("instagram_business_account")
            
            if ig_account:
                ig_id = ig_account["id"]
                ig_res = requests.get(f"{base_url}/{ig_id}?fields=username,followers_count,media_count,profile_picture_url&access_token={page_token}").json()
                
                if "error" not in ig_res:
                    ig_data = {
                        "username": ig_res.get("username", ""),
                        "followers": ig_res.get("followers_count", 0),
                        "media_count": ig_res.get("media_count", 0),
                        "status": "connected"
                    }
                else:
                    ig_data = {"status": "failed", "error": ig_res["error"]["message"]}
            else:
                ig_data = {"status": "failed", "error": "No Instagram Business account linked."}
        else:
            fb_data = {"status": "failed", "error": "No Facebook Page found."}
            ig_data = {"status": "failed", "error": "Facebook Page required first."}
            
    except Exception as e:
        return {
            "facebook": {"status": "failed", "error": str(e)},
            "instagram": {"status": "failed", "error": str(e)}
        }
    
    return {"facebook": fb_data, "instagram": ig_data}