from helpers import parse_blueprint_metadata, create_word_doc
from ai_engine import run_my_crew_ai_agents
from social_publisher import post_to_twitter_thread, post_to_linkedin
from analytics_engine import fetch_youtube_analytics, fetch_meta_analytics
from auth_urls import get_linkedin_oauth_url, get_threads_oauth_url, get_facebook_oauth_url, get_youtube_oauth_url, get_twitter_oauth_url, get_meta_access_token, get_youtube_access_token
# 1. Pehle sahi function ko import karo
from db_engine import get_supabase_admin_client
# 2. Phir us function ko call karke apna supabase_admin variable bana lo
supabase_admin = get_supabase_admin_client()
from datetime import datetime
# ✈️ Dynamic Telegram Storage aur Database Engines Connect Karna
from storage_engine import upload_video_to_telegram
from db_engine import insert_schedule_queue
# ── Groq Cache Fix ─────────────────────────────────────
try:
    from crewai.llms import cache as _cache
    _cache.mark_cache_breakpoint = lambda msg: msg
except ImportError:
    pass

import streamlit as st
from supabase import create_client, Client
import uuid

# Supabase se connect karna
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_SERVICE_KEY"]
supabase: Client = create_client(url, key)
import urllib.parse
import tempfile
import os
import base64
import hashlib
import os
import io  # 🌟 Virtual Memory (RAM) ke liye
from docx import Document  # 🌟 Word Document Blueprint ke liye
from crewai import Agent, Task, Crew, LLM
import time # 🌟 Runtime backoff delays ke liye
import requests
import json
import re
# ==============================================================
# 🔄 MASTER SYNC ENGINE (API to Supabase Cache)
# ==============================================================
def sync_platform_analytics():
    """
    User ke tokens fetch karta hai, live APIs ko hit karta hai, aur data ko 
    platform_analytics_cache table mein update (UPSERT) kar deta hai.
    """
    creator_handle = st.session_state.get("creator_handle")
    if not creator_handle:
        return False
        
    try:
        # 1. User ke secure tokens nikalo
        profile_res = supabase.table("creator_profiles").select("*").eq("creator_handle", creator_handle).execute()
        if not profile_res.data:
            return False
            
        user_tokens = profile_res.data[0]
        yt_token = user_tokens.get("youtube_token")
        
        yt_data = {}
        sync_health = "Healthy"
        
        # 2. YouTube Data Pull karo
        if yt_token:
            yt_data = fetch_youtube_analytics(yt_token)
            if yt_data.get("status") == "auth_failed":
                sync_health = "YT_Auth_Failed"
                
        # 3. META Data Pull (Pure Unified Meta Graph API Route)
        fb_token = user_tokens.get("facebook_token") or user_tokens.get("instagram_token")
        
        meta_results = {}
        if fb_token:
            meta_results = fetch_meta_analytics(fb_token)
            if meta_results.get("status") == "auth_failed":
                sync_health = "Meta_Auth_Failed"
                
        # 4. Supabase Cache Matrix mein Inject karo (No Garbage Functions!)
        cache_res = supabase_admin.table("platform_analytics_cache").select("id").eq("creator_handle", creator_handle).execute()
        
        if cache_res.data:
            # UPDATE
            supabase_admin.table("platform_analytics_cache").update({
                "youtube_data": yt_data,
                "facebook_data": meta_results.get("facebook", {}),
                "instagram_data": meta_results.get("instagram", {}), # 👈 Unified Graph API data directly injected
                "sync_status": sync_health,
            }).eq("creator_handle", creator_handle).execute()
        else:
            # INSERT
            supabase_admin.table("platform_analytics_cache").insert({
                "creator_handle": creator_handle,
                "youtube_data": yt_data,
                "facebook_data": meta_results.get("facebook", {}),
                "instagram_data": meta_results.get("instagram", {}),
                "sync_status": sync_health
            }).execute()
            
        return True
        
    except Exception as e:
        # Ab hum error ko chhipayenge nahi, seedha UI par bhejenge!
        return f"CRASH LOG: {str(e)}"

st.set_page_config(page_title="Creator AI OS", layout="wide")

# ==============================================================
# 🔐 SECURE AUTHENTICATION SYSTEM (Supabase Auth)
# ==============================================================
if "user_email" not in st.session_state:
    st.session_state["user_email"] = None

# 🔄 NAYA: Redirect ke baad Supabase ka 'ID Card' wapas pehnana
if st.session_state.get("sb_access_token") and st.session_state.get("sb_refresh_token"):
    try:
        supabase.auth.set_session(st.session_state["sb_access_token"], st.session_state["sb_refresh_token"])
    except:
        pass

# 🧠 SUPABASE SESSION AUTO-RECOVERY (Memory Check)
if st.session_state["user_email"] is None:
    try:
        current_session = supabase.auth.get_session()
        if current_session and current_session.user:
            st.session_state["user_email"] = current_session.user.email
            st.session_state["creator_handle"] = current_session.user.email
            st.session_state["sb_access_token"] = current_session.access_token
            st.session_state["sb_refresh_token"] = current_session.refresh_token
    except:
        pass

# Agar user logged in nahi hai, toh secure Login/Signup screen dikhao
if st.session_state["user_email"] is None:
    st.markdown("<h2 style='text-align: center;'>🔐 Secure Access - Creator AI OS</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>Create an account or login to access your secure workspace.</p>", unsafe_allow_html=True)
    
    st.write(" ")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_login, tab_signup = st.tabs(["🔑 Login", "📝 Create Account"])
        
        # --- LOGIN TAB ---
        with tab_login:
            log_email = st.text_input("Email Address", key="log_email")
            log_pass = st.text_input("Password", type="password", key="log_pass")
            if st.button("🚀 Login", use_container_width=True):
                try:
                    # Supabase API Call
                    user = supabase.auth.sign_in_with_password({"email": log_email.strip(), "password": log_pass})
                    st.session_state["user_email"] = log_email.strip()
                    st.session_state["creator_handle"] = log_email.strip()
                    # 💾 ID Card memory mein save kar rahe hain
                    st.session_state["sb_access_token"] = user.session.access_token
                    st.session_state["sb_refresh_token"] = user.session.refresh_token
                    st.success("Login Successful!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"⚠️ Login Error: {str(e)}") 

        # --- SIGN UP TAB ---
        with tab_signup:
            reg_email = st.text_input("New Email Address", key="reg_email")
            reg_pass = st.text_input("Create Password (Min 6 chars)", type="password", key="reg_pass")
            opt_in = st.checkbox("Send my generated AI scripts & channel audit reports to my email.", value=True)
            
            if st.button("✨ Create Free Account", use_container_width=True):
                if len(reg_pass) < 6:
                    st.warning("Password must be at least 6 characters long.")
                else:
                    try:
                        user = supabase.auth.sign_up({"email": reg_email.strip(), "password": reg_pass})
                        st.success("Account Created! Logging you in automatically... 🚀")
                        time.sleep(1.5)
                        st.session_state["user_email"] = reg_email.strip()
                        st.session_state["creator_handle"] = reg_email.strip()
                        # 💾 ID Card memory mein save kar rahe hain
                        st.session_state["sb_access_token"] = user.session.access_token
                        st.session_state["sb_refresh_token"] = user.session.refresh_token
                        st.rerun()
                    except Exception as e:
                        st.error(f"⚠️ Registration Failed: {str(e)}")
    
    # 🛑 SECURITY LOCK
    st.stop() 

# ✅ SIRF YEH NAYA CODE REHNA CHAHIYE ✅
st.sidebar.markdown(f"### 👤 Profile:\n**{st.session_state['user_email']}**")
# ==============================================================
# 🧠 SMART MEMORY RECOVERY & HELPERS
# ==============================================================
if "db_checked" not in st.session_state and st.session_state.get("creator_handle"):
    try:
        response = supabase.table("creator_profiles").select("*").eq("creator_handle", st.session_state["creator_handle"]).execute()
        if response.data:
            user_data = response.data[0]
            # Har platform ka individual status check
            st.session_state["yt_connected"] = bool(user_data.get("youtube_token"))
            st.session_state["tw_connected"] = bool(user_data.get("twitter_token"))
            st.session_state["ig_connected"] = bool(user_data.get("instagram_token"))
            st.session_state["fb_connected"] = bool(user_data.get("facebook_token"))
            st.session_state["li_connected"] = bool(user_data.get("linkedin_token")) # 💼 LinkedIn Memory Load
            st.session_state["th_connected"] = bool(user_data.get("threads_token")) # Threads Memory Load

            if any([st.session_state.get(k) for k in ["yt_connected", "tw_connected", "ig_connected", "fb_connected", "li_connected", "th_connected"]]):
                st.session_state["channels_synced"] = True
                
        st.session_state["db_checked"] = True
    except Exception as e:
        print(f"Memory Sync Error: {e}")

def disconnect_platform(platform_column, session_key):
    """Database se token hatane aur button reset karne ka function"""
    if st.session_state.get("creator_handle"):
        supabase.table("creator_profiles").update({platform_column: None}).eq("creator_handle", st.session_state["creator_handle"]).execute()
        st.session_state[session_key] = False
        st.rerun()
if st.sidebar.button("🚪 Secure Logout"):
    supabase.auth.sign_out()
    st.session_state["sb_access_token"] = None
    st.session_state["sb_refresh_token"] = None
    st.session_state["user_email"] = None
    st.session_state["creator_handle"] = None
    st.session_state["channels_synced"] = False 
    st.rerun()
st.sidebar.write("---")

# ── Session State Management Nodes ──────────────────────
if "active_model"      not in st.session_state: st.session_state["active_model"] = ""
if "gemini_error"      not in st.session_state: st.session_state["gemini_error"] = ""
if "channels_synced"   not in st.session_state: st.session_state["channels_synced"] = False
if "audit_data_ready"  not in st.session_state: st.session_state["audit_data_ready"] = False
if "mock_upload_ready" not in st.session_state: st.session_state["mock_upload_ready"] = False
# ── Dynamic Sidebar Control Panel ───────────────────────
with st.sidebar:
    st.title("⚙️ Control Panel Matrix")
    current_os_mode = st.pills(
        "🔮 Core OS Operations Mode:",
        ["✍️ AI Script Generator", "📊 AI Channel Auditor & Sync"],
        default="✍️ AI Script Generator"
    )
    st.write("---")
    st.caption("Architecture Framework: CrewAI + Gemini + Groq Matrix")
# ── Main Content Gateway Router ──────────────────────────
def save_platform_token(platform_column_name, auth_code):
    current_user = st.session_state.get("user_email") # 👈 FIXED: Swapped handle to explicit user_email session key
    if not current_user:
        return 
        
    response = supabase.table("creator_profiles").select("id").eq("creator_handle", current_user).execute()
    
    if response.data:
        supabase.table("creator_profiles").update({
            platform_column_name: auth_code
        }).eq("creator_handle", current_user).execute()
    else:
        supabase.table("creator_profiles").insert({
            "creator_handle": current_user,
            platform_column_name: auth_code
        }).execute()
# ── Main Content Gateway Router ──────────────────────────
if "code" in st.query_params:
    auth_code = st.query_params["code"] 
    platform_state = st.query_params.get("state", "instagram") 
    
    if platform_state == "facebook":
        st.info("🔄 Authenticating secure connection with Meta Ecosystem...")
        user_access_token = get_meta_access_token(auth_code)
        
        if user_access_token:
            base_url = "https://graph.facebook.com/v20.0"
            pages_url = f"{base_url}/me/accounts?access_token={user_access_token}"
            try:
                # 📡 Fetching Data from Meta
                pages_res = requests.get(pages_url).json()
                
                # 🚨 X-RAY VISION: Agar Meta Error deta hai
                if "error" in pages_res:
                    st.error("🚨 META CORE ERROR DETECTED:")
                    st.json(pages_res) 
                
                # ✅ SUCCESS: Agar pages mil gaye
                elif "data" in pages_res and len(pages_res["data"]) > 0:
                    
                    # ⚡ MAGIC FIX 2: Claude's function requires the USER Token. 
                    # Pehle hum yahan Page Token extract kar rahe the, jisse clash ho raha tha.
                    save_platform_token("facebook_token", user_access_token)
                    save_platform_token("instagram_token", user_access_token) 
                    
                    st.session_state["fb_connected"] = True
                    st.session_state["ig_connected"] = True
                    st.session_state["channels_synced"] = True
                    st.success("🎉 Meta Ecosystem (Facebook + Instagram) Successfully Linked! ♾️")
                    
                    st.query_params.clear()
                    time.sleep(1)
                    st.rerun()
                
                # 📭 EMPTY: Agar sach mein page missing hai
                else:
                    st.error("❌ Linkage Failed: The API returned an empty list of pages.")
                    st.warning("🕵️ RAW API RESPONSE FROM META:")
                    st.json(pages_res) 
                    
            except Exception as e:
                st.error(f"❌ Core Router Error: {str(e)}")
        else:
            st.warning("⚠️ Meta session token already rotated or validated. Please refresh your granular analytics dashboard below.")
            st.query_params.clear()
        
    elif platform_state == "youtube":
        st.info("🔄 Authenticating secure connection with Google...")
        real_access_token = get_youtube_access_token(auth_code)
        
        # Agar error string aayi hai, toh directly print karo
        if isinstance(real_access_token, str) and ("GOOGLE_ERROR" in real_access_token or "SYSTEM_ERROR" in real_access_token):
            st.error(f"❌ YouTube Auth Failed. Reason: {real_access_token}")
        elif real_access_token:
            st.success("🎉 YouTube Channel Successfully Linked! ❤️")
            save_platform_token("youtube_token", real_access_token) 
            st.session_state["yt_connected"] = True
            st.session_state["channels_synced"] = True
        else:
            st.error("❌ Unknown Error. Token is empty.")
    
    elif platform_state.startswith("linkedin"):
        st.success("🎉 LinkedIn Profile Successfully Linked! 💼")
        save_platform_token("linkedin_token", auth_code)
        st.session_state["li_connected"] = True 
        st.session_state["channels_synced"] = True
    
    # 🧵 THREADS DETECTOR (Isko Instagram se hamesha UPAR rakhna)
    elif "thread" in str(platform_state).lower():
        st.success("🎉 Meta Threads Account Successfully Linked! 🧵")
        save_platform_token("threads_token", auth_code)
        st.session_state["th_connected"] = True
        st.session_state["channels_synced"] = True

    else:
        # 🟢 THE TWITTER SUPABASE FIX 🟢
        response = supabase.table("twitter_auth_states").select("code_verifier").eq("state", platform_state).execute()
        if response.data:
            st.success("🎉 X (Twitter) Account Successfully Linked! 🩵")
            save_platform_token("twitter_token", auth_code)
            st.session_state["tw_connected"] = True
            st.session_state["channels_synced"] = True
            supabase.table("twitter_auth_states").delete().eq("state", platform_state).execute()
        else:
            st.error("⚠️ Unknown platform state or Twitter Session Expired. Please try again.")
            
    st.query_params.clear()
st.markdown(
    """
    <div style="display: flex; align-items: baseline; gap: 10px;">
        <h1 style="margin: 0;">🚀 Creator AI Manager OS</h1>
        <span style="background-color: #ff4b4b; color: white; padding: 4px 10px; border-radius: 15px; font-size: 14px; font-weight: bold;">
            ⚡ Shorts Only (Long-form coming soon)
        </span>
    </div>
    """, 
    unsafe_allow_html=True
)
st.write(f"System Context: **{current_os_mode}** active")
st.write("---")

# MODE 1: SCRIPT ENGINE
if current_os_mode == "✍️ AI Script Generator":
    tab1, tab2, tab3 = st.tabs(["🔥 Trend & Script Workspace", "📥 Download Generated Blueprint", "📂 My Saved Vault"])
    with tab1:
        st.markdown("### 🔥 AI Content Strategy Hub")
        app_mode = st.radio("🔮 Kis Mode me kaam karna hai?", ["🚀 Complete Blueprint Mode", "✍️ Repurpose My Script Mode"], horizontal=True)
        st.write("---")
        
        # 1. Blueprint Arrays (The 10 Hooks, 4 Bodies, 4 CTAs)
        HOOK_OPTIONS = [
            "Select a Hook...",
            "The Negative Warning (Stop doing X. It's destroying Y)",
            "The Curiosity Gap (The real reason why X, and nobody is talking about it)",
            "The Contrarian (Myth Buster - X is a complete lie)",
            "The Secret Tool Drop (This secret feels illegal to know)",
            "The Bold Claim (This simple shift will change X forever)",
            "The 'How-To' Tease (How to achieve X in short time)",
            "The Mind-Reader (You are probably struggling with X...)",
            "The Shocking Statistic (99% fail because of this...)",
            "The Visual Anchor (Direct bizarre statement matching B-Roll)",
            "The 'Us vs. Them' (Why A is losing, while B takes over)"
        ]

        BODY_OPTIONS = [
            "Select a Body Framework...",
            "The Step-by-Step Blueprint (Highly logical, Step 1, 2, 3)",
            "The Case Study (Real-world success story or trend breakdown)",
            "The Problem-Agitate-Solve (PAS - Pain, Agitate, Solution)",
            "Rapid Fire Facts (High-density, fast-paced bullet points)"
        ]

        CTA_OPTIONS = [
            "Select a CTA...",
            "The Value Bribe (Comment [KEYWORD] for DM)",
            "The Seamless Loop (Connects end perfectly to the hook)",
            "The Cliffhanger (Hit subscribe for Part 2)",
            "The Direct Engagement Question (What is your take?)"
        ]

        # 2. UI Routing based on Mode
        if app_mode == "🚀 Complete Blueprint Mode":
            bundle_options = st.pills("🎁 Content Bundle Items: (Multi-Select)", ["🎬 Retention Script & Visual Cues", "📺 YouTube SEO: Viral Title & Description", "📸 Insta & FB Reels: Captions + Tags", "🏢 LinkedIn Post", "🐦 X & Threads: Viral Thread Format"], default=["🎬 Retention Script & Visual Cues"], selection_mode="multi")
            user_niche = st.text_input("🎯 Kis topic par video banani hai?", value=st.session_state.get("niche_data", ""))
            video_duration = 60

            # 🎯 CONDITIONAL LOGIC ADDED HERE
            if "🎬 Retention Script & Visual Cues" in bundle_options:
                video_duration = st.slider("⏱ Video duration (Seconds)", min_value=30, max_value=60, value=60, step=5)
                st.markdown("### 🧬 Viral Script Parameters")
                col1, col2, col3 = st.columns(3)
                with col1: selected_hook = st.selectbox("🪝 Hook", HOOK_OPTIONS)
                with col2: selected_body = st.selectbox("🧬 Body", BODY_OPTIONS)
                with col3: selected_cta = st.selectbox("🎯 CTA", CTA_OPTIONS)
                
                # Strict Validation Logic only if Script is selected
                is_ready_to_launch = (selected_hook != "Select a Hook..." and selected_body != "Select a Body Framework..." and selected_cta != "Select a CTA...")
            else:
                # Agar user sirf Metadata/Title maang raha hai, toh background mein variables bypass kardo
                selected_hook = "Standard"
                selected_body = "Standard"
                selected_cta = "Standard"
                is_ready_to_launch = True # Button unlock ho jayega!
        
        else:
            bundle_options = st.pills("🎁 Extraction Bundle Items: (Multi-Select)", ["📺 YouTube SEO: Viral Title & Description", "📸 Insta & FB Reels: Captions + Tags", "🏢 LinkedIn Post", "🐦 X & Threads: Viral Thread Format"], default=["📺 YouTube SEO: Viral Title & Description"], selection_mode="multi")
            user_niche = st.text_input("🎯 Video Title/Topic:", value=st.session_state.get("niche_data", ""))
            st.caption("💡 60-Second Limit: A typical Short contains 150-180 words.")
            user_pasted_script = st.text_area("📝 Script content:", height=200, max_chars=1200)
            is_ready_to_launch = True # Repurpose mode bypasses validation

        st.write("---")
        
        # 🌍 THE DYNAMIC LANGUAGE UI 🌍
        # Sirf tab dikhega jab Script Blueprint mode mein ho aur Script option selected ho
        if app_mode == "🚀 Complete Blueprint Mode" and "🎬 Retention Script & Visual Cues" in bundle_options:
            st.markdown("### 🎬 Core Script Language")
            script_language = st.selectbox("Select language for your Voiceover/Script:", ["Hinglish", "Hindi", "English"], index=0)
        else:
            # Repurpose mode ya 'Metadata Only' mode ke liye background variable (UI mein nahi dikhega)
            script_language = "English" 
        
        meta_languages = {"yt": "English", "ig": "English", "li": "English", "tw": "English"}
        st.markdown("### 📱 Social Media Language Routing")
        lang_col1, lang_col2 = st.columns(2)
        
        with lang_col1:
            if any("YouTube SEO" in opt for opt in bundle_options):
                meta_languages["yt"] = st.selectbox("📺 YouTube Title & Desc:", ["English", "Hinglish", "Hindi"], index=0)
            if any("LinkedIn" in opt for opt in bundle_options):
                meta_languages["li"] = st.selectbox("🏢 LinkedIn Post:", ["English", "Hinglish", "Hindi"], index=0)
        with lang_col2:
            if any("Insta & FB" in opt for opt in bundle_options):
                meta_languages["ig"] = st.selectbox("📸 Insta/FB Captions:", ["Hinglish", "Hindi", "English"], index=0)
            if any("X & Threads" in opt for opt in bundle_options):
                meta_languages["tw"] = st.selectbox("🐦 X & Threads:", ["English", "Hinglish", "Hindi"], index=0)

        st.write("---")

        # 3. Dynamic Engine Button (Outside of st.form to work properly)
        submit_btn = st.button("🚀 Launch Specialized Agents Grid", use_container_width=True, disabled=not is_ready_to_launch)

        if not is_ready_to_launch and app_mode == "🚀 Complete Blueprint Mode":
            st.warning("⚠️ Please select Hook, Body, and CTA to unlock the Generate button.")

        if submit_btn:
            if not bundle_options: 
                st.error("⚠️ Bundle item select karein!")
            elif not user_niche: 
                st.error("⚠️ Topic cannot be empty!")
            else:
                # 🧠 MAGIC INJECTION: We append the chosen frameworks directly to the topic!
                if app_mode == "🚀 Complete Blueprint Mode":
                    # Check karo ki kya script actually selected hai
                    if "🎬 Retention Script & Visual Cues" in bundle_options:
                        st.session_state["niche_data"] = f"{user_niche} | STRICT RULES -> Hook: {selected_hook} | Body: {selected_body} | CTA: {selected_cta}"
                    else:
                        # Sirf title/metadata hai, toh extra rules mat add karo
                        st.session_state["niche_data"] = user_niche
                else:
                    st.session_state["niche_data"] = user_niche
                    
                st.session_state["form_submitted"] = True
                st.session_state["selected_options"] = bundle_options
                st.session_state["current_mode"] = app_mode
                st.session_state["pasted_script"] = user_pasted_script if app_mode != "🚀 Complete Blueprint Mode" else ""
                st.session_state["duration"] = video_duration if app_mode == "🚀 Complete Blueprint Mode" else 1.0

        # 4. Engine Processing Block
        if st.session_state.get("form_submitted"):
            with st.spinner("🕵️ Processing failproof generation sequence..."):
                try:
                    # CrewAI Executed with Injected Data
                    ai_output = run_my_crew_ai_agents(
                        niche_topic=st.session_state["niche_data"],
                        social_platform="Omnichannel", # 👈 YEH THA MISSING LINK!
                        script_language=script_language, 
                        meta_langs=meta_languages, 
                        video_duration=st.session_state.get("duration", 1.0), 
                        app_mode=st.session_state["current_mode"], 
                        user_pasted_script=st.session_state.get("pasted_script", ""), 
                        selected_bundle_options=st.session_state["selected_options"]
                    )
                    
                    st.session_state["script_data"] = ai_output
                    st.session_state["form_submitted"] = False
                    
                    # 💾 THE VAULT MEMORY
                    if st.session_state.get("user_email"):
                        try:
                            supabase.table("ai_blueprints_vault").insert({
                                "creator_email": st.session_state["user_email"],
                                "target_platform": "Omnichannel",
                                "niche_topic": st.session_state["niche_data"], # Updated context goes here
                                "script_content": ai_output,
                                "social_metadata": str(st.session_state["selected_options"]),
                                "status": "Draft"
                            }).execute()
                        except Exception as db_error:
                            print(f"[VAULT ERROR] Could not save to database: {db_error}")

                    st.success("🎉 Blueprint ready & automatically saved to your Vault! Switch to Tab 2 to download content.")
                except Exception as e:
                    st.session_state["form_submitted"] = False
                    st.error(f"Engine Error: {str(e)}")

    with tab2:
        st.header("📥 Download Generated Content")
        if "script_data" in st.session_state and st.session_state["script_data"]:
            st.markdown(st.session_state["script_data"])
            st.write("---")
            
            # Dinamic file name banayein
            safe_name = st.session_state.get('niche_data', 'blueprint').replace(" ", "_")[:30]
            
            c1, c2 = st.columns(2)
            with c1: st.download_button("📥 Notepad (.txt)", str(st.session_state["script_data"]), file_name=f"{safe_name}.txt", use_container_width=True)
            with c2: st.download_button("📥 Word Doc (.docx)", create_word_doc(str(st.session_state["script_data"]), "Omnichannel", st.session_state.get("niche_data", "File")), file_name=f"{safe_name}.docx", use_container_width=True)
        else: st.warning("⚠️ No data compiled yet. Run Tab 1 first.")
    with tab3:
        st.header("📂 My Saved Blueprints Vault")
        st.markdown("Access all your previously generated high-retention scripts and metadata here.")
        
        if st.session_state.get("user_email"):
            # Database se user ki purani scripts fetch karna (Nayi sabse upar aayegi)
            try:
                response = supabase_admin.table("ai_blueprints_vault").select("*").eq("creator_email", st.session_state["user_email"]).order("created_at", desc=True).execute()
                
                if response.data and len(response.data) > 0:
                    st.success(f"📦 Found {len(response.data)} saved blueprints in your secure vault.")
                    st.write("---")
                    
                    # Har script ko ek accordion (expander) mein dikhana
                    for item in response.data:
                        # Date format ko clean karna
                        raw_date = item.get('created_at', '')
                        clean_date = raw_date.split('T')[0] if 'T' in raw_date else "Unknown Date"
                        
                        # Expander ka Title
                        with st.expander(f"🎬 {item.get('niche_topic', 'Untitled')} | 📅 {clean_date} | 📍 {item.get('target_platform', 'Unknown')}"):
                            st.caption(f"**Selected Metadata Assets:** {item.get('social_metadata', 'None')}")
                            st.write("---")
                            st.markdown(item.get('script_content', 'No content found.'))
                            
                            # Ek chhota sa copy button logic (user copy-paste kar sake)
                            # Action Buttons (Access & Delete)
                            col_action1, col_action2 = st.columns(2)
                            with col_action1:
                                st.button("📋 Access Data", key=f"btn_{item['id']}", use_container_width=True)
                            with col_action2:
                                if st.button("🗑️ Delete Script", key=f"del_{item['id']}", use_container_width=True):
                                    # Supabase DB se permanent delete karna
                                    supabase_admin.table("ai_blueprints_vault").delete().eq("id", item['id']).execute()
                                    st.rerun() # UI ko turant refresh karne ke liye
                else:
                    st.info("📭 Your vault is currently empty. Generate your first script in Tab 1 to see it here!")
            except Exception as e:
                st.error(f"⚠️ Vault Sync Error: Could not fetch data from database. ({str(e)})")
        else:
            st.warning("⚠️ Access Blocked: Please log in to view your saved blueprints.")

# MODE 2: AUDITOR ENGINE
else:
    st.markdown("### 📊 AI Omnichannel Channel Auditor Ecosystem")
    st.write("---")
    
    # Isko cleanly call karein bina kisi dynamic variable mapping breakdown ke
    selected_auditor_section = st.pills(
        "🛠️ Select Auditor Operational Node Framework:",
        ["🔗 1. Secure Social Account Hub", "📈 2. Real-Time Performance Audit", "🚀 3. Omnichannel Media Publisher Node"],
        default="🔗 1. Secure Social Account Hub"
    )
    st.write("---")
    
    # 🎯 INTEGRATION POINT 2: Re-writing Pill 1 for Real Connections
    if selected_auditor_section == "🔗 1. Secure Social Account Hub":
        st.markdown("## 🔐 Connect Your Social Accounts")
        st.write("Apne platforms ko ek click mein connect karein. (One Brand Rule Active)")
        st.write(" ")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📺 YouTube")
            if st.session_state.get("yt_connected"):
                st.success("✅ Connected: YouTube Channel")
                if st.button("❌ Disconnect YouTube", use_container_width=True):
                    disconnect_platform("youtube_token", "yt_connected")
            else:
                yt_login_link = get_youtube_oauth_url()
                st.markdown(f"<div style='margin-bottom: 16px;'><a href='{yt_login_link}' target='_blank' style='text-decoration: none;'><button style='width:100%; background-color:#FF0000; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer; height:42px; font-size:14px; box-shadow: 0px 2px 4px rgba(0,0,0,0.1);'>❤️ Connect YouTube Channel</button></a></div>", unsafe_allow_html=True)
                
            st.write(" ")
            st.subheader("🐦 X (Twitter)")
            if st.session_state.get("tw_connected"):
                st.success("✅ Connected: X Account")
                if st.button("❌ Disconnect X (Twitter)", use_container_width=True):
                    disconnect_platform("twitter_token", "tw_connected")
            else:
                tw_login_link = get_twitter_oauth_url()
                st.markdown(f"<div style='margin-bottom: 16px;'><a href='{tw_login_link}' target='_blank' style='text-decoration: none;'><button style='width:100%; background-color:#000000; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer; height:42px; font-size:14px; box-shadow: 0px 2px 4px rgba(0,0,0,0.1);'>🩵 Connect X Account</button></a></div>", unsafe_allow_html=True)
            # 🧵 NEW: META THREADS UI CONNECT NODE
            st.write(" ")
            st.subheader("🧵 Meta Threads")
            if st.session_state.get("th_connected"):
                st.success("✅ Connected: Threads Profile")
                if st.button("❌ Disconnect Threads", use_container_width=True):
                    disconnect_platform("threads_token", "th_connected")
            else:
                # 🟢 YAHAN UPDATE KIYA HAI: Asli threads ka function call hoga
                meta_threads_link = get_threads_oauth_url() 
                st.markdown(f"<div style='margin-bottom: 16px;'><a href='{meta_threads_link}' target='_blank' style='text-decoration: none;'><button style='width:100%; background-color:#000000; color:white; border: 1px solid #333; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer; height:42px; font-size:14px; box-shadow: 0px 2px 4px rgba(0,0,0,0.1);'>🧵 Connect Meta Threads</button></a></div>", unsafe_allow_html=True)

        with col2:
            st.subheader("♾️ Meta Ecosystem (FB & IG)")
            
            if st.session_state.get("fb_connected") and st.session_state.get("ig_connected"):
                st.success("✅ Connected: Meta Ecosystem (Facebook + Instagram)")
                if st.button("❌ Disconnect Meta Ecosystem", use_container_width=True):
                    # Dono tokens ko ek sath securely nullify karo
                    if st.session_state.get("creator_handle"):
                        supabase.table("creator_profiles").update({
                            "facebook_token": None,
                            "instagram_token": None
                        }).eq("creator_handle", st.session_state["creator_handle"]).execute()
                    st.session_state["fb_connected"] = False
                    st.session_state["ig_connected"] = False
                    st.rerun()
            else:
                # 🚀 Unified Gateway URL call ho raha hai ab bina kisi error ke
                meta_login_link = get_facebook_oauth_url()
                st.markdown(f"<a href='{meta_login_link}' target='_blank' style='text-decoration: none;'><button style='width:100%; background-color:#0668E1; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer; height:42px; font-size:14px; box-shadow: 0px 2px 4px rgba(0,0,0,0.1);'>♾️ Connect Meta Ecosystem</button></a>", unsafe_allow_html=True)
                st.caption("💡 Note: This will securely link your Facebook Pages and its connected Instagram Business account simultaneously using the new approved developer scopes.")

            # 💼 NEW: LINKEDIN UI CONNECT NODE
            st.write(" ")
            st.subheader("💼 LinkedIn")
            if st.session_state.get("li_connected"):
                st.success("✅ Connected: LinkedIn Profile")
                if st.button("❌ Disconnect LinkedIn", use_container_width=True):
                    disconnect_platform("linkedin_token", "li_connected")
            else:
                linkedin_login_link = get_linkedin_oauth_url()
                st.markdown(f"<div style='margin-bottom: 16px;'><a href='{linkedin_login_link}' target='_blank' style='text-decoration: none;'><button style='width:100%; background-color:#0077B5; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer; height:42px; font-size:14px; box-shadow: 0px 2px 4px rgba(0,0,0,0.1);'>💼 Connect LinkedIn Profile</button></a></div>", unsafe_allow_html=True)
        st.write("---")
        
        # Bottom Utility Buttons Configuration Flow
        if st.session_state.get("channels_synced", False):
            action_col1, action_col2 = st.columns([2, 1])
            with action_col1:
                st.success("🔒 SYSTEM STATUS CLEAR: Verified session tokens encrypted securely inside local cache.")
            with action_col2:
                if st.button("⚠️ EMERGENCY KILL-SWITCH REVOKE", use_container_width=True):
                    with st.spinner("Nuking all connected accounts from secure vault..."):
                        # 1. Database se ek saath saare tokens uda do
                        if st.session_state.get("creator_handle"):
                            supabase.table("creator_profiles").update({
                                "youtube_token": None,
                                "twitter_token": None,
                                "instagram_token": None,
                                "facebook_token": None,
                                "linkedin_token": None,
                                "threads_token": None
                            }).eq("creator_handle", st.session_state["creator_handle"]).execute()
                        # 👉 1.5 NEW: Twitter Auth States ka anonymous kachra (garbage data) delete karo
                        try:
                            # Note: Agar tumne admin client is file mein import kiya hai toh 'supabase_admin' likho
                            # Warna normal 'supabase' rehne do (kyunki humne SQL mein anon delete permission de di thi)
                            supabase_admin.table("twitter_auth_states").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
                        except Exception as e:
                            pass # Agar table pehle se khali hai, toh error ignore karega
                        
                        # 2. App ki memory (RAM) se sab reset kar do
                        st.session_state["yt_connected"] = False
                        st.session_state["tw_connected"] = False
                        st.session_state["ig_connected"] = False
                        st.session_state["fb_connected"] = False
                        st.session_state["li_connected"] = False
                        st.session_state["th_connected"] = False
                        
                        st.session_state["channels_synced"] = False
                        st.session_state["audit_data_ready"] = False
                        st.session_state["mock_upload_ready"] = False
                        time.sleep(1)
                        st.rerun()
        else:
            st.info("🔒 SYSTEM STATUS IDLE: Please click one of the platform connection buttons above to sync handles.")

    # PILL SECTION B: ANALYSIS ENGINE CODES MATRIX
    elif selected_auditor_section == "📈 2. Real-Time Performance Audit":
        st.markdown("### 📈 Omnichannel Granular Analytics Radar")
        st.write("Independently sync and monitor live parameters for each social node.")
        
        st.markdown("""
        <style>
        .metric-box {
            background-color: #111111;
            border-left: 4px solid #00FFAA;
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            margin-bottom: 15px;
        }
        .metric-title { color: #888888; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; font-weight: bold;}
        .metric-value { color: #FFFFFF; font-size: 32px; font-weight: 800; margin-top: 5px;}
        .warning-box { border-left: 4px solid #FF4444 !important; }
        </style>
        """, unsafe_allow_html=True)

        creator_handle = st.session_state.get("creator_handle")
        
        if not creator_handle:
            st.warning("⚠️ Security Lock: Please connect your accounts in Tab 1 first.")
        else:
            # 🗄️ FETCH CURRENT CACHE
            # 🗄️ FETCH CURRENT CACHE
            try:
                # 🚀 YAHAN supabase KO supabase_admin BANA DIYA
                cache_res = supabase_admin.table("platform_analytics_cache").select("*").eq("creator_handle", creator_handle).execute()
                cache_data = cache_res.data[0] if cache_res.data else {}
            except Exception as e:
                st.error(f"Cache Fetch Error: {str(e)}") # Achhi practice ke liye error bhi print karwa diya
                cache_data = {}

            profile_res = supabase.table("creator_profiles").select("*").eq("creator_handle", creator_handle).execute()
            user_tokens = profile_res.data[0] if profile_res.data else {}

            # 📺 YOUTUBE SECTION
            st.write(" ")
            st.markdown("#### 📺 YouTube Mainframe")
            yt_col_btn, yt_col_blank = st.columns([1, 3])
            with yt_col_btn:
                if st.button("🔄 Sync YouTube Only", key="sync_yt_alone", use_container_width=True):
                    yt_token = user_tokens.get("youtube_token")
                    if yt_token:
                        with st.spinner("Pinging Google Mainframe..."):
                            yt_data = fetch_youtube_analytics(yt_token)
                            st.warning(f"🔍 GOOGLE NE KYA BHEJA: {yt_data}")
                            # Normal 'supabase' ko 'supabase_admin' se replace kar diya gaya hai
                            check_res = supabase_admin.table("platform_analytics_cache").select("id").eq("creator_handle", creator_handle).execute()

                            if check_res.data:
                                supabase_admin.table("platform_analytics_cache").update({
                                    "youtube_data": yt_data
                                }).eq("creator_handle", creator_handle).execute()
                            else:
                                supabase_admin.table("platform_analytics_cache").insert({
                                    "creator_handle": creator_handle,
                                    "youtube_data": yt_data
                                }).execute()
                                
                            st.toast("✅ YouTube Cache updated!")
                            time.sleep(0.5)
                            st.rerun()
                    else:
                        st.error("YouTube Token Missing!")

            yt = cache_data.get("youtube_data", {})
            if yt and yt.get("status") == "connected":
                y1, y2, y3 = st.columns(3)
                with y1: st.markdown(f'<div class="metric-box"><div class="metric-title">Total Views</div><div class="metric-value">{yt.get("views", 0):,}</div></div>', unsafe_allow_html=True)
                with y2: st.markdown(f'<div class="metric-box"><div class="metric-title">Subscribers</div><div class="metric-value">{yt.get("subscribers", 0):,}</div></div>', unsafe_allow_html=True)
                with y3: st.markdown(f'<div class="metric-box"><div class="metric-title">Video Count</div><div class="metric-value">{yt.get("video_count", 0):,}</div></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="metric-box warning-box"><div class="metric-title">YouTube Node</div><div class="metric-value" style="color: #FF4444;">Offline</div></div>', unsafe_allow_html=True)

            st.write("---")

            # 📱 INDEPENDENT SOCIAL NODES MATRIX
            st.markdown("##### 📱 Independent Social Nodes (IG / FB)")
            fb = cache_data.get("facebook_data", {})
            ig = cache_data.get("instagram_data", {})
                
            # 🔥 TOKEN LOCK ENCRYPTED (Yahi chahiye!)
            meta_token = user_tokens.get("facebook_token") or user_tokens.get("instagram_token")
                
            m1, m2 = st.columns(2)
            with m1:
                st.markdown("##### 📸 Instagram Node")
                if st.button("🔄 Sync Instagram Only", key="sync_ig_alone", use_container_width=True):
                    if meta_token:
                        with st.spinner("Scanning Meta Graph..."):
                            meta_results = fetch_meta_analytics(meta_token)
                            ig_final_data = meta_results.get("instagram", {"status": "offline"})
                            check_res = supabase_admin.table("platform_analytics_cache").select("id").eq("creator_handle", creator_handle).execute()
                            if check_res.data:
                                supabase_admin.table("platform_analytics_cache").update({"instagram_data": ig_final_data}).eq("creator_handle", creator_handle).execute()
                            else:
                                supabase_admin.table("platform_analytics_cache").insert({"creator_handle": creator_handle, "instagram_data": ig_final_data}).execute()
                            st.toast("✅ Instagram Cache updated!")
                            time.sleep(0.5)
                            st.rerun()
                    else:
                        st.error("Meta Token Missing!")
                    
                if ig and ig.get("status") == "connected":
                    st.markdown(f'<div class="metric-box"><div class="metric-title">IG Followers</div><div class="metric-value">{ig.get("followers", 0):,}</div></div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="metric-box warning-box"><div class="metric-title">IG Node</div><div class="metric-value" style="color: #FF4444;">Offline</div></div>', unsafe_allow_html=True)
                    st.error(f"🕵️ IG Diagnostics Log: {ig.get('debug_msg', 'Token empty or never synced.')}")

            with m2:
                st.markdown("##### 🔵 Facebook Node")
                if st.button("🔄 Sync Facebook Only", key="sync_fb_alone", use_container_width=True):
                    if meta_token:
                        with st.spinner("Extracting Facebook Insights..."):
                            meta_results = fetch_meta_analytics(meta_token)
                            fb_final_data = meta_results.get("facebook", {"status": "offline"})
                            check_res = supabase_admin.table("platform_analytics_cache").select("id").eq("creator_handle", creator_handle).execute()
                            if check_res.data:
                                supabase_admin.table("platform_analytics_cache").update({"facebook_data": fb_final_data}).eq("creator_handle", creator_handle).execute()
                            else:
                                supabase_admin.table("platform_analytics_cache").insert({"creator_handle": creator_handle, "facebook_data": fb_final_data}).execute()
                            st.toast("✅ Facebook Cache updated!")
                            time.sleep(0.5)
                            st.rerun()
                    else:
                        st.error("Meta Token Missing!")
                    
                if fb and fb.get("status") == "connected":
                    st.markdown(f'<div class="metric-box"><div class="metric-title">FB Page Followers</div><div class="metric-value">{fb.get("followers", 0):,}</div></div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="metric-box warning-box"><div class="metric-title">FB Node</div><div class="metric-value" style="color: #FF4444;">Offline</div></div>', unsafe_allow_html=True)
                    st.error(f"🕵️ FB Diagnostics Log: {fb.get('debug_msg', 'Token empty or never synced.')}")

    # ── PILL SECTION C: AUTOMATED PUBLISHER DEPLOYMENT PIPELINE ──────────────────
    elif selected_auditor_section == "🚀 3. Omnichannel Media Publisher Node":
        st.markdown("### 🚀 Omnichannel Automated Media Publisher")
        st.write("Upload your video, select metadata, and publish everywhere in one click.")
        
        # 🎬 STEP 1: VIDEO UPLOAD GATEWAY
        st.markdown("#### 🎬 Step 1: Upload Media")
        uploaded_video = st.file_uploader("Drop your final video file here (Max 500MB)", type=["mp4", "mov", "mkv"])
        
        if uploaded_video:
            st.success(f"✅ Video '{uploaded_video.name}' ready for processing!")
            
        st.write("---")
        
        # 🧠 STEP 2: METADATA SOURCE ENGINE
        st.markdown("#### 🧠 Step 2: Metadata Source")
        metadata_source = st.radio("Choose how you want to add titles, descriptions, and captions:", 
                                   ["📂 Use Saved Vault Data (Recommended)", "✍️ Manual Paste", "✨ Generate New Metadata"], 
                                   horizontal=True)
        
        # Variables default initialize karna taaki scope errors na aayein
        final_yt_title = ""
        final_yt_desc = ""
        final_tw_thread = ""
        final_ig_cap = ""
        final_th_content = ""
        final_li_post = ""
        parsed_data = {}

        # Option 1: Vault Data (The Bridge with Smart Parser)
        # Option 1: Vault Data (The Bridge with Smart Parser)
        if metadata_source == "📂 Use Saved Vault Data (Recommended)":
            try:
                response = supabase_admin.table("ai_blueprints_vault").select("*").eq("creator_email", st.session_state.get("user_email")).order("created_at", desc=True).execute()
                blueprints = response.data if response.data else []
            except:
                blueprints = []
                
            if not blueprints:
                st.error("📭 Your Vault is empty. Please generate a script first.")
            else:
                blueprint_options = {f"{item['niche_topic']} ({item['target_platform']})": item for item in blueprints}
                selected_bp_name = st.selectbox("Select a Blueprint to extract metadata from:", options=list(blueprint_options.keys()))
                selected_bp = blueprint_options[selected_bp_name]
                
                # 🧠 PARSER ACTION: Text ko tod kar variables mein badalna
                parsed_data = parse_blueprint_metadata(selected_bp['script_content'])
                
                # 🚀 NAYA JADOO: Regex se Trend Research wale Hooks nikalna!
                import re
                raw_text = selected_bp['script_content']
                # Yeh regex "Hook:" ke baad likhe hue text ko pakad lega
                extracted_hooks = re.findall(r'(?:Hook|Retention):\s*"?([^"\n]+)"?', raw_text)
                
                st.success(f"✅ AI Metadata successfully parsed and injected! Please review below.")
                
                # Yahan auto-fill boxes aayenge
                with st.expander("📺 Auto-Filled: YouTube Metadata", expanded=True):
                    # Agar AI ne hooks generate kiye hain, toh user ko dropdown dikhao
                    if extracted_hooks:
                        chosen_hook = st.selectbox(
                            "🎯 Select a Viral Hook for your Title (or use default):", 
                            ["(Use Default Parsed Title)"] + extracted_hooks
                        )
                        
                        # Agar user dropdown se hook select karta hai, toh text_input mein wahi aayega
                        default_title_value = parsed_data.get("yt_title", "").replace("[YOUTUBE SHORTS TITLE]", "").replace("[", "").replace("]", "").strip()
                        if chosen_hook != "(Use Default Parsed Title)":
                            default_title_value = chosen_hook
                            
                        final_yt_title = st.text_input("YouTube Title", value=default_title_value)
                    else:
                        # Agar kisi wajah se hooks nahi mile, toh normal text box dikhao (safely clean karke)
                        clean_title = parsed_data.get("yt_title", "").replace("[YOUTUBE SHORTS TITLE]", "").replace("[", "").replace("]", "").strip()
                        final_yt_title = st.text_input("YouTube Title", value=clean_title)
                        
                    final_yt_desc = st.text_area("YouTube Description", value=parsed_data.get("yt_desc", "").replace("[YOUTUBE SHORTS DESCRIPTION]", "").replace("[", "").replace("]", "").strip(), height=150)
                
                with st.expander("🐦 Auto-Filled: X (Twitter) Thread"):
                    final_tw_thread = st.text_area("Generated Thread Content", value=parsed_data.get("tw_thread", ""), height=150)
                
                with st.expander("📸 Auto-Filled: Social Captions"):
                    final_ig_cap = st.text_area("Instagram/Facebook Caption", value=parsed_data.get("ig_caption", ""), height=100)

        # Option 2: Manual Paste (Clean UI with Expanders)
        elif metadata_source == "✍️ Manual Paste":
            st.info("Manually enter your content for each platform below.")
            with st.expander("📺 YouTube Metadata", expanded=True):
                final_yt_title = st.text_input("YouTube Title", key="man_yt_title")
                final_yt_desc = st.text_area("YouTube Description", key="man_yt_desc")
            with st.expander("🐦 X (Twitter) Thread"):
                final_tw_thread = st.text_area("Tweet 1 (Video attached here)", key="man_tw_1")
                st.caption("*(Logic for '+ Add Tweet' button will be integrated here during API wiring)*")
            with st.expander("📸 Instagram & Facebook Captions"):
                final_ig_cap = st.text_area("Reel/Post Caption", key="man_ig_cap")
                
        # Option 3: Generate New
        elif metadata_source == "✨ Generate New Metadata":
            st.warning("⚠️ You need fresh metadata. Please switch to the **'✍️ AI Script Generator'** mode from the left sidebar to build and save a new blueprint to your Vault.")
            
        st.write("---")
        
        # 🌍 STEP 3: OMNICHANNEL DISTRIBUTION & INDEPENDENT TIMING MATRIX
        st.markdown("#### 🌍 Step 3: Distribution Routing & Custom Timings")

        st.write("Select the platforms and set independent times for each:")
        import pytz
        all_timezones = pytz.common_timezones
        default_tz_index = all_timezones.index("Asia/Kolkata") if "Asia/Kolkata" in all_timezones else 0
        user_timezone = st.selectbox("🌍 Select your Local Timezone:", all_timezones, index=default_tz_index)
        local_tz = pytz.timezone(user_timezone)

        # Har platform ke liye settings hold karne ke liye dictionary
        platform_schedule_map = {}

        # 5 Columns for all 5 platforms - Strictly Independent
        col_p1, col_p2, col_p3, col_p4, col_p5 = st.columns(5)

        with col_p1:
            push_yt = False
            if st.session_state.get("yt_connected"):
                push_yt = st.checkbox("📺 YouTube", value=True)
                if push_yt:
                    with st.expander("⏰ YT Timing", expanded=True):
                        yt_date = st.date_input("YT Date", min_value=datetime.today(), key="yt_d")
                        yt_time = st.time_input("YT Time", key="yt_t")
                        # 🔄 NAYA: User ke time ko convert kar raha hai
                        naive_dt = datetime.combine(yt_date, yt_time)
                        local_aware_dt = local_tz.localize(naive_dt)
                        platform_schedule_map["youtube"] = local_aware_dt.astimezone(pytz.utc)
            else:
                st.caption("📺 YouTube\n(Not Connected)")

        with col_p2:
            push_tw = False
            if st.session_state.get("tw_connected"):
                push_tw = st.checkbox("🐦 X (Twitter)", value=True)
                if push_tw:
                    with st.expander("⏰ X Timing", expanded=True):
                        tw_date = st.date_input("X Date", min_value=datetime.today(), key="tw_d")
                        tw_time = st.time_input("X Time", key="tw_t")
                        # 🔄 NAYA: User ke time ko convert kar raha hai
                        naive_dt = datetime.combine(tw_date, tw_time)
                        local_aware_dt = local_tz.localize(naive_dt)
                        platform_schedule_map["twitter"] = local_aware_dt.astimezone(pytz.utc)
            else:
                st.caption("🐦 X (Twitter)\n(Not Connected)")

        with col_p3:
            push_ig = False
            if st.session_state.get("ig_connected"):
                push_ig = st.checkbox("📸 Instagram", value=True)
                if push_ig:
                    with st.expander("⏰ IG Timing", expanded=True):
                        ig_date = st.date_input("IG Date", min_value=datetime.today(), key="ig_d")
                        ig_time = st.time_input("IG Time", key="ig_t")
                        # 🔄 NAYA: User ke time ko convert kar raha hai
                        naive_dt = datetime.combine(ig_date, ig_time)
                        local_aware_dt = local_tz.localize(naive_dt)
                        platform_schedule_map["instagram"] = local_aware_dt.astimezone(pytz.utc)
            else:
                st.caption("📸 Instagram\n(Not Connected)")

        with col_p4:
            push_th = False
            if st.session_state.get("th_connected"):
                push_th = st.checkbox("🧵 Threads", value=True)
                if push_th:
                    with st.expander("⏰ Threads Timing", expanded=True):
                        th_date = st.date_input("TH Date", min_value=datetime.today(), key="th_d")
                        th_time = st.time_input("TH Time", key="th_t")
                        # 🔄 NAYA: User ke time ko convert kar raha hai
                        naive_dt = datetime.combine(th_date, th_time)
                        local_aware_dt = local_tz.localize(naive_dt)
                        platform_schedule_map["threads"] = local_aware_dt.astimezone(pytz.utc)
            else:
                st.caption("🧵 Threads\n(Not Connected)")

        with col_p5:
            push_li = False
            if st.session_state.get("li_connected"):
                push_li = st.checkbox("💼 LinkedIn", value=True)
                if push_li:
                    with st.expander("⏰ LinkedIn Timing", expanded=True):
                        li_date = st.date_input("LI Date", min_value=datetime.today(), key="li_d")
                        li_time = st.time_input("LI Time", key="li_t")
                        # 🔄 NAYA: User ke time ko convert kar raha hai
                        naive_dt = datetime.combine(li_date, li_time)
                        local_aware_dt = local_tz.localize(naive_dt)
                        platform_schedule_map["linkedin"] = local_aware_dt.astimezone(pytz.utc)
            else:
                st.caption("💼 LinkedIn\n(Not Connected)")
        
        if push_yt:
            st.caption("*Note: YouTube API does not support custom thumbnails for Shorts. A frame will be auto-selected.*")
            
        st.write("---")
        
        # 🛡️ STEP 4: COMPLIANCE & KILL-SWITCH (Brought out of LinkedIn scope!)
        st.markdown("#### 🛡️ Step 4: Compliance & Safety")
        legal_1 = st.checkbox("I have reviewed and edited the AI-generated content and confirm it is ready for publishing.")
        legal_2 = st.checkbox("I take full responsibility for this posting. I understand that Creator AI OS is not liable for account strikes, spam bans, or TOS violations.")
        
        st.write(" ")
        
        # Bas 'disabled=not (legal_1 and legal_2)' add karna hai
        if st.button("🚀 EXECUTE MASTER ACTION PLAN", use_container_width=True, type="primary", disabled=not (legal_1 and legal_2)):
            if not uploaded_video:
                st.error("⚠️ Action Blocked: Please upload a video file first!")
            elif not (legal_1 and legal_2):
                st.error("⚠️ Action Blocked: You must agree to both compliance checkboxes before publishing.")
            elif not platform_schedule_map:
                st.warning("⚠️ Please select at least one platform to schedule.")
            else:
                with st.spinner("Initiating secure action pipeline..."):
                    try:
                        success_logs = []
                        st.info("✈️ Uploading video binary chunks to secure Telegram node...")
                        file_bytes = uploaded_video.read()
                        
                        # Triggering storage module function
                        video_cloud_url = upload_video_to_telegram(file_bytes, file_name=uploaded_video.name)
                        
                        if video_cloud_url:
                            st.info("🗄️ Splitting blueprints & Syncing with Supabase Cluster...")
                            
                            # Clean Variable mapping matrix safely resolving states
                            metadata_payload = {
                                "video_title": final_yt_title if final_yt_title else uploaded_video.name,
                                "youtube_description": final_yt_desc if final_yt_desc else "",
                                "twitter_thread_text": final_tw_thread if final_tw_thread else "",
                                "instagram_caption": final_ig_cap if final_ig_cap else "",
                                "threads_content": final_th_content if final_th_content else "",
                                "linkedin_post_text": final_li_post if final_li_post else ""
                            }
                            
                            # LOOP FOR MULTI-TIME OMNICHANNEL DISTRIBUTION
                            scheduling_errors = 0
                            for platform_name, target_datetime in platform_schedule_map.items():
                                db_response = insert_schedule_queue(
                                    creator_email=st.session_state.get("user_email"),
                                    platforms=[platform_name],  # Array containing single target platform
                                    video_url=video_cloud_url,
                                    scheduled_time=target_datetime, # Pure dynamic per-platform time matrix
                                    metadata_payload=metadata_payload
                                )
                                
                                if db_response:
                                    success_logs.append(f"📅 Locked: {platform_name.upper()} queue for {target_datetime.strftime('%Y-%m-%d %H:%M')}")
                                else:
                                    scheduling_errors += 1
                            
                            if scheduling_errors > 0:
                                st.error(f"❌ {scheduling_errors} platform schedules failed to sync with Database.")
                                
                            if success_logs:
                                st.success(f"🔥 BOOM! Action Plan execution complete:\n" + "\n".join(success_logs))
                                st.balloons()
                        else:
                            st.error("❌ Telegram node rejected the asset stream.")
                                
                    except Exception as master_e:
                        st.error(f"⚠️ Core Engine Failure: {str(master_e)}")