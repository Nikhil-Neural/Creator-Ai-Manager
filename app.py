# ── Groq Cache Fix (SABSE PEHLE) ──────────────────────
# ✅ LAGAO YE:
try:
    from crewai.llms import cache as _cache
    _cache.mark_cache_breakpoint = lambda msg: msg
except ImportError:
    pass  # Naye version mein fix already built-in hai
import streamlit as st
import os
from crewai import Agent, Task, Crew, LLM

st.set_page_config(page_title="Creator AI OS", layout="wide")

# ── API Keys ───────────────────────────────────────────
GEMINI_KEY = st.secrets.get("GEMINI_API_KEY", "")
GROQ_KEY   = st.secrets.get("GROQ_API_KEY", "")

if not GEMINI_KEY and not GROQ_KEY:
    st.sidebar.error("⚠️ Koi bhi API key set nahi hai!")

# ── Smart LLM Loader: Gemini → Groq Fallback ──────────
def get_llm():
    """Pehle Gemini try karo, fail ho toh Groq use karo."""
    if GEMINI_KEY:
        try:
            llm = LLM(
                model="gemini/gemini-2.5-flash",
                api_key=GEMINI_KEY,
                timeout=25,
                max_retries=1
            )
            # Quick test — agar initialize hua toh theek hai
            st.sidebar.success("🟢 Gemini Active")
            return llm
        except Exception:
            st.sidebar.warning("🟡 Gemini failed, Groq pe switch ho raha hai...")

    if GROQ_KEY:
        st.sidebar.info("🔵 Groq Active (Fallback)")
        return LLM(
            model="groq/llama-3.3-70b-versatile",
            api_key=GROQ_KEY,
            temperature=0.7
        )

    st.error("❌ Koi LLM available nahi! API keys check karo.")
    st.stop()

# ── CrewAI Backend ─────────────────────────────────────
def run_my_crew_ai_agents(niche_topic, social_platform, output_language):
    my_llm = get_llm()

    trend_researcher = Agent(
        role="Senior Content Trend Analyst",
        goal=f"Analyze what hooks people on '{niche_topic}' for {social_platform}.",
        backstory="Expert in viral retention algorithms. Knows what sub-topics trend right now.",
        llm=my_llm,
        max_iter=2,
        max_rpm=5,
        allow_delegation=False,
        verbose=True
    )

    script_writer = Agent(
        role="Expert Social Media Script Writer",
        goal=f"Create a viral script blueprint in {output_language} from the research.",
        backstory="Disciplined scriptwriter who turns raw research into high-retention video blueprints.",
        llm=my_llm,
        max_iter=2,
        max_rpm=5,
        allow_delegation=False,
        verbose=True
    )

    research_task = Task(
        description=f"Find 3 viral angles/hooks for: '{niche_topic}' on {social_platform}.",
        expected_output="Top 3 viral sub-themes or hooks for this content niche.",
        agent=trend_researcher
    )

    write_script_task = Task(
        description=f"Using the 3 viral angles, write a complete video script for {social_platform} in {output_language}.",
        expected_output="Formatted script with timing blocks [00:00-00:05], hook, shot description, dialogues.",
        agent=script_writer
    )

    crew = Crew(
        agents=[trend_researcher, script_writer],
        tasks=[research_task, write_script_task],
        verbose=True
    )

    return str(crew.kickoff())

# ── Session State ──────────────────────────────────────
if "niche_data"   not in st.session_state: st.session_state["niche_data"]   = ""
if "script_data"  not in st.session_state: st.session_state["script_data"]  = ""
if "active_model" not in st.session_state: st.session_state["active_model"] = ""

# ── Sidebar ────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Control Panel")
    platform = st.selectbox("Platform:", ["YouTube", "Instagram", "Facebook", "X (Twitter)"])
    language = st.selectbox("Language:", ["Hinglish", "Hindi", "English"])
    st.write("---")
    st.caption("Powered by Gemini + Groq & CrewAI")

# ── Main UI ────────────────────────────────────────────
st.title("🚀 Creator AI Manager")
st.write(f"**{platform}** manager active | Language: **{language}**")
st.write("---")

tab1, tab2, tab3 = st.tabs(["🔥 Trend & Script", "📝 Generated Script", "📊 Analytics"])

# ── Tab 1 ──────────────────────────────────────────────
with tab1:
    st.markdown("### 🔥 AI Content Strategy Hub")
    st.caption("Topic daliye — Researcher + Writer agents kaam karenge.")
    st.write("---")

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
                with st.spinner("🕵️ Agents kaam kar rahe hain... 20-30 seconds lagenge..."):
                    try:
                        ai_output = run_my_crew_ai_agents(user_niche, platform, language)
                        st.session_state["niche_data"]  = user_niche
                        st.session_state["script_data"] = ai_output
                        st.success("✅ Done! 'Generated Script' tab mein dekho.")
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
            else:
                st.error("⚠️ Topic box mein kuch likho pehle!")

# ── Tab 2 ──────────────────────────────────────────────
with tab2:
    st.header("📝 AI Script & Blueprint")
    st.write("---")
    if st.session_state["script_data"]:
        st.success("🎉 Script Taiyar Hai!")
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

# ── Tab 3 ──────────────────────────────────────────────
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
        st.subheader("🐦 X (Twitter)")
        st.metric("Followers",    "3,200", "+150")
        st.metric("Impressions",  "50K",   "+12K")