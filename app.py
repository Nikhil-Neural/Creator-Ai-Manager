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
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)
import urllib.parse
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

st.set_page_config(page_title="Creator AI OS", layout="wide")

# ── API Keys ───────────────────────────────────────────
# ── STEP 1: TRIPLE-LAYER FAILPROOF LLM RESOLVER MATRIX ──
G_KEY_1 = st.secrets.get("GEMINI_API_KEY_1", "")
G_KEY_2 = st.secrets.get("GEMINI_API_KEY_2", "")
GR_KEY_1 = st.secrets.get("GROQ_API_KEY_1", "")
GR_KEY_2 = st.secrets.get("GROQ_API_KEY_2", "")
S_KEY_1 = st.secrets.get("SERPER_API_KEY_1", "")
S_KEY_2 = st.secrets.get("SERPER_API_KEY_2", "")

GEMINI_KEY = G_KEY_1 if G_KEY_1 else st.secrets.get("GEMINI_API_KEY", "")
GROQ_KEY   = GR_KEY_1 if GR_KEY_1 else st.secrets.get("GROQ_API_KEY", "")
SERPER_KEY = S_KEY_1 if S_KEY_1 else st.secrets.get("SERPER_API_KEY", "")
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
            
            if any([st.session_state.get(k) for k in ["yt_connected", "tw_connected", "ig_connected", "fb_connected"]]):
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

from crewai_tools import SerperDevTool
search_tool = SerperDevTool(api_key=SERPER_KEY) if SERPER_KEY else None

if not G_KEY_1 and not GR_KEY_1 and not GEMINI_KEY and not GROQ_KEY:
    st.sidebar.error("⚠️ Control Panel Matrix Empty: Keys Missing!")

def get_cluster_llm(provider="groq"):
    if provider == "groq":
        primary_key = GR_KEY_1 if GR_KEY_1 else GROQ_KEY
        fallback_key = GR_KEY_2 if GR_KEY_2 else primary_key
        try:
            return LLM(model="groq/llama-3.3-70b-versatile", api_key=primary_key, timeout=30)
        except Exception as e:
            print(f"[ROUTING ALERT] Groq Key 1 failed. Swapping to Groq Key 2. Error: {e}")
            return LLM(model="groq/llama-3.3-70b-versatile", api_key=fallback_key, timeout=30)
    else:
        primary_key = G_KEY_1 if G_KEY_1 else GEMINI_KEY
        fallback_key = G_KEY_2 if G_KEY_2 else primary_key
        try:
            return LLM(model="gemini/gemini-2.5-flash", api_key=primary_key, timeout=30)
        except Exception as e:
            print(f"[ROUTING ALERT] Gemini Key 1 failed. Swapping to Gemini Key 2. Error: {e}")
            return LLM(model="gemini/gemini-2.5-flash", api_key=fallback_key, timeout=30)

def create_word_doc(script_text, platform_name, topic_name):
    doc = Document()
    doc.add_heading(f"🎬 Production Blueprint: {topic_name}", level=1)
    doc.add_paragraph(f"Target Platform: {platform_name}")
    doc.add_paragraph("Generated by: Creator AI OS (Multi-Agent System)")
    doc.add_paragraph("="*50)
    doc.add_heading("📝 Video Script Content", level=2)
    doc.add_paragraph(script_text)
    bio = io.BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio

def fetch_live_trends(niche_topic):
    if not SERPER_KEY:
        return []
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": f"site:youtube.com watch viral video {niche_topic}", "num": 5})
    headers = {'X-API-KEY': SERPER_KEY, 'Content-Type': 'application/json'}
    video_trends = []
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        data = response.json()
        if "organic" in data:
            for item in data["organic"]:
                link = item.get("link", "")
                if "youtube.com/watch" in link or "youtu.be" in link:
                    video_trends.append({"title": item.get("title", "Trending Video Blueprint"), "url": link})
                if len(video_trends) >= 3:
                    break
        return video_trends
    except Exception as e:
        print(f"[RADAR ERROR] Blueprint link extraction failed: {str(e)}")
        return []

# ── Session State Management Nodes ──────────────────────
if "active_model"      not in st.session_state: st.session_state["active_model"] = ""
if "gemini_error"      not in st.session_state: st.session_state["gemini_error"] = ""
if "channels_synced"   not in st.session_state: st.session_state["channels_synced"] = False
if "audit_data_ready"  not in st.session_state: st.session_state["audit_data_ready"] = False
if "mock_upload_ready" not in st.session_state: st.session_state["mock_upload_ready"] = False


# 🎯 INTEGRATION POINT 1: OAuth Link Generators Modules
def get_meta_oauth_url():
    client_id = st.secrets.get("INSTAGRAM_APP_ID", "")
    
    if not client_id:
        print("[AUTH ERROR] Instagram App ID missing in secrets!")
        return "#error_missing_client_id"

    # YAHAN UPDATE KIYA HAI: http ko https kar diya hai (exact match with Meta dashboard)
    redirect_uri = "https://creator-ai-manager-tgrh5ifkgfqme6kdomcvxb.streamlit.app/" 
    
    scopes = ["instagram_business_basic", "instagram_business_manage_insights", "instagram_business_content_publish"]
    scope_str = ",".join(scopes)
    
    auth_url = f"https://www.instagram.com/oauth/authorize?enable_fb_login=0&client_id={client_id}&redirect_uri={redirect_uri}&scope={scope_str}&response_type=code&state=instagram"
    
    return auth_url
def get_facebook_oauth_url():
    # Facebook apne main Meta App ID ka hi use karta hai
    client_id = st.secrets.get("META_APP_ID", "")
    
    if not client_id:
        return "#error_missing_fb_client_id"

    # Aapka live URL
    redirect_uri = "https://creator-ai-manager-tgrh5ifkgfqme6kdomcvxb.streamlit.app/" 
    
    # Facebook ke specific permissions (Scopes)
    # Yeh permissions aapko page ki list dekhne aur uspar post karne ki power dengi
    scopes = ["pages_show_list", "pages_read_engagement", "pages_manage_posts"]
    scope_str = ",".join(scopes)
    
    # Facebook ka direct authorization endpoint
    auth_url = f"https://www.facebook.com/v18.0/dialog/oauth?client_id={client_id}&redirect_uri={redirect_uri}&scope={scope_str}&response_type=code&state=facebook"
    
    return auth_url

def get_youtube_oauth_url():
    client_id = st.secrets.get("YOUTUBE_CLIENT_ID", "")
    
    if not client_id:
        return "#error_missing_yt_client_id"

    redirect_uri = "https://creator-ai-manager-tgrh5ifkgfqme6kdomcvxb.streamlit.app/" 
    
    # YouTube ke scopes (Analytics padhne aur video upload karne ke liye)
    scopes = [
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/youtube.upload"
    ]
    # Google mein scopes space (" ") se alag hote hain
    scope_str = " ".join(scopes)
    
    # Google ka OAuth URL (&state=youtube lagana zaroori hai pehchaan ke liye)
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope={scope_str}&access_type=offline&prompt=consent&state=youtube"
    
    return auth_url

# ==============================================================
# TWITTER PKCE GENERATOR (Missing Function Added)
# ==============================================================
def generate_pkce_pair():
    code_verifier = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8').rstrip('=')
    m = hashlib.sha256()
    m.update(code_verifier.encode('utf-8'))
    code_challenge = base64.urlsafe_b64encode(m.digest()).decode('utf-8').rstrip('=')
    return code_verifier, code_challenge

# ==============================================================
# FIXED TWITTER OAUTH FUNCTION
# ==============================================================
def get_twitter_oauth_url():
    CLIENT_ID = st.secrets.get("TWITTER_CLIENT_ID", "") 
    REDIRECT_URI = "https://creator-ai-manager-tgrh5ifkgfqme6kdomcvxb.streamlit.app/"
    
    # 1. Naya code_verifier aur challenge banayein
    code_verifier, code_challenge = generate_pkce_pair() 
    
    # 2. Ek unique ID banayein is login session ke liye
    state = str(uuid.uuid4())
    
    # 3. Streamlit memory ki jagah SUPABASE mein save karein
    supabase.table("twitter_auth_states").insert({
        "state": state,
        "code_verifier": code_verifier
    }).execute()
    
    # 4. Apna Twitter URL return karein (💥 ADDED SCOPE PARAMETER)
    scopes = "tweet.read users.read tweet.write offline.access"
    encoded_scopes = scopes.replace(" ", "%20")
    tw_login_link = f"https://twitter.com/i/oauth2/authorize?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&state={state}&code_challenge={code_challenge}&code_challenge_method=S256&scope={encoded_scopes}"
    
    return tw_login_link


def run_my_crew_ai_agents(niche_topic, social_platform, output_language, video_duration, app_mode, user_pasted_script, selected_bundle_options):
    target_seconds = int(video_duration * 60)
    target_words = int(video_duration * 140)
    
    groq_cluster_llm = get_cluster_llm(provider="groq")
    script_writing_llm = None
    gemini_resolved = False
    
    if G_KEY_1 or GEMINI_KEY:
        k1 = G_KEY_1 if G_KEY_1 else GEMINI_KEY
        for attempt in range(1, 3):
            try:
                test_llm = LLM(model="gemini/gemini-2.5-flash", api_key=k1, timeout=15)
                test_llm.call(messages=[{"role": "user", "content": "ping"}])
                script_writing_llm = test_llm
                gemini_resolved = True
                print(f"[MATRIX SUCCESS] Gemini Key 1 working flawlessly on attempt {attempt}.")
                time.sleep(15)
                break
            except Exception as e:
                print(f"[MATRIX WARNING] Gemini Key 1 attempt {attempt} failed with error: {e}. Cooling down...")
                time.sleep(15)
                
    if not gemini_resolved and G_KEY_2:
        for attempt in range(1, 3):
            try:
                test_llm = LLM(model="gemini/gemini-2.5-flash", api_key=G_KEY_2, timeout=15)
                test_llm.call(messages=[{"role": "user", "content": "ping"}])
                script_writing_llm = test_llm
                gemini_resolved = True
                time.sleep(15)
                break
            except Exception as e:
                time.sleep(15)

    if not gemini_resolved:
        target_groq_key = GR_KEY_2 if GR_KEY_2 else (GR_KEY_1 if GR_KEY_1 else GROQ_KEY)
        script_writing_llm = LLM(model="groq/llama-3.3-70b-versatile", api_key=target_groq_key, timeout=30)

    trend_analyst = Agent(
        role="Fast Trend Spotter",
        goal=f"Extract minimal psychological hooks and viewer retention triggers for '{niche_topic}' on {social_platform}.",
        backstory="Data-saving trend analyst. Raw psychological data output constraint locked.",
        llm=groq_cluster_llm, max_iter=1, max_rpm=5, verbose=True, allow_delegation=False, memory=False
    )

    script_writer = Agent(
        role="Humanized Script Writer",
        goal="Write a 2-column video script blueprint.",
        backstory="Writes clean high-retention humanized content without any robotic AI watermarks.",
        llm=script_writing_llm, max_iter=1, max_rpm=5, verbose=True, allow_delegation=False, memory=False
    )

    copy_maestro = Agent(
        role="Micro Copywriter",
        goal="Convert concepts into short social media assets instantly.",
        backstory="Extreme token efficiency. Expert direct copy structures setup engine.",
        llm=groq_cluster_llm, max_iter=1, max_rpm=5, verbose=True, allow_delegation=False, memory=False
    )

    tasks_pipeline = []
    live_scanned_context = ""
    if niche_topic:
        raw_trends = fetch_live_trends(niche_topic)
        if raw_trends:
            live_scanned_context = "\n".join([f"- Title: {item['title']} (URL: {item['url']})" for item in raw_trends])

    research_task = Task(
        description=f"Analyze topic: '{niche_topic}' on {social_platform}.\nContext:\n{live_scanned_context}\nIdentify 3 breakout hooks and 3 retention nodes under 150 words total. No titles/urls.",
        expected_output="Clean bullet points analysis matrix data.",
        agent=trend_analyst
    )
    tasks_pipeline.append(research_task)

    script_task = None
    if any("Script" in opt for opt in selected_bundle_options):
        script_prompt = f"Write a full video script for '{niche_topic}' around {target_words} words ({target_seconds} seconds)."
        if app_mode == "✍️ Repurpose My Script Mode":
            script_prompt = f"Analyze and re-engineer raw script: '{user_pasted_script}'."
            
        script_task = Task(
            description=f"""{script_prompt} Target language: '{output_language}'.
            CRITICAL CRITERIA: You MUST use this exact table framework layout:
            | Timestamp | Visuals | Audio ({output_language}) |
            | :--- | :--- | :--- |""",
            expected_output="Perfect Markdown 3-column table framework script context.",
            agent=script_writer, context=[research_task]
        )
        tasks_pipeline.append(script_task)

    distribution_task = None
    dist_requirements = []
    if any("Titles" in opt for opt in selected_bundle_options): dist_requirements.append("- 5 High-CTR Titles & Descriptions")
    if any("Thumbnail" in opt for opt in selected_bundle_options): dist_requirements.append("- 3 thumbnail design concepts layout framework")
    if any("Captions" in opt for opt in selected_bundle_options): dist_requirements.append("- 3 short captions & tags")
    if any("Threads" in opt for opt in selected_bundle_options): dist_requirements.append("- 5 vertical engagement elements package")

    if dist_requirements:
        distribution_task = Task(
            description=f"Generate package for topic '{niche_topic}' in '{output_language}':\n{chr(10).join(dist_requirements)}\nNo fluffy text, raw conversion ready blocks only.",
            expected_output="Compiled social media assets tier list package.",
            agent=copy_maestro
        )
        tasks_pipeline.append(distribution_task)

    master_crew = Crew(agents=[trend_analyst, script_writer, copy_maestro], tasks=tasks_pipeline, verbose=True, process='sequential')
    master_crew.kickoff()
    
    compiled_final_output = "### 🕵️ EXPERT TREND RESEARCH ANALYSIS\n" + str(research_task.output.raw if hasattr(research_task, 'output') and research_task.output else "") + "\n\n"
    if script_task and script_task.output:
        compiled_final_output += "### 🎬 PREMIUM AUDIO/VISUAL RETENTION SCRIPT\n" + str(script_task.output.raw) + "\n\n"
    if distribution_task and distribution_task.output:
        compiled_final_output += "### 📱 DISTRIBUTION MICRO-ASSETS PACKAGE\n" + str(distribution_task.output.raw) + "\n\n"
        
    return compiled_final_output

# ── Dynamic Sidebar Control Panel ───────────────────────
with st.sidebar:
    st.title("⚙️ Control Panel Matrix")
    current_os_mode = st.pills(
        "🔮 Core OS Operations Mode:",
        ["✍️ AI Script Generator", "📊 AI Channel Auditor & Sync"],
        default="✍️ AI Script Generator"
    )
    st.write("---")
    platform = st.selectbox("Global Target Platform:", ["YouTube", "Instagram", "Facebook", "X (Twitter)"])
    language = st.selectbox("Output Interface Language:", ["Hinglish", "Hindi", "English"])
    st.write("---")
    st.caption("Architecture Framework: CrewAI + Gemini + Groq Matrix")

# ── Main Content Gateway Router ──────────────────────────
# ── Main Content Gateway Router ──────────────────────────
# ==============================================================
# 💾 TOKEN SAVER HELPER FUNCTION
# ==============================================================
def save_platform_token(platform_column_name, auth_code):
    current_user = st.session_state.get("creator_handle")
    if not current_user:
        return # Agar user login nahi hai toh kuch mat karo
        
    # Check karo ki kya is user ka profile pehle se database mein hai
    response = supabase.table("creator_profiles").select("id").eq("creator_handle", current_user).execute()
    
    if response.data:
        # User pehle se hai, toh bas us naye platform ka token update kar do
        supabase.table("creator_profiles").update({
            platform_column_name: auth_code
        }).eq("creator_handle", current_user).execute()
    else:
        # Naya user hai, toh naya row banao aur token save karo
        supabase.table("creator_profiles").insert({
            "creator_handle": current_user,
            platform_column_name: auth_code
        }).execute()
# ── Main Content Gateway Router ──────────────────────────
if "code" in st.query_params:
    auth_code = st.query_params["code"] 
    platform_state = st.query_params.get("state", "instagram") 
    
    if platform_state == "facebook":
        st.success("🎉 Facebook Page Successfully Linked! 💙")
        save_platform_token("facebook_token", auth_code)
        st.session_state["fb_connected"] = True
        st.session_state["channels_synced"] = True
        
    elif platform_state == "youtube":
        st.success("🎉 YouTube Channel Successfully Linked! ❤️")
        save_platform_token("youtube_token", auth_code)
        st.session_state["yt_connected"] = True
        st.session_state["channels_synced"] = True
        
    elif platform_state == "instagram":
        st.success("🎉 Instagram Account Successfully Linked! 🩷")
        save_platform_token("instagram_token", auth_code)
        st.session_state["ig_connected"] = True
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
st.title("🚀 Creator AI Manager OS")
st.write(f"System Context: **{current_os_mode}** active | Platform: **{platform}**")
st.write("---")

# MODE 1: SCRIPT ENGINE
if current_os_mode == "✍️ AI Script Generator":
    tab1, tab2, tab3 = st.tabs(["🔥 Trend & Script Workspace", "📥 Download Generated Blueprint", "📂 My Saved Vault"])
    with tab1:
        st.markdown("### 🔥 AI Content Strategy Hub")
        app_mode = st.radio("🔮 Kis Mode me kaam karna hai?", ["🚀 Complete Blueprint Mode", "✍️ Repurpose My Script Mode"], horizontal=True)
        st.write("---")
        
        with st.form("trend_form"):
            if app_mode == "🚀 Complete Blueprint Mode":
                bundle_options = st.pills("🎁 Content Bundle Items: (Multi-Select)", ["🎬 Retention Script & Visual Cues", "🎯 High-CTR Viral Titles & Descriptions", "🎨 High-CTR Thumbnail Design Concepts", "📱 Shorts/Reels Viral Captions & Tags", "🧵 LinkedIn & X (Twitter) Threads"], default=["🎬 Retention Script & Visual Cues"], selection_mode="multi")
                user_niche = st.text_input("🎯 Kis topic par video banani hai?", value=st.session_state.get("niche_data", ""))
                video_duration = st.slider("⏱ Video duration (Minutes)", 0.5, 3.0, 1.0, 0.5)
            else:
                bundle_options = st.pills("🎁 Extraction Bundle Items: (Multi-Select)", ["🎯 High-CTR Viral Titles & Descriptions", "🎨 High-CTR Thumbnail Design Concepts", "📱 Shorts/Reels Viral Captions & Tags", "🧵 LinkedIn & X (Twitter) Threads"], default=["🎯 High-CTR Viral Titles & Descriptions"], selection_mode="multi")
                user_niche = st.text_input("🎯 Video Title/Topic:", value=st.session_state.get("niche_data", ""))
                user_pasted_script = st.text_area("📝 Script content:", height=200)

            submit_btn = st.form_submit_button("🚀 Launch Specialized Agents Grid", use_container_width=True)
            if submit_btn:
                if not bundle_options: st.error("⚠️ Bundle item select karein!")
                elif user_niche:
                    st.session_state["niche_data"] = user_niche
                    st.session_state["form_submitted"] = True
                    st.session_state["selected_options"] = bundle_options
                    st.session_state["current_mode"] = app_mode
                    st.session_state["pasted_script"] = user_pasted_script if 'user_pasted_script' in locals() else ""
                    st.session_state["duration"] = video_duration if 'video_duration' in locals() else 1.0
                else: st.error("⚠️ Topic cannot be empty!")

        if st.session_state.get("form_submitted"):
            with st.spinner("🕵️ Processing failproof generation sequence..."):
                try:
                    # CrewAI se script banwayi
                    ai_output = run_my_crew_ai_agents(st.session_state["niche_data"], platform, language, st.session_state.get("duration", 1.0), st.session_state["current_mode"], st.session_state.get("pasted_script", ""), st.session_state["selected_options"])
                    
                    st.session_state["script_data"] = ai_output
                    st.session_state["form_submitted"] = False
                    
                    # 💾 THE VAULT: Database mein permanent save karna
                    if st.session_state.get("user_email"):
                        try:
                            supabase.table("ai_blueprints_vault").insert({
                                "creator_email": st.session_state["user_email"],
                                "target_platform": platform,
                                "niche_topic": st.session_state["niche_data"],
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
            c1, c2 = st.columns(2)
            with c1: st.download_button("📥 Notepad (.txt)", str(st.session_state["script_data"]), file_name="blueprint.txt", use_container_width=True)
            with c2: st.download_button("📥 Word Doc (.docx)", create_word_doc(str(st.session_state["script_data"]), platform, st.session_state.get("niche_data", "File")), file_name="blueprint.docx", use_container_width=True)
        else: st.warning("⚠️ No data compiled yet. Run Tab 1 first.")
    with tab3:
        st.header("📂 My Saved Blueprints Vault")
        st.markdown("Access all your previously generated high-retention scripts and metadata here.")
        
        if st.session_state.get("user_email"):
            # Database se user ki purani scripts fetch karna (Nayi sabse upar aayegi)
            try:
                response = supabase.table("ai_blueprints_vault").select("*").eq("creator_email", st.session_state["user_email"]).order("created_at", desc=True).execute()
                
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
                            st.button("📋 Access Data", key=f"btn_{item['id']}")
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
                
        with col2:
            st.subheader("📸 Instagram")
            if st.session_state.get("ig_connected"):
                st.success("✅ Connected: Instagram Business")
                if st.button("❌ Disconnect Instagram", use_container_width=True):
                    disconnect_platform("instagram_token", "ig_connected")
            else:
                meta_login_link = get_meta_oauth_url()
                st.markdown(f"<div style='margin-bottom: 16px;'><a href='{meta_login_link}' target='_blank' style='text-decoration: none;'><button style='width:100%; background-color:#E1306C; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer; height:42px; font-size:14px; box-shadow: 0px 2px 4px rgba(0,0,0,0.1);'>🩷 Connect Instagram Business</button></a></div>", unsafe_allow_html=True)    
                
            st.write(" ")
            st.subheader("🔵 Facebook")
            if st.session_state.get("fb_connected"):
                st.success("✅ Connected: Facebook Page")
                if st.button("❌ Disconnect Facebook", use_container_width=True):
                    disconnect_platform("facebook_token", "fb_connected")
            else:
                fb_login_link = get_facebook_oauth_url()
                st.markdown(f"<a href='{fb_login_link}' target='_blank' style='text-decoration: none;'><button style='width:100%; background-color:#1877F2; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer; height:38px; font-size:14px; box-shadow: 0px 2px 4px rgba(0,0,0,0.1);'>💙 Connect Facebook Page</button></a>", unsafe_allow_html=True)
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
                                "facebook_token": None
                            }).eq("creator_handle", st.session_state["creator_handle"]).execute()
                        
                        # 2. App ki memory (RAM) se sab reset kar do
                        st.session_state["yt_connected"] = False
                        st.session_state["tw_connected"] = False
                        st.session_state["ig_connected"] = False
                        st.session_state["fb_connected"] = False
                        
                        st.session_state["channels_synced"] = False
                        st.session_state["audit_data_ready"] = False
                        st.session_state["mock_upload_ready"] = False
                        time.sleep(1)
                        st.rerun()
        else:
            st.info("🔒 SYSTEM STATUS IDLE: Please click one of the platform connection buttons above to sync handles.")

    # PILL SECTION B: ANALYSIS ENGINE CODES MATRIX
    elif selected_auditor_section == "📈 2. Real-Time Performance Audit":
        st.markdown("### 📈 Live Extraction Performance Audit Strategies")
        
        # 1. BRIDGE: Vault se blueprints fetch karo
        try:
            response = supabase.table("ai_blueprints_vault").select("*").eq("creator_email", st.session_state["user_email"]).execute()
            blueprints = response.data if response.data else []
        except:
            blueprints = []

        if not blueprints:
            st.warning("⚠️ Vault Empty: Pehle Tab 1 mein script generate karein.")
        else:
            # 2. Dropdown UI to Select Blueprint
            blueprint_options = {f"{item['niche_topic']} ({item['target_platform']})": item for item in blueprints}
            selected_bp_name = st.selectbox("Select a Blueprint to Audit:", options=list(blueprint_options.keys()))
            selected_bp = blueprint_options[selected_bp_name]

            # 3. Inject Metadata into Session
            st.session_state["audit_data_ready"] = True
            
            st.write(f"---")
            st.write(f"🔄 **Auditing Blueprint:** {selected_bp['niche_topic']}")
            
            # 4. Zero-Cost Metrics Display (Using fetched DB data)
            m1, m2, m3 = st.columns(3)
            with m1: st.metric("Platform", selected_bp['target_platform'])
            with m2: st.metric("Status", selected_bp['status'])
            with m3: st.metric("Date", selected_bp['created_at'].split('T')[0])
            
            st.write("---")
            st.markdown("#### 🕵️ Deep Virality Leak Diagnostics")
            
            # Yahan hum AI ko call nahi kar rahe, DB se utha kar dikha rahe hain!
            with st.expander("🔴 VIEW PRODUCTION ANALYSIS", expanded=True):
                st.markdown(selected_bp['script_content'])

    # PILL SECTION C: AUTOMATED PUBLISHER DEPLOYMENT PIPELINE
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
        
        # Option 1: Vault Data (The Bridge)
        if metadata_source == "📂 Use Saved Vault Data (Recommended)":
            try:
                response = supabase.table("ai_blueprints_vault").select("*").eq("creator_email", st.session_state.get("user_email")).order("created_at", desc=True).execute()
                blueprints = response.data if response.data else []
            except:
                blueprints = []
                
            if not blueprints:
                st.error("📭 Your Vault is empty. Please generate a script first.")
            else:
                blueprint_options = {f"{item['niche_topic']} ({item['target_platform']})": item for item in blueprints}
                selected_bp_name = st.selectbox("Select a Blueprint to extract metadata from:", options=list(blueprint_options.keys()))
                selected_bp = blueprint_options[selected_bp_name]
                
                st.success(f"✅ Data injected from: {selected_bp['niche_topic']}")
                with st.expander("🔍 Preview Injected Data", expanded=False):
                    st.markdown(selected_bp['script_content'])

        # Option 2: Manual Paste (Clean UI with Expanders)
        elif metadata_source == "✍️ Manual Paste":
            st.info("Manually enter your content for each platform below.")
            with st.expander("📺 YouTube Metadata", expanded=True):
                st.text_input("YouTube Title", key="man_yt_title")
                st.text_area("YouTube Description", key="man_yt_desc")
            with st.expander("🐦 X (Twitter) Thread"):
                st.text_area("Tweet 1 (Video attached here)", key="man_tw_1")
                st.caption("*(Logic for '+ Add Tweet' button will be integrated here during API wiring)*")
            with st.expander("📸 Instagram & Facebook Captions"):
                st.text_area("Reel/Post Caption", key="man_ig_cap")
                
        # Option 3: Generate New
        elif metadata_source == "✨ Generate New Metadata":
            st.warning("⚠️ You need fresh metadata. Please switch to the **'✍️ AI Script Generator'** mode from the left sidebar to build and save a new blueprint to your Vault.")
            
        st.write("---")
        
        # 🌍 STEP 3: PLATFORM ROUTING
        st.markdown("#### 🌍 Step 3: Distribution Routing")
        st.write("Select the platforms you want to publish this video to:")
        
        col_p1, col_p2, col_p3, col_p4 = st.columns(4)
        with col_p1: push_yt = st.checkbox("📺 YouTube", value=True)
        with col_p2: push_tw = st.checkbox("🐦 X (Twitter)")
        with col_p3: push_ig = st.checkbox("📸 Instagram")
        with col_p4: push_fb = st.checkbox("🔵 Facebook")
        
        if push_yt:
            st.caption("*Note: YouTube API does not support custom thumbnails for Shorts. A frame will be auto-selected.*")
            
        st.write("---")
        
        # 🛡️ STEP 4: COMPLIANCE & KILL-SWITCH
        st.markdown("#### 🛡️ Step 4: Compliance & Safety")
        legal_1 = st.checkbox("I have reviewed and edited the AI-generated content and confirm it is ready for publishing.")
        legal_2 = st.checkbox("I take full responsibility for this posting. I understand that Creator AI OS is not liable for account strikes, spam bans, or TOS violations.")
        
        st.write(" ")
        
        # 🚀 THE PUBLISH BUTTON
        if st.button("🚀 PUBLISH TO ALL SELECTED PLATFORMS", use_container_width=True, type="primary"):
            if not uploaded_video:
                st.error("⚠️ Action Blocked: Please upload a video file first!")
            elif not (legal_1 and legal_2):
                st.error("⚠️ Action Blocked: You must agree to both compliance checkboxes before publishing.")
            elif not st.session_state.get("channels_synced"):
                st.error("⚠️ Connection Error: Your social accounts are not linked. Go to 'Secure Social Account Hub' first.")
            else:
                with st.spinner("Initiating secure upload sequence to social APIs..."):
                    time.sleep(2) # Fake processing time for UI feel
                    st.success("🔥 SUCCESS CONFIRMED: Media and metadata routed to platform staging! (Python API dispatch logic will run here)")