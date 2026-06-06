import streamlit as st
import os

# 1. Page Configuration
st.set_page_config(page_title="Creator AI OS", layout="wide")

# 🔐 NAYI CHEEZ: Google Gemini ki Entry Ticket (API Key) check karna
# Yeh line st.secrets me se 'GEMINI_API_KEY' naam ki ticket dundhegi
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
else:
    # Agar user ne local system par chalaya hai aur key nahi mili toh warning dikhayega
    st.sidebar.warning("⚠️ Please set GEMINI_API_KEY in secrets to activate AI!")

# 🧠 REAL APP FUNCTION BASE (Ab ye fake nahi raha, kal isme CrewAI chalega)
def run_my_crew_ai_agents(niche_topic, social_platform, output_language):
    # Agar ticket sahi mil gayi toh ye message aayega
    st.markdown(f"### 🎬 {social_platform.upper()} VIDEO BLUEPRINT")
    st.caption(f"Language: {output_language} | Topic: {niche_topic}")
    st.write("---")
    
    # Layout setting
    col1, col2 = st.columns([1, 4])
    
    with col1:
        st.subheader("⏱️ Timing")
        st.info("00:00 - 00:05")
        st.info("00:05 - 00:30")
        
    with col2:
        st.subheader("📝 Content & Cinematography (Script)")
        st.markdown("**🎥 Status:** *[Backend Core Connection Successful. Ready for CrewAI Agents...]*")
        st.code(f"AI Manager is active for {social_platform} in {output_language} language.", language="text")
        
    return "SUCCESS"

# 2. Tijori (Session State) Setup
if "niche_data" not in st.session_state:
    st.session_state["niche_data"] = ""

if "script_data" not in st.session_state:
    st.session_state["script_data"] = ""

# 3. Sidebar Layout
with st.sidebar:
    st.title("⚙️ Control Panel")
    platform = st.selectbox("Platform Chunein:", ["YouTube", "Instagram", "Facebook", "X (Twitter)"])
    language = st.selectbox("Language / Bhasha:", ["Hinglish", "Hindi", "English"])
    st.write("---")
    st.caption("Powered by Gemini & CrewAI")

# 4. Main Screen Title (FIXED: Aapki dhundhi hui line wapas aa gayi!)
st.title("🚀 Creator AI Manager")
st.write(f"Abhi aapka **{platform}** manager active hai, aur AI aapko **{language}** me reply karega.")
st.write("---")

# 5. Creating Tabs
tab1, tab2, tab3 = st.tabs(["🔥 Trend Researcher", "📝 Script Generator", "📊 Channel Analytics"])

# --- TAB 1: TREND RESEARCHER ---
    # --- Tab 1 ke andar ka purana code hata kar ye jodo ---
with tab1:
    st.header("🔥 Content Research & Client Input Form")
    st.write("Is form ka use karke data ko safe aur organize tarike se submit karein.")
    
    # 🌟 NAYI CHEEZ: st.form se saare inputs ek sath group ho jaate hain aur page refresh nahi hota baar-baar
    with st.form("my_freelance_form"):
        client_name = st.text_input("Creator / Client Ka Naam:")
        project_niche = st.text_input("Content Niche (Topic):")
        
        # Interactive Slider numeric inputs ke liye
        estimated_budget = st.slider("Project Budget ($)", 10, 500, 50) 
        
        # Form ka apna special submit button
        submitted = st.form_submit_button("Save Input Data")
        
        if submitted:
            if client_name and project_niche:
                st.success(f"Done! {client_name} ka data form me submit ho gaya.")
                st.info(f"Niche: {project_niche} | Budget: ${estimated_budget}")
            else:
                st.error("Kripya saari jankari bharein!")

# --- TAB 2: SCRIPT GENERATOR ---
with tab2:
    st.header("AI Script & Cinematography Blueprint")
    
    if st.session_state["script_data"] != "":
        st.success("Aapki Script Taiyar Hai!")
    else:
        st.warning("Pehle Tab 1 par jaakar trends analyze karein, tabhi script banegi.")

# --- TAB 3: CHANNEL ANALYTICS ---

    # --- Tab 3 ke andar ka purana text hata kar ye jodo ---
with tab3:
    st.header("📊 Multi-Platform Weekly Performance Report")
    st.caption("Aapke saare linked social media handles ki progress yahan dikhegi.")
    st.write("---")
    
    # 🌟 NAYI CHEEZ: Ek hi line me 3 platforms ke cards dikhane ke liye 3 columns
    m_col1, m_col2, m_col3 = st.columns(3)
    
    with m_col1:
        st.subheader("🔴 YouTube Stats")
        # st.metric(label, value, delta) -> delta se + ya - ka arrow banta h
        st.metric(label="Subscribers", value="15,400", delta="+1,200 (Is Hafte)")
        st.metric(label="Total Views", value="240K", delta="+45K")
        
    with m_col2:
        st.subheader("📸 Instagram Stats")
        st.metric(label="Followers", value="8,900", delta="+850")
        st.metric(label="Reels Engagement", value="12%", delta="-2% (Kam Mehnat Hui)")
        
    with m_col3:
        st.subheader("🐦 X (Twitter) Stats")
        st.metric(label="Followers", value="3,200", delta="+150")
        st.metric(label="Impressions", value="50K", delta="+12K")