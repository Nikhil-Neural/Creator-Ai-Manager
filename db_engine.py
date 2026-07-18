import streamlit as st
from supabase import create_client, Client

def get_supabase_client() -> Client:
    """Supabase connection runtime active client initialization"""
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

def insert_schedule_queue(creator_email, platforms, video_url, scheduled_time, metadata_payload):
    """
    Supabase master_scheduler_queue table mein dynamic parameters block insert karta hai.
    """
    supabase = get_supabase_client()
    
    data_entry = {
        "creator_handle": creator_email,
        "target_platforms": platforms,  # Array matching list format ['youtube', 'twitter']
        "video_url": video_url,         # Direct Telegram storage link string 
        "scheduled_time": scheduled_time.isoformat(), # Timestring formatting
        "status": "pending",
        "metadata_payload": metadata_payload # Dynamic JSONB Matrix Block
    }
    
    try:
        response = supabase.table("master_scheduler_queue").insert(data_entry).execute()
        return response
    except Exception as e:
        st.error(f"Database insertion structural failure: {str(e)}")
        return None