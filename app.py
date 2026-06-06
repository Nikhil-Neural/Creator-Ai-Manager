import streamlit as st
import os
from crewai import Agent, Task, Crew, LLM

# 1. Page Configuration
st.set_page_config(page_title="Creator AI OS", layout="wide")

# 🔐 API Key Security Check
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
else:
    st.sidebar.warning("⚠️ Please set GEMINI_API_KEY in secrets to activate AI!")

# 🧠 REAL BACKEND: Controlled & Safe CrewAI Function
def run_my_crew_ai_agents(niche_topic, social_platform, output_language):
    
    # 🌟 UPGRADE: Lagaye gaye hain strict guards taaki Free API limits khatam na ho (Loop Chaos Protection)
    my_llm = LLM(
        model="gemini/gemini-2.5-flash", 
        api_key=os.environ["GEMINI_API_KEY"],
        max_rpm=2,       # 1 minute me max 2 requests (Strict Limit)
        timeout=30,      # Server slow hone par 30 seconds ka sabr (Wait time)
        max_retries=2    # Fail hone par crash nahi hoga, 2 baar fir koshish karega
    )
    
    # 2. Agent 1: Script Writer Agent (Strictly Single Controlled Agent)
    script_writer = Agent(
        role="Expert Social Media Script Writer",
        goal=f"Create a single highly viral script blueprint for {social_platform} on '{niche_topic}' in {output_language}.",
        backstory="A disciplined scriptwriter who delivers exact results in one go without wasting API calls or repeating queries.",
        llm=my_llm,
        allow_delegation=False, # Isko false rakha h taaki ye deuse agents se loop na banaye
        verbose=True
    )
    
    # 3. Task: Isko ekdum clear and limited instruction dena
    write_script_task = Task(
        description=f"Write a standard video script structure for {social_platform}. Topic: {niche_topic}. Language: {output_language}. Keep it precise and do not call the model recursively.",
        expected_output="A well-formatted script with timing blocks like [00:00 - 00:05] Hook, Shot Description, and dialogues.",
        agent=script_writer
    )
    
    # 4. Crew Connection
    crew = Crew(
        agents=[script_writer],
        tasks=[write_script_task],
        verbose=True
    )
    
    # Run the controlled crew
    result = crew.kickoff()
    
    return str(result)

# 2. Tijori (Session State) Setup
if "niche_data" not in st.session_state:
    st.session_state["niche_data"] = ""

if "script_data" not in st.session_state:
    st.session_state["script_data"] = ""

# 3. Sidebar Layout (Yahan variables: platform aur language hain)
with st.sidebar:
    st.title("⚙️ Control Panel")
    platform = st.selectbox("Platform Chunein:", ["YouTube", "Instagram", "Facebook", "X (Twitter)"])
    language = st.selectbox("Language / Bhasha:", ["Hinglish", "Hindi", "English"])
    st.write("---")
    st.caption("Powered by Gemini & CrewAI")

# 4. Main Screen Title
st.title("🚀 Creator AI Manager")
st.write(f"Abhi aapka **{platform}** manager active hai, aur AI aapko **{language}** me reply karega.")
st.write("---")

# 5. Creating Tabs
tab1, tab2, tab3 = st.tabs(["🔥 Trend Researcher", "📝 Script Generator", "📊 Channel Analytics"])

# --- TAB 1: TREND RESEARCHER ---
with tab1:
    st.header("Find What's Viral Today")
    
    # Form ka use kiya taaki page button dabane par hi refresh ho
    with st.form("trend_form"):
        user_niche = st.text_input(
            "Apna Niche ya Topic dalein:", 
            value=st.session_state["niche_data"],
            placeholder="Yahan type karein..."
        ) 
        
        submit_btn = st.form_submit_button("🚀 Scrap & Analyze Trends")
        
        if submit_btn:
            if user_niche:
                with st.spinner("🧠 AI Agents active ho rahe hain... Script taiyar ho rahi hai..."):
                    # 🌟 FIXED CONNECTION: Yahan niche platform=platform aur output_language=language kar diya h match karne k liye
                    ai_output = run_my_crew_ai_agents(
                        niche_topic=user_niche, 
                        social_platform=platform, 
                        output_language=language
                    )
                    
                    # Tijori me data save karna
                    st.session_state["niche_data"] = user_niche
                    st.session_state["script_data"] = ai_output
                
                st.success("🎉 Asli AI Script ready hai! Kripya 'Script Generator' tab par jayein.")
            else:
                st.error("Kripya 'Apna Niche dalein' wale box me kuch likhein!")

# --- TAB 2: SCRIPT GENERATOR ---
with tab2:
    st.header("AI Script & Cinematography Blueprint")
    
    if st.session_state["script_data"] != "":
        st.success("Aapki Script Taiyar Hai!")
        # 🌟 REAL OUTPUT: Jo AI generate karega use screen par print karna
        st.write(st.session_state["script_data"])
    else:
        st.warning("Pehle Tab 1 par jaakar trends analyze karein, tabhi script banegi.")

# --- TAB 3: CHANNEL ANALYTICS ---
with tab3:
    st.header("📊 Multi-Platform Weekly Performance Report")
    st.caption("Aapke saare linked social media handles ki progress yahan dikhegi.")
    st.write("---")
    
    m_col1, m_col2, m_col3 = st.columns(3)
    
    with m_col1:
        st.subheader("🔴 YouTube Stats")
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