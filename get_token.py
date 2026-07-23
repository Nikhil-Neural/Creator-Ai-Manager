import streamlit as st
from google_auth_oauthlib.flow import InstalledAppFlow

# 1. Streamlit ke secrets se Client ID aur Secret uthana
client_id = st.secrets["GOOGLE_CLIENT_ID"]
client_secret = st.secrets["GOOGLE_CLIENT_SECRET"]

# 2. Google OAuth ka configuration setup karna
client_config = {
    "installed": {
        "client_id": client_id,
        "client_secret": client_secret,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

# 3. YouTube Upload ka permission (scope)
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def main():
    print("Google OAuth Flow start ho raha hai...")
    
    # Flow initialize karna
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    
    # Local server chalu karke token fetch karna (prompt='consent' force karega refresh token dene ke liye)
    credentials = flow.run_local_server(port=8080, prompt='consent')
    
    print("\n" + "="*50)
    print("SUCCESS! 🎉 Yahan se niche wala REFRESH TOKEN copy karo:")
    print("="*50 + "\n")
    
    print(credentials.refresh_token)
    
    print("\n" + "="*50)
    print("Is token ko copy karke apne .streamlit/secrets.toml mein is tarah save kar lo:")
    print('YOUTUBE_REFRESH_TOKEN = "tumhara-token-yahan"')

if __name__ == "__main__":
    main()