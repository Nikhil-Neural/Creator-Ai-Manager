# ai_engine.py
import streamlit as st
import json
import requests
import time
from crewai import Agent, Task, Crew, LLM

# ── SINGLE PAID API KEY SETUP ──
GEMINI_KEY = st.secrets.get("GEMINI_API_KEY", "")
SERPER_KEY = st.secrets.get("SERPER_API_KEY", "")

from crewai_tools import SerperDevTool
search_tool = SerperDevTool(api_key=SERPER_KEY) if SERPER_KEY else None

if not GEMINI_KEY:
    st.sidebar.error("⚠️ Control Panel Matrix Empty: Gemini API Key Missing!")


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

def run_my_crew_ai_agents(niche_topic, social_platform, script_language, meta_langs, video_duration, app_mode, user_pasted_script, selected_bundle_options, selected_hook, selected_body, selected_cta):
    # ⏱️ SHORTS MATHS: Direct seconds, aur approx 2.5 words per second (150 words/min)
    target_seconds = int(video_duration)
    target_words = int((video_duration / 60) * 140)
    
    # ── PRODUCTION LLM ENGINE ──
    production_llm = LLM(
        model="gemini/gemini-3.8-flash", 
        api_key=GEMINI_KEY, 
        temperature=0.6, 
        timeout=60
    )

    trend_analyst = Agent(
        role="Content Research & Verification Specialist",
        goal=f"Extract high-signal facts and credible retention triggers for '{niche_topic}' on {social_platform}. Accuracy > Virality.",
        backstory="""You are a top-tier researcher. You prioritize primary sources and factual accuracy over extreme clickbait. 
        NEVER invent statistics, dates, percentages, or product capabilities. 
        Distinguish between verified facts, reasonable inferences, and speculation.
        Do not pass unsupported claims, invented benchmarks, or unverified authority statements into downstream context as facts. 
        CRITICAL: You must explicitly label your findings before passing them downstream. Use these exact labels:
        [VERIFIED]: For hard facts.
        [INFERENCE]: For logical deductions.
        [UNVERIFIED / DO NOT USE AS FACT]: For uncertain or unsupported claims.""",
        llm=production_llm, max_iter=1, max_rpm=10, verbose=True, allow_delegation=False, memory=False
    )

    # 🔥 SCRIPT WRITER UPDATED WITH CONTEXT BOUNDING
    script_writer = Agent(
        role="Premium Video Scriptwriter & QA Auditor",
        goal="Write a high-retention, nuanced, and factually bulletproof video script.",
        backstory="""You are an elite video scriptwriter. 
        CRITICAL QA RULES YOU MUST STRICTLY FOLLOW:
        1. NO UNSUPPORTED NUMBERS: Never invent numeric benchmarks (e.g., '70% retention', '3x growth') unless explicitly verified in the research context provided to you.
        2. AUTHORITY CHECKS: Never attribute a claim to company leads, engineers, or official sources unless a specific source is present in the research context. If no source is available, either omit the attribution or use only a claim that is explicitly supported by the [VERIFIED] research findings.
        3. NO DETERMINISTIC ALGORITHM CLAIMS: Never say "the algorithm freezes impressions." Use the nuanced reality: "this can weaken organic performance."
        4. AVOID BINARY CONCLUSIONS: Do not force absolute "X is bad, Y is good" narratives. Find the nuanced insight (e.g., "Frequency isn't the enemy, sacrificing quality is").
        5. EVIDENCE BOUNDARY: Treat [VERIFIED] findings as factual source material. Treat [INFERENCE] only as interpretation, never as established fact. Never use [UNVERIFIED / DO NOT USE AS FACT] content in the script.
        Avoid repetitive transitions like 'Look,' or 'Honestly,'. The framework serves the story.""",
        llm=production_llm, max_iter=1, max_rpm=10, verbose=True, allow_delegation=False, memory=False
    )

    copy_maestro = Agent(
        role="Platform-Native Conversion Copywriter",
        goal="Convert concepts into high-signal, platform-optimized social media assets without fake urgency or repetition.",
        backstory="""You are a conversion-aware social media strategist. 
        CRITICAL QA RULES:
        1. Never invent statistics, unsupported numbers, or fake authority claims.
        2. DO NOT repeat the exact same thesis across all platforms. Adapt the core insight dynamically:
           - YouTube: Focus on Search/Curiosity.
           - Instagram: Focus on Relatable Creator/User Pain.
           - LinkedIn: Focus on Productivity/Business Insight (No corporate jargon).
           - Twitter/X: Focus on Strong Opinion and Discussion.
        3. Never use cheap rage-bait or absolute deterministic claims.""",
        llm=production_llm, max_iter=1, max_rpm=10, verbose=True, allow_delegation=False, memory=False
    )

    tasks_pipeline = []
    live_scanned_context = ""
    if niche_topic:
        raw_trends = fetch_live_trends(niche_topic)
        if raw_trends:
            live_scanned_context = "\n".join([f"- Title: {item['title']} (URL: {item['url']})" for item in raw_trends])

    # 1. UPGRADED RESEARCH TASK (The Fact-Check Gatekeeper)
    research_task = Task(
        description=f"""Analyze topic: '{niche_topic}' on {social_platform}.
        Context:\n{live_scanned_context}
        
        CRITICAL FACT-CHECK RULE: You are the gatekeeper. Verify all company/product attributions before writing. Example: Project Astra = Google DeepMind (NOT OpenAI). If the user's premise contains a factual error, YOU MUST SILENTLY CORRECT IT. Never mix up competing companies in hooks or claims.
        
        Identify 3 COMPLETELY DIFFERENT breakout hooks (1 Negative/Fear, 1 Story/Curiosity, and 1 Direct Benefit) and 3 retention nodes under 150 words total. Do not repeat sentence structures. No titles/urls.""",
        expected_output="Clean bullet points analysis matrix data with factually verified and corrected premise.",
        agent=trend_analyst
    )
    tasks_pipeline.append(research_task)

    script_task = None
    if any("Script" in opt for opt in selected_bundle_options):
        script_prompt = f"Write a full video script for '{niche_topic}' around {target_words} words ({target_seconds} seconds)."
        if app_mode == "✍️ Repurpose My Script Mode":
            script_prompt = f"Analyze and re-engineer raw script: '{user_pasted_script}'."
            
        # 2. UPGRADED SCRIPT TASK (Emotion Tones, 8-Word Hook, MM:SS fix)
        script_task = Task(
            description=f"""{script_prompt} Target language: '{script_language}'.
            
            🎯 STRICT FRAMEWORK EXECUTION:
            - Hook Style: {selected_hook}
            - Body Structure: {selected_body}
            - CTA Mechanism: {selected_cta}
            
            HOOK RULE: The first 3 seconds [00:00-00:03] MUST be UNDER 8 WORDS. Make it a provocative question or shocking statement only.
            ENDING RULE: The last 5 seconds MUST use a strong psychological ending. NEVER end with a generic "what do you think?".
            TIME RULE: Time markers must follow standard MM:SS format (e.g., 00:59, never 00:60).
            
            ANTI-ROBOT RULES:
            1. RHYTHM VARIATION: Mix short punchy sentences (3-5 words) with longer explanatory ones.
            2. VISUAL-VERBAL SYNC: Point to visuals organically (e.g., "See this?").
            
            CRITICAL CRITERIA: You MUST use this exact table framework layout including [Emotion Tone] for editing:
            | Timestamp | Visuals & [Emotion Tone] | Audio ({script_language}) |
            | :--- | :--- | :--- |
            """,
            expected_output="Perfect Markdown 3-column table framework script avoiding banned AI words, factually correct, and strictly following the selected frameworks.",
            agent=script_writer, context=[research_task]
        )
        tasks_pipeline.append(script_task)

    distribution_task = None
    dist_requirements = []
    # 🧠 SMART UI CHECKS (Checking individual buttons by new names)
    include_youtube = any("YouTube SEO" in opt for opt in selected_bundle_options)
    include_linkedin = any("LinkedIn" in opt for opt in selected_bundle_options)
    include_twitter = any("X & Threads" in opt for opt in selected_bundle_options)
    include_ig_fb = any("Insta & FB" in opt for opt in selected_bundle_options)
        
    # Appending only what user requested
    if include_youtube: dist_requirements.append("- 1 Optimized YouTube Title & Description")
    if include_ig_fb: dist_requirements.append("- 3 short Instagram/Facebook captions & tags")
    if include_linkedin: dist_requirements.append("- 1 High-Converting LinkedIn Post")
    if include_twitter: dist_requirements.append("- 1 Viral Thread format suitable for X (Twitter) and Meta Threads")
    
    if dist_requirements:
        desc_instruction = ""
        yt_title_instruction = ""
        ig_fb_instruction = ""
        linkedin_instruction = ""
        twitter_instruction = ""
        parser_format = ""
            
        # 📺 YOUTUBE: Factual SEO (No Keyword Stuffing)
        if include_youtube:
            yt_title_instruction = """[YOUTUBE SHORTS TITLE]
            Constraint: STRICTLY UNDER 60 CHARACTERS.
            CRITICAL: Verify all company names are correct before writing.
            Structure: Pattern interrupt + core keyword + power word. 
            Do NOT use "officially dead" or "game over" unless factually verified. No misleading attributions."""
            
            desc_instruction = """[YOUTUBE SHORTS DESCRIPTION]
            Write 2-4 natural sentences. 
            Naturally weave 3-4 highly relevant SEO search terms directly into the flow of the sentences. 
            DO NOT explicitly write the word 'Keywords:'. Include a natural CTA and 2-3 niche hashtags."""
                
            parser_format += f"\nTitle: [{yt_title_instruction}]\nDescription: [{desc_instruction}]"
            
        # 📸 META (IG/FB): 3 Distinct Angles (No Insulting Language)
        if include_ig_fb:
            ig_fb_instruction = f"""[INSTAGRAM/FACEBOOK REELS CAPTION]
            Target Language: STRICTLY {meta_langs.get('ig', 'English')}
            Generate 3 GENUINELY DIFFERENT caption angles:
            [Option 1] - News Angle: What happened and why it matters.
            [Option 2] - Insight Angle: What does this mean for users?
            [Option 3] - Debate Angle: What could this change in the future?
            Rules: Strong first line (under 100 chars), natural spoken language. NO insults, NO fake stats, NO cheap rage-bait. End with 3-5 relevant hashtags."""
            
            parser_format += f"\nInstagram Caption:\n[{ig_fb_instruction}]"
    
        # 💼 LINKEDIN: Human Professional (No Corporate Jargon)
        if include_linkedin:
            linkedin_instruction = """[LINKEDIN POST FRAMEWORK]
            Role: A modern, high-level creator sharing insights.
            Constraints: Use conversational but professional language. BANNED: Corporate jargon like 'ROI', 'synergy', 'asymmetric', 'terminal phase', 'spatial execution'.
            Structure: 1. Strong observation -> 2. Verified fact -> 3. Why it matters -> 4. Nuanced insight -> 5. Question.
            Never invent business statistics. Never mention a link in the comments unless a real resource is provided."""
                
            parser_format += f"\nLinkedIn Post:\n[{linkedin_instruction}]"
    
        # 🧵 TWITTER: Storytelling & Strict Length
        if include_twitter:
            twitter_instruction = """[TWITTER/X VIRAL THREAD FRAMEWORK]
            Constraints: 5 to 7 tweets total. HARD RULE: Each tweet MUST be under 240 characters (keep a buffer). NO HASHTAGS. End each tweet with a progress tracker (e.g., 1/6).
            Structure: Tell a story. 1: Hook+News, 2: Context, 3: Core capability/fact, 4: Why it matters, 5: TL;DR or Implication, 6: Conclusion/Question.
            Every post must add NEW information. Do not force a CTA into every thread."""
                
            parser_format += f"\nTwitter Thread:\n[{twitter_instruction}]"
        # ⚡ THE INVISIBLE SCRIPT INJECTION BRIDGE ⚡
        dist_context_list = [research_task]
        if script_task:
            dist_context_list.append(script_task)
            smart_injection_logic = "IMPORTANT: Deeply analyze the final video script generated by the 'Humanized Script Writer' in your context. Match your metadata's tone, hooks, and context perfectly to that exact script."
        elif user_pasted_script.strip(): 
            # Repurpose Mode (Jab user ne apna text diya ho)
            smart_injection_logic = f"IMPORTANT: Deeply analyze the following script provided by the user. Match your metadata's tone, hooks, and context perfectly to this script:\n\n[USER SCRIPT BEGIN]\n{user_pasted_script}\n[USER SCRIPT END]"
        else:
            # Metadata Only Mode (Na AI ki script hai, na user ki)
            smart_injection_logic = f"IMPORTANT: You are generating standalone social media metadata based on the trend research and the core topic: '{niche_topic}'. THERE IS NO SCRIPT PROVIDED. Focus 100% on making the metadata hyper-viral, factually accurate, and strictly aligned with the provided topic context."
    
        distribution_task = Task(
            description=f"""Act as a Top-Tier Metadata & Copywriting Specialist. 
                
            {smart_injection_logic}
                
            Generate a package based on the script or topic context for the requested platforms:
            {chr(10).join(dist_requirements)}
                
            CRITICAL CONSTRAINTS FOR OUTPUT (FOLLOW STRICTLY):
                
            1. 🛑 LANGUAGE RULE: 
                - If '{script_language}' is 'Hinglish': Use ONLY the English alphabet (Latin script).
                - If 'Hindi': Use ONLY the Devanagari script (हिंदी).
                - If 'English': Use pure English.
                   
            2. 🤖 API PARSER FORMAT (MANDATORY FORMATTING):
                You MUST output EXACTLY in this format with these exact section headings for the requested items. Do not deviate.
                {parser_format}
            """,
            expected_output="Compiled social media assets tier list package with highly engineered, logically structured, SEO-optimized metadata and professional social copy.",
            agent=copy_maestro,
            context=dist_context_list # 👈 YEH FIX ZAROORI THA TAAKI AI SCRIPT READ KAR SAKE
        )
        tasks_pipeline.append(distribution_task)
    
    master_crew = Crew(agents=[trend_analyst, script_writer, copy_maestro], tasks=tasks_pipeline, verbose=True, process='sequential')
        
    try:
        master_crew.kickoff()
    except Exception as crew_error:
        print(f"🚨 [ENGINE ERROR] Pipeline failed: {crew_error}")
        return f"Error generating content. Please check logs. Details: {crew_error}"
        
    compiled_final_output = "### 🕵️ EXPERT TREND RESEARCH ANALYSIS\n" + str(research_task.output.raw if hasattr(research_task, 'output') and research_task.output else "") + "\n\n"
    if script_task and script_task.output:
        compiled_final_output += "### 🎬 PREMIUM AUDIO/VISUAL RETENTION SCRIPT\n" + str(script_task.output.raw) + "\n\n"
    if distribution_task and distribution_task.output:
        compiled_final_output += "### 📱 DISTRIBUTION MICRO-ASSETS PACKAGE\n" + str(distribution_task.output.raw) + "\n\n"     
    
    return compiled_final_output