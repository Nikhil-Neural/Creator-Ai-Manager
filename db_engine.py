import streamlit as st
from supabase import create_client, Client
import json

def insert_schedule_queue(creator_email, platforms, video_url, scheduled_time, metadata_payload):
    """
    Restored to target the original master_scheduler_queue for true Omnichannel routing.
    """
    try:
        # Hum directly admin client use kar rahe hain jo tumhari file mein already defined hai
        supabase = get_supabase_admin_client()
        
        payload = {
            "creator_handle": creator_email, # Tumhari table mein creator_handle hai
            "target_platforms": platforms,   # Tumhara original array (e.g. ['twitter'])
            "video_url": video_url,
            "scheduled_time": scheduled_time.isoformat(),
            "metadata_payload": metadata_payload,
            "status": "Pending"
        }
        
        response = supabase.table("master_scheduler_queue").insert(payload).execute()
        return response.data # Success hone par data return karega
        
    except Exception as e:
        print(f"Database Sync Error: {str(e)}")
        return None # Fail hone par None return karega

def get_supabase_client() -> Client:
    """Supabase connection runtime active client initialization for public reads if needed"""
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"] # Standard Anon Key
    return create_client(url, key)

def get_supabase_admin_client() -> Client:
    """🛡️ Master Admin Client initialization that safely bypasses RLS for backend writes"""
    url: str = st.secrets["SUPABASE_URL"]
    admin_key: str = st.secrets["SUPABASE_SERVICE_KEY"] # Master Service Role Key
    return create_client(url, admin_key)