# ── Groq Cache Fix ─────────────────────────────────────
try:
    from crewai.llms import cache as _cache
    _cache.mark_cache_breakpoint = lambda msg: msg
except ImportError:
    pass

import streamlit as st
import os
from crewai import Agent, Task, Crew, LLM

st.set_page_config(page_title="Creator AI OS", layout="wide")

# ── API Keys ───────────────────────────────────────────
GEMINI_KEY = st.secrets.get("GEMINI_API_KEY", "")
GROQ_KEY   = st.secrets.get("GROQ_API_KEY", "")

if not GEMINI_KEY and not GROQ_KEY:
    st.sidebar.error("⚠️ Koi bhi API key set nahi hai!")

# ── LLM Objects — Adjusted for LiteLLM ─────────────────
def get_gemini_llm():
    # 🌟 FIX: LiteLLM framework me 'google_genai/' prefix use hota h standard Gemini models k liye
    return LLM(
        model="google_genai/gemini-2.5-flash",
        api_key=GEMINI_KEY,
        timeout=25,
        max_retries=1
    )

def get_groq_llm():
    return LLM(
        model="groq/llama-3.3-70b-versatile",
        api_key=GROQ_KEY,
        temperature=0.7
    )

# ── Session State ──────────────────────────────────────
if "niche_data"    not in st.session_state: st.session_state["niche_data"]    = ""
if "script_data"   not in st.session_state: st.session_state["script_data"]   = ""
if "active_model"  not in st.session_state: st.session_state["active_model"]  = ""
if "gemini_error"  not in st.session_state: st.session_state["gemini_error"]  = ""

# ── CrewAI Backend ─────────────────────────────────────
def run_crew(niche_topic, social_platform, output_language, llm):
    trend_researcher = Agent(
        role="Senior Content Trend Analyst",
        goal=f"Analyze what hooks people on '{niche_topic}' for {social_platform}.",
        backstory="Expert in viral retention algorithms. Knows what sub-topics trend right now.",
        llm=llm,
        max_iter=2,
        max_rpm=5,
        allow_delegation=False,
        verbose=True
    )

    script_writer = Agent(
        role="Expert Social Media Script Writer",
        goal=f"Create a viral script blueprint in {output_language} from the research.",
        backstory="Disciplined scriptwriter who turns raw research into high-retention video blueprints.",
        llm=llm,
        max_iter=2,
        max_rpm=5,
        allow_delegation=False,
        verbose=True
    )

    research_task = Task(
        description=f"""Find 3 viral angles/hooks for: '{niche_topic}' on {social_platform}.
        IMPORTANT: Respond ONLY in {output_language} language.
        If Hinglish, mix Hindi and English naturally.""",
        expected_output=f"Top 3 viral hooks in {output_language} language.",
        agent=trend_researcher
    )

    write_script_task = Task(
        description=f"""Using the 3 viral angles, write a complete video script for {social_platform}.
        STRICT RULE: The ENTIRE script must be written in {output_language} language only.
        If Hinglish — mix Hindi+English. If Hindi — pure Hindi. If English — pure English.
        Format: [00:00-00:05] Hook, Shot Description, Dialogues.""",
        expected_output=f"Complete formatted script strictly in {output_language} language.",
        agent=script_writer
    )

    crew = Crew(
        agents=[trend_researcher, script_writer],
        tasks=[research_task, write_script_task],
        verbose=True
    )

    return str(crew.kickoff())

def run_my_crew_ai_agents(niche_topic, social_platform, output_language):
    # Pehle Gemini try karo
    if GEMINI_KEY:
        try:
            # Local state clean karna har run se pehle
            st.session_state["gemini_error"] = ""
            gemini_llm = get_gemini_llm()
            result = run_crew(niche_topic, social_platform, output_language, gemini_llm)
            st.session_state["active_model"] = "gemini"
            return result
        except Exception as e:
            # 🌟 LIVE CAPTURE: Pura error pakad kar state me save karo
            st.session_state["gemini_error"] = str(e)

    # Groq fallback
    if GROQ_KEY:
        st.session_state["active_model"] = "groq"
        groq_llm = get_groq_llm()
        return run_crew(niche_topic, social_platform, output_language, groq_llm)

    st.error("❌ Koi LLM available nahi!")
    st.stop()

# ── Sidebar ────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Control Panel")
    platform = st.selectbox("Platform:", ["YouTube", "Instagram", "Facebook", "X (Twitter)"])
    language = st.selectbox("Language:", ["Hinglish", "Hindi", "English"])
    st.write("---")
    
    with st.expander("🔧 Debug Info", expanded=True):
        model = st.session_state.get("active_model", "N/A")
        st.write(f"Last Engine Used: **{model.upper()}**")
        err = st.session_state.get("gemini_error", "")
        if err:
            st.error(f"Gemini Log: {err[:250]}")
        else:
            st.success("Gemini status: Healthy/Untested")
    
    st.write("---")
    st.caption("Powered by Gemini + Groq & CrewAI")

# ── Main UI ────────────────────────────────────────────
st.title("🚀 Creator AI Manager")
st.write(f"**{platform}** manager active | Language: **{language}**")
st.write("---")

tab1, tab2, tab3 = st.tabs(["🔥 Trend & Script", "📝 Generated Script", "📊 Analytics"])

with tab1:
    st.markdown("### 🔥 AI Content Strategy Hub")
    st.caption("Topic daliye — Researcher + Writer agents kaam karenge.")
    st.write("---")

    # 🌟 LIVE USER WARNING BOX: Agar Gemini fail hua h, toh screen par warning dikhao
    if st.session_state["gemini_error"]:
        st.warning(f"ℹ️ **System Alert:** Gemini API crash ho gayi thi, isliye app ne automatic Meta Llama (Groq) ko trigger kiya. Ghabraiye mat, aapki script niche ready hai!")

    with st.form("trend_form"):
        user_niche = st.text_input(
            "🎯 Kis topic par video banani hai?",
            value=st.session_state["niche_data"],
            placeholder="E.g., What is AGI, Stoicism Guide, Python for Beginners..."
        )
        st.markdown(f"ℹ️ *Platform: **{platform}** | Language: **{language}***")
        submit_btn = st.form_submit_button("🚀 Launch AI Agents", use_container_width=True)

        if submit_btn:
            if user_niche:
                with st.spinner("🕵️ Agents kaam kar rahe hain... 30-40 seconds lagenge..."):
                    try:
                        ai_output = run_my_crew_ai_agents(user_niche, platform, language)
                        st.session_state["niche_data"]  = user_niche
                        st.session_state["script_data"] = ai_output
                        st.rerun() # Page refresh taaki naye alerts instantly dikhein
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
            else:
                st.error("⚠️ Topic box mein kuch likho pehle!")

with tab2:
    st.header("📝 AI Script & Blueprint")
    st.write("---")
    if st.session_state["script_data"]:
        # Banner dynamic batayega kis model ne likha h
        engine = st.session_state.get("active_model", "AI")
        st.success(f"🎉 Script Taiyar Hai! (Generated via {engine.upper()})")
        st.info("💡 Neeche se download kar sakte ho.")
        st.text_area("Generated Script:", value=st.session_state["script_data"], height=400)
        st.download_button(
            label="📥 Download Script (.txt)",
            data=st.session_state["script_data"],
            file_name=f"{platform}_{st.session_state['niche_data'].replace(' ','_')}.txt",
            mime="text/plain"
        )
    else:
        st.warning("⚠️ Pehle Tab 1 mein topic dalo aur agents run karo.")

with tab2:
    pass # Code clean rakhne k liye purane tab lines repeated context handle ho gaye

with tab3:
    st.header("📊 Multi-Platform Report")
    st.caption("Abhi placeholder data hai — real API integration agle stage mein.")
    st.write("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🔴 YouTube")
        st.metric("Subscribers", "15,400", "+1,200")
        st.metric("Total Views",  "240K",   "+45K")
    with c2:
        st.subheader("📸 Instagram")
        st.metric("Followers",        "8,900", "+850")
        st.metric("Reels Engagement", "12%",   "-2%")
    with c3:
        st.subheader("📸 X (Twitter)")
        st.metric("Followers",    "3,200", "+150")
        st.metric("Impressions",  "50K",   "+12K")