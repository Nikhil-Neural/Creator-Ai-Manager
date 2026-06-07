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
# --- Real Backend: 2 Agents Connection (Researcher + Writer) ---
def run_my_crew_ai_agents(niche_topic, social_platform, output_language):
    
    my_llm = LLM(
        model="gemini/gemini-2.5-flash", 
        api_key=os.environ["GEMINI_API_KEY"],
        max_rpm=2,       
        timeout=30,      
        max_retries=2    
    )
    
    # 🕵️‍♂️ AGENT 1: Trend Researcher (Naya Agent!)
    trend_researcher = Agent(
        role="Senior Content Trend Analyst",
        goal=f"Analyze what hooks people on the topic '{niche_topic}' for {social_platform}.",
        backstory="An expert in studying viral retention algorithms. Knows exactly what sub-topics are trending right now.",
        llm=my_llm,
        allow_delegation=False,
        verbose=True
    )
    
    # 📝 AGENT 2: Script Writer (Aapka purana agent)
    script_writer = Agent(
        role="Expert Social Media Script Writer",
        goal=f"Create a single highly viral script blueprint in {output_language} based on the Researcher's findings.",
        backstory="A disciplined scriptwriter who takes raw research and turns it into high-retention video blueprints.",
        llm=my_llm,
        allow_delegation=False,
        verbose=True
    )
    
    # 📋 TASK 1: Research Kaam
    research_task = Task(
        description=f"Identify 3 viral angles or psychological hooks for the topic: {niche_topic} on {social_platform}.",
        expected_output="Top 3 viral sub-themes or hooks for this specific content niche.",
        agent=trend_researcher
    )
    
    # 📋 TASK 2: Writing Kaam (Iske paas piche se research ka data automatic aayega)
    write_script_task = Task(
        description=f"Using the 3 viral angles found by the researcher, write a complete video script for {social_platform} in {output_language} language.",
        expected_output="A well-formatted script with timing blocks like [00:00 - 00:05] Hook, Shot Description, and dialogues.",
        agent=script_writer
    )
    
    # 🤝 THE REAL CREW: Ab dono agents line se kaam karenge sequential order me!
    crew = Crew(
        agents=[trend_researcher, script_writer],
        tasks=[research_task, write_script_task],
        verbose=True
    )
    
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
# --- TAB 1: TREND RESEARCHER (Premium Designer Look) ---
with tab1:
    # Ek sundar banner aur subtitle
    st.markdown("### 🔥 AI Content Strategy Hub")
    st.caption("Apna topic daliye aur hamare dual-agents (Researcher + Writer) ko apna jaadu karne dijiye.")
    st.write("---")
    
    # Poore form ko ek sundar clean box (container) me daalna
    with st.container():
        with st.form("trend_form"):
            # Input Section ko clean banana
            user_niche = st.text_input(
                "🎯 Kis topic par video banani hai?", 
                value=st.session_state["niche_data"],
                placeholder="E.g., What is AGI, Stoicism Guide, Python for Beginners..."
            )
            
            # Ek choti warning indicator taaki user ko pata rahe background me kya chal rha h
            st.markdown(
                f"ℹ️ *AI is current set for **{platform}** in **{language}** mode. Change settings from the sidebar if needed.*"
            )
            
            # Submit Button ko full-width aur design dena
            submit_btn = st.form_submit_button("🚀 Launch AI Agents & Generate Blueprint", use_container_width=True)
            
            if submit_btn:
                if user_niche:
                    # Spinner text ko thoda aur exciting banana
                    with st.spinner("🕵️‍♂️ Senior Analyst is researching hooks... Please wait 15 seconds..."):
                        ai_output = run_my_crew_ai_agents(
                            niche_topic=user_niche, 
                            social_platform=platform, 
                            output_language=language
                        )
                        
                        st.session_state["niche_data"] = user_niche
                        st.session_state["script_data"] = ai_output
                    
                    st.success("✨ Success! Research and Script generation complete. Go to 'Script Generator' tab.")
                else:
                    st.error("⚠️ Opps! Kripya 'Topic' waale box me kuch likhein barna agents confuse ho jayenge!")

# --- TAB 2: SCRIPT GENERATOR ---
    # --- TAB 2: SCRIPT GENERATOR (With Pro Download Feature) ---
with tab2:
    st.header("📝 AI Script & Cinematography Blueprint")
    st.write("---")
    
    if st.session_state["script_data"] != "":
        st.success("🎉 Aapki Script Taiyar Hai!")
        
        # 🌟 REAL OUTPUT: Jo AI ne generate kiya use saaf-saaf border ke andar dikhana
        st.info("💡 Tip: Aap is script ko neeche diye gaye button se download kar sakte hain.")
        st.text_area("Your Generated Script:", value=st.session_state["script_data"], height=400)
        
        # 📥 PRO FEATURE: Download Button Integration
        # Yeh button session state ke data ko uthayega aur text file me convert kar dega
        st.download_button(
            label="📥 Download Script as Text File",
            data=st.session_state["script_data"],
            file_name=f"{platform.lower()}_{st.session_state['niche_data'].replace(' ', '_')}_script.txt",
            mime="text/plain"
        )
    else:
        st.warning("⚠️ Pehle Tab 1 par jaakar trends analyze karein, tabhi script banegi.")

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