# analytics_engine.py
import requests

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
                return {
                    "views": int(stats.get("viewCount", 0)),
                    "subscribers": int(stats.get("subscriberCount", 0)),
                    "video_count": int(stats.get("videoCount", 0)),
                    "status": "connected"
                }
            else:
                return {"error": "Channel not found", "status": "failed"}
        elif response.status_code == 401:
            return {"error": "Token Expired", "status": "auth_failed"}
        else:
            return {"error": f"API Error: {response.status_code}", "status": "failed"}
            
    except Exception as e:
        print(f"[YT ANALYTICS ERROR] {str(e)}")
        return {"error": str(e), "status": "failed"}

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