import streamlit as st
import boto3
import subprocess
import tempfile
import os
import uuid
from pathlib import Path

# 🚨 FIXED: Max 200MB file limit set for DoS and RAM protection
MAX_VIDEO_SIZE = 200 * 1024 * 1024 

def compress_video_ffmpeg(temp_in_path, temp_out_path):
    """
    FFmpeg engine: CRF 18 ke sath file size reduce karta hai.
    Return values: True (Success) or False (Failed)
    """
    try:
        command = [
            'ffmpeg', '-y', '-i', temp_in_path,
            '-vcodec', 'libx264', '-crf', '18', '-preset', 'fast',
            '-c:a', 'aac', '-b:a', '128k', temp_out_path
        ]
        # 300s Timeout for DoS protection
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=300)
        return True
    except subprocess.TimeoutExpired:
        print("FFmpeg compression timed out")
        return False
    except Exception as e:
        print(f"FFmpeg Compression Failed: {e}")
        return False


def upload_video_to_r2(video_file_bytes, file_name="video.mp4"):
    """
    Video ko temp disk par rakhta hai, compress karta hai, aur RAM ko bypass karke seedha R2 mein upload karta hai.
    """
    # 🚨 FIXED: File size guard
    if len(video_file_bytes) > MAX_VIDEO_SIZE:
        st.error("Video file is too large. Max limit is 200MB.")
        return None

    # Disk par file write karo taaki RAM bache
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_in, \
         tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_out:
        
        temp_in.write(video_file_bytes)
        temp_in_path = temp_in.name
        temp_out_path = temp_out.name

    try:
        st.info("⚙️ FFmpeg Engine: Compressing video at CRF 18...")
        success = compress_video_ffmpeg(temp_in_path, temp_out_path)
        
        # 🚨 FIXED: Agar compression fail hui, toh error de do, original ko upload mat karo
        if not success:
            st.error("Video processing/compression failed. Please try a different file.")
            return None

        # Sanitize filename and create R2 Key
        safe_file_name = Path(file_name).name
        unique_file_name = f"{uuid.uuid4().hex}_{safe_file_name}"
        r2_key = f"videos/{unique_file_name}"
        
        s3_client = boto3.client(
            's3',
            endpoint_url=st.secrets["R2_ENDPOINT_URL"],
            aws_access_key_id=st.secrets["R2_ACCESS_KEY"],
            aws_secret_access_key=st.secrets["R2_SECRET_KEY"],
            region_name='auto'
        )
        
        # 🚨 FIXED: RAM bypass karke directly disk se file upload ho rahi hai
        s3_client.upload_file(
            temp_out_path, 
            st.secrets["R2_BUCKET_NAME"], 
            r2_key,
            ExtraArgs={'ContentType': 'video/mp4'}
        )
        
        return r2_key
        
    except Exception as e:
        print(f"R2 upload error: {e}")
        st.error("Video upload failed. Please try again.")
        return None
        
    finally:
        # Hamesha disk se kachra saaf karo
        if os.path.exists(temp_in_path): os.remove(temp_in_path)
        if os.path.exists(temp_out_path): os.remove(temp_out_path)


def generate_presigned_url(r2_key, expiration=3600):
    """
    Publish/Preview time par DB se r2_key fetch karke temporary URL banata hai.
    """
    try:
        s3_client = boto3.client(
            's3',
            endpoint_url=st.secrets["R2_ENDPOINT_URL"],
            aws_access_key_id=st.secrets["R2_ACCESS_KEY"],
            aws_secret_access_key=st.secrets["R2_SECRET_KEY"],
            region_name='auto'
        )
        
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': st.secrets["R2_BUCKET_NAME"], 'Key': r2_key},
            ExpiresIn=expiration
        )
        return url
    except Exception as e:
        print(f"Presigned URL generation error: {e}")
        return None