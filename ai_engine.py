# ai_engine.py
import streamlit as st
import json
import requests
import time
from crewai import Agent, Task, Crew, LLM

# ── API Keys & TRIPLE-LAYER FAILPROOF LLM RESOLVER MATRIX ──
G_KEY_1 = st.secrets.get("GEMINI_API_KEY_1", "")
G_KEY_2 = st.secrets.get("GEMINI_API_KEY_2", "")
GR_KEY_1 = st.secrets.get("GROQ_API_KEY_1", "")
GR_KEY_2 = st.secrets.get("GROQ_API_KEY_2", "")
S_KEY_1 = st.secrets.get("SERPER_API_KEY_1", "")
S_KEY_2 = st.secrets.get("SERPER_API_KEY_2", "")

GEMINI_KEY = G_KEY_1 if G_KEY_1 else st.secrets.get("GEMINI_API_KEY", "")
GROQ_KEY   = GR_KEY_1 if GR_KEY_1 else st.secrets.get("GROQ_API_KEY", "")
SERPER_KEY = S_KEY_1 if S_KEY_1 else st.secrets.get("SERPER_API_KEY", "")

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

def run_my_crew_ai_agents(niche_topic, social_platform, script_language, meta_langs, video_duration, app_mode, user_pasted_script, selected_bundle_options):    # ⏱️ SHORTS MATHS: Direct seconds, aur approx 2.5 words per second (150 words/min)
    target_seconds = int(video_duration)
    target_words = int((video_duration / 60) * 150)
    
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
        role="Viral Retention Strategist",
        goal=f"Extract extreme psychological hooks and viewer retention triggers for '{niche_topic}' on {social_platform}.",
        backstory="""You are a top-tier YouTube Shorts & Reels strategist who has analyzed 10,000+ viral videos. 
        You don't just look for 'topics', you look for 'Dopamine Hits', 'Curiosity Gaps', and 'Pattern Interrupts'. 
        You know exactly why a user stops scrolling in the first 3 seconds.""",
        llm=groq_cluster_llm, max_iter=1, max_rpm=5, verbose=True, allow_delegation=False, memory=False
    )

    script_writer = Agent(
        role="Humanized Script Writer",
        goal="Write a hyper-engaging, 2-column video script blueprint.",
        backstory="""You are a highly successful, 28-year-old content creator who has written 500+ viral scripts. 
        You talk like you're explaining a fascinating secret to a friend, not presenting in a boardroom. 
        You use casual, spoken-English transitions like 'Look,', 'Here's the thing,', 'Honestly,', 'The crazy part is...'.
        
        NEVER write like this (robotic): "Context windows play a crucial role in determining LLM performance."
        ALWAYS write like this (human): "Itni lambi memory honi chahiye AI ko ki purani baatein bhool na jaaye."
        
        BANNED WORDS: Delve, Unleash, Tapestry, In today's digital landscape, Buckle up, Crucial, Imperative, Furthermore, Moreover, In conclusion, Testament.""",
        llm=script_writing_llm, max_iter=1, max_rpm=5, verbose=True, allow_delegation=False, memory=False
    )

    copy_maestro = Agent(
        role="Direct-Response Micro Copywriter",
        goal="Convert concepts into highly aggressive, scroll-stopping social media assets.",
        backstory="""You are a ruthless social media manager known for driving massive engagement. 
        You use psychological triggers, extreme curiosity, and sharp sarcasm. 
        You NEVER use cringey emojis or robotic corporate speak like 'In today's fast-paced world'. 
        Your goal is to force the user to click '...more' or jump into the comments section.""",
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
            description=f"""{script_prompt} Target language: '{script_language}'.
            
            ANTI-ROBOT RULES:
            1. RHYTHM VARIATION: Mix short punchy sentences (3-5 words) with longer explanatory ones. Do not over-explain.
            2. VISUAL-VERBAL SYNC: Do not formally narrate the visuals. Point to them organically (e.g., "See this? It's not just a graphic...").
            
            CRITICAL CRITERIA: You MUST use this exact table framework layout:
            | Timestamp | Visuals | Audio ({script_language}) |
            | :--- | :--- | :--- |
            
            🌟 EXAMPLE SHOT-PROMPTING FORMAT:
            | [00:00-00:05] | Camera zooms in sharply | Kya tumhe pata hai AI kya sochta hai? |
            | [00:05-00:10] | Holographic flowchart expanding | Yeh simple hai. Lekin iska impact bahut bada hai. |
            """,
            expected_output="Perfect Markdown 3-column table framework script avoiding all banned AI words.",
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
            
        # 🧠 HYPER-ENGINEERED DYNAMIC SEO LOGIC (YOUTUBE)
        if include_youtube:
            yt_title_instruction = """[YOUTUBE SHORTS TITLE]
            Constraint: STRICTLY UNDER 60 CHARACTERS.
            Structure: Use extreme curiosity or a pattern interrupt. Include the core keyword naturally. End with a relevant emoji or a bracketed word like (Warning) or (Secret). NO HASHTAGS in the title."""
            desc_instruction = """[YOUTUBE SHORTS DESCRIPTION]
            Constraint: STRICTLY UNDER 60 WORDS.
            Structure MUST include: 
            1. A punchy hook line.
            2. A direct CTA.
            3. 'Keywords:' followed by 3-4 highly relevant SEO search terms (comma-separated).
            4. EXACTLY 3 niche hashtags.
            DO NOT generate long paragraphs, mini-blogs, or timestamps."""
                
            # YouTube ka format parser mein add ho gaya
            parser_format += f"""
                Title: [{yt_title_instruction}]
                Description: [{desc_instruction}]
                """
        # 🔥 THE HIGHLY ENGINEERED INSTA/FB PROMPT RESTORED
        if include_ig_fb:
            ig_fb_instruction = f"""[INSTAGRAM/FACEBOOK REELS CAPTION]
            Target Language: STRICTLY {meta_langs.get('ig', 'English')}
            Constraints: STRICTLY follow this 3-part framework:
            1. The Truncation Hook (Above the Fold): Only the first few words are visible. First line MUST be under 100 characters. End with an unresolved thought, curiosity, sarcasm, or a bold claim to force a '...more' click.
            2. The Context Drop: Leave a blank line, then write a 2-3 sentence punchy, highly engaging summary about the video.
            3. The 5-Tag Rule: End with EXACTLY 5 highly relevant SEO hashtags (Do not use generic tags)."""
            parser_format += f"\nInstagram Caption:\n[{ig_fb_instruction}]"
    
        # 🏢 HYPER-ENGINEERED B2B COPY LOGIC (LINKEDIN)
        if include_linkedin:
            linkedin_instruction = """[LINKEDIN POST FRAMEWORK]
            Role: B2B Authority & Tech Industry Leader.
            Constraints: Use short sentences (1 sentence = 1 line). Use high-level business vocabulary (e.g., ROI-driven, operational friction, scalable architecture).
            Structure MUST strictly follow:
            1. Pattern Interrupt Hook: First 2 lines must make a bold claim or share a hard data point. 
            2. The Cliffhanger: Leave a blank line after the 3rd sentence to force a '...see more' click.
            3. The Skimmable Meat: Use bullet points to deliver the core blueprint/value.
            4. The 'Aha!' Insight: Provide a contrarian or paradigm-shifting perspective near the end.
            5. Engagement CTA: Ask a thought-provoking question to drive comments. Explicitly state "Link is in the first comment" (Do not put the actual URL in the text)."""
                
            # LinkedIn ka format parser mein add ho gaya
            parser_format += f"""
                LinkedIn Post:
                [{linkedin_instruction}]
                """
    
        # 🧵 HYPER-ENGINEERED VIRAL LOGIC (TWITTER/X)
        if include_twitter:
            twitter_instruction = """[TWITTER/X VIRAL THREAD FRAMEWORK]
            Role: Tech/SaaS Thought Leader.
            Constraints: Exactly 5 to 7 tweets total. Max 280 characters per tweet. NO HASHTAGS. End each tweet with a progress tracker (e.g., 1/6, 2/6).
            Structure MUST strictly follow:
            - Tweet 1 (The Banger): Scroll-stopping massive claim. Suggest a sleek, dark-themed, ultra-detailed visual/graphic in brackets. End with thread emoji 🧵👇.
            - Tweet 2 (The Agitation): Hit the core pain point. Why should the reader care?
            - Tweet 3-5 (The Meat): One single idea per tweet. Use white space and bullet marks (•, ✅).
            - Penultimate Tweet (TL;DR): A quick bulleted summary of the thread.
            - Final Tweet (The Loop): CTA asking to Retweet the first tweet ♻️, follow for more breakdowns, and check the link in the reply."""
                
            # Twitter ka format parser mein add ho gaya
            parser_format += f"""
                Twitter Thread:
                [{twitter_instruction}]
                """
        # ⚡ THE INVISIBLE SCRIPT INJECTION BRIDGE ⚡
        dist_context_list = [research_task]
        if script_task:
            dist_context_list.append(script_task)
            smart_injection_logic = "IMPORTANT: Deeply analyze the final video script generated by the 'Humanized Script Writer' in your context. Match your metadata's tone, hooks, and context perfectly to that exact script."
        elif user_pasted_script.strip(): 
            # Repurpose Mode (Jab user ne apna text diya ho)
            smart_injection_logic = f"IMPORTANT: Deeply analyze the following script provided by the user. Match your metadata's tone, hooks, and context perfectly to this script:\n\n[USER SCRIPT BEGIN]\n{user_pasted_script}\n[USER SCRIPT END]"
        else:
            # 👈 NAYA: Metadata Only Mode (Na AI ki script hai, na user ki)
            smart_injection_logic = f"IMPORTANT: You are generating standalone social media metadata based on the trend research and the core topic: '{niche_topic}'. THERE IS NO SCRIPT PROVIDED. Focus 100% on making the metadata hyper-viral and strictly aligned with the provided topic context."
    
        distribution_task = Task(
            description=f"""Act as a Top-Tier Metadata & Copywriting Specialist. 
                
            {smart_injection_logic}
                
            Generate a package based on the script above for the requested platforms:
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
            expected_output="Compiled social media assets tier list package with highly engineered, dynamically scaled, SEO-optimized metadata and professional social copy.",
            agent=copy_maestro
        )
        tasks_pipeline.append(distribution_task)
    
    master_crew = Crew(agents=[trend_analyst, script_writer, copy_maestro], tasks=tasks_pipeline, verbose=True, process='sequential')
        
    # 🛡️ THE MID-AIR PARACHUTE SYSTEM
    try:
        master_crew.kickoff()
    except Exception as crew_error:
        print(f"🚨 [ENGINE CRASH] Primary LLM failed mid-generation: {crew_error}")
        print("🔄 Deploying GROQ Parachute Engine...")
            
        # 1. Force swap the failed agent's brain to Groq
        script_writer.llm = groq_cluster_llm
            
        # 2. Restart the Crew with the new engine
        master_crew = Crew(agents=[trend_analyst, script_writer, copy_maestro], tasks=tasks_pipeline, verbose=True, process='sequential')
        master_crew.kickoff()
        
    compiled_final_output = "### 🕵️ EXPERT TREND RESEARCH ANALYSIS\n" + str(research_task.output.raw if hasattr(research_task, 'output') and research_task.output else "") + "\n\n"
    if script_task and script_task.output:

        
        compiled_final_output += "### 🎬 PREMIUM AUDIO/VISUAL RETENTION SCRIPT\n" + str(script_task.output.raw) + "\n\n"
    if distribution_task and distribution_task.output:
        compiled_final_output += "### 📱 DISTRIBUTION MICRO-ASSETS PACKAGE\n" + str(distribution_task.output.raw) + "\n\n"     
    return compiled_final_output