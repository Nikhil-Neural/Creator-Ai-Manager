import streamlit as st
import requests
import subprocess
import tempfile
import os

def compress_video_ffmpeg(video_bytes):
    """
    FFmpeg engine: CRF 18 (Visually Lossless) ke sath file size reduce karta hai.
    """
    # 1. Temporary files setup karna
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_in, \
         tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_out:
        
        temp_in.write(video_bytes)
        temp_in_path = temp_in.name
        temp_out_path = temp_out.name

    try:
        # 2. FFmpeg Command (CRF 18 for high quality, fast preset for speed)
        command = [
            'ffmpeg', '-y', '-i', temp_in_path,
            '-vcodec', 'libx264', '-crf', '18', '-preset', 'fast',
            '-c:a', 'aac', '-b:a', '128k', temp_out_path
        ]
        
        # 3. Process run karna (without printing unnecessary logs to UI)
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        
        # 4. Compressed bytes read karna
        with open(temp_out_path, 'rb') as f:
            compressed_bytes = f.read()
            
        return compressed_bytes
        
    except Exception as e:
        print(f"FFmpeg Compression Failed: {e}")
        return None # Agar fail hua toh None return karega
        
    finally:
        # 5. Server se kachra (temp files) delete karna
        if os.path.exists(temp_in_path): os.remove(temp_in_path)
        if os.path.exists(temp_out_path): os.remove(temp_out_path)


def upload_video_to_telegram(video_file_bytes, file_name="video.mp4"):
    """
    Streamlit buffer se bytes lekar Telegram Private Channel par upload karta hai
    aur direct high-speed download network URL return karta hai.
    """
    bot_token = st.secrets["TELEGRAM_BOT_TOKEN"]
    chat_id = st.secrets["TELEGRAM_CHAT_ID"]
    
    # ⚡ ENGINE INJECTION: Upload hone se pehle video compress karo
    st.info("⚙️ FFmpeg Engine: Compressing video at CRF 18...")
    compressed_bytes = compress_video_ffmpeg(video_file_bytes)
    
    # Agar compression successful raha toh compressed file use karo, warna original
    final_upload_bytes = compressed_bytes if compressed_bytes else video_file_bytes
    
    # NAYA ENDPOINT: sendVideo
    url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
    
    payload = {
        'chat_id': chat_id,
        'caption': f"Uploaded via Creator OS App: {file_name}",
        'supports_streaming': True # Important for Telegram players
    }
    
    # DOCUMENT ki jagah VIDEO key
    files = {
        'video': (file_name, final_upload_bytes, 'video/mp4')
    }
    
    try:
        response = requests.post(url, data=payload, files=files)
        response_data = response.json()
        
        if response_data.get("ok"):
            # DOCUMENT ki jagah VIDEO se file_id extract karo
            file_id = response_data["result"]["video"]["file_id"]
            
            file_path_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
            path_response = requests.get(file_path_url).json()
            
            if path_response.get("ok"):
                inner_path = path_response["result"]["file_path"]
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