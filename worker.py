import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

def upload_to_youtube(video_path, title, description, refresh_token, client_id, client_secret):
    """
    Background worker function to upload video to YouTube.
    """
    # 1. Background worker auto-generates fresh credentials using the refresh token
    creds = Credentials(
        None, # No initial access token needed
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret
    )
    
    # 2. Build the YouTube API client
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)
    
    # 3. Setup Metadata (Title, Description, Tags, Privacy)
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["AI", "Tech", "CreatorOS"],
            "categoryId": "28" # 28 is for Science & Technology
        },
        "status": {
            "privacyStatus": "public", # ya "private" / "unlisted"
            "selfDeclaredMadeForKids": False
        }
    }
    
    # 4. Load the compressed video file
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    
    # 5. Execute the upload request
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )
    
    response = request.execute()
    return response.get("id") # Returns the YouTube Video ID