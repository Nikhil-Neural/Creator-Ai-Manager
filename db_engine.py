import streamlit as st
from supabase import create_client, Client
import json

def insert_schedule_queue(supabase_client, user_email, platform, content_data, scheduled_time):
    """
    User ke parsed data ko Supabase ki queue table mein 'Pending' status ke sath save karta hai.
    """
    try:
        # JSON payload tayar kar rahe hain taaki kisi bhi platform ka data fit aa jaye
        payload = {
            "creator_email": user_email,
            "platform": platform,
            "content_payload": content_data, # Yeh ek dictionary hogi jisme title, thread, etc. hoga
            "scheduled_time": scheduled_time.isoformat(), # Time ko standard ISO format mein convert kiya
            "status": "Pending"
        }
        
        # Supabase table mein insert karna
        response = supabase_client.table("schedule_queue").insert(payload).execute()
        
        return True, f"✅ Successfully scheduled for {platform} at {scheduled_time.strftime('%Y-%m-%d %H:%M')}"
        
    except Exception as e:
        return False, f"❌ Failed to schedule: {str(e)}"

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

def insert_schedule_queue(supabase_client, user_email, platform, content_data, scheduled_time):
    # Tumhara baaki ka andar ka code waisa hi rahega
    try:
        payload = {
            "creator_email": user_email,
            "platform": platform,
            "content_payload": content_data,
            "scheduled_time": scheduled_time.isoformat(),
            "status": "Pending"
        }
        
        response = supabase_client.table("schedule_queue").insert(payload).execute()
        return True, f"✅ Successfully scheduled for {platform} at {scheduled_time.strftime('%Y-%m-%d %H:%M')}"
        
    except Exception as e:
        return False, f"❌ Failed to schedule: {str(e)}"