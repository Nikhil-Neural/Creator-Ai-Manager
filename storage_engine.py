import streamlit as st
import requests

def upload_video_to_telegram(video_file_bytes, file_name="video.mp4"):
    """
    Streamlit buffer se bytes lekar Telegram Private Channel par upload karta hai
    aur direct high-speed download network URL return karta hai.
    """
    # Secrets file se secure tokens load karna
    bot_token = st.secrets["TELEGRAM_BOT_TOKEN"]
    chat_id = st.secrets["TELEGRAM_CHAT_ID"]
    
    # Telegram API Endpoint for sending video documents
    url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
    
    # Payload metrics setup mapping
    payload = {
        'chat_id': chat_id,
        'caption': f"Uploaded via Creator OS App: {file_name}"
    }
    
    # Continuous network byte-stream pipeline injection
    files = {
        'video': (file_name, video_file_bytes, 'video/mp4')
    }
    
    try:
        response = requests.post(url, data=payload, files=files)
        response_data = response.json()
        
        if response_data.get("ok"):
            # 3. Yahan bhi 'document' hata kar 'video' lagao
            file_id = response_data["result"]["video"]["file_id"]
            
            # File absolute path generation logic via bot gateway
            file_path_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
            path_response = requests.get(file_path_url).json()
            
            if path_response.get("ok"):
                inner_path = path_response["result"]["file_path"]
                # 🚀 The Ultimate Direct Download URL
                final_download_url = f"https://api.telegram.org/file/bot{bot_token}/{inner_path}"
                return final_download_url
            else:
                st.error("Telegram file path mapping block crashed!")
                return None
        else:
            st.error(f"Telegram API Upload Error: {response_data.get('description')}")
            return None
            
    except Exception as e:
        st.error(f"Storage System critical error: {str(e)}")
        return None