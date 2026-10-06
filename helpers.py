from docx import Document
from docx.shared import RGBColor, Pt
import io
import re

def parse_blueprint_metadata(raw_text):
    """
    AI text se metadata extract karne ka fail-proof regex parser.
    """
    parsed_data = {
        "yt_title": "",
        "yt_desc": "",
        "tw_thread": "",
        "ig_caption": "",
        "li_post": "",
        "hooks": []
    }
    
    if not raw_text:
        return parsed_data

    # 1. Extract Hooks (Tumhare app.py logic ko support karne ke liye)
    extracted_hooks = re.findall(r'(?:Hook|Retention):\s*"?([^"\n]+)"?', raw_text, re.IGNORECASE)
    parsed_data["hooks"] = [h.strip() for h in extracted_hooks if h.strip()]

    # 2. Extract YouTube Title (Bohot flexible rakha hai)
    yt_title_match = re.search(r'(?:YouTube Title|Title):\s*(.*?)(?=\n|$)', raw_text, re.IGNORECASE)
    if yt_title_match:
        # Faltu brackets aur quotes hata do
        clean_title = yt_title_match.group(1).replace("[YOUTUBE SHORTS TITLE]", "").replace('"', '').replace('[', '').replace(']', '').strip()
        parsed_data["yt_title"] = clean_title

    # 3. Extract YouTube Description
    yt_desc_match = re.search(r'(?:YouTube Description|Description):\s*(.*?)(?:\[?TWITTER|\[?INSTA|\[?LINKEDIN|\[?X THREAD|$)', raw_text, re.IGNORECASE | re.DOTALL)
    if yt_desc_match:
        # Faltu tags (single ya double brackets) aur extra characters ko clean kar dega
        clean_desc = yt_desc_match.group(1).replace("[YOUTUBE SHORTS DESCRIPTION]", "").replace("[[YOUTUBE SHORTS DESCRIPTION]", "")
        
        # Agar string ke aage-peeche koi akele brackets '[' ya ']' bach gaye hain, toh unhe strip kar dega
        clean_desc = clean_desc.strip('[]').strip()
        
        parsed_data["yt_desc"] = clean_desc

    # 4. Extract Twitter/X Thread (Sabse important)
    # Yeh dekhega ki "TWITTER" ya "X THREAD" kahan likha hai, aur wahan se lekar agle section tak sab utha lega
    tw_match = re.search(r'(?:\[?TWITTER.*?THREAD.*?\]?)(.*?)(?:\[?INSTAGRAM|\[?LINKEDIN|\[?YOUTUBE|$)', raw_text, re.IGNORECASE | re.DOTALL)
    if tw_match:
        thread_content = tw_match.group(1).strip()
        # Agar start mein koi faltu dash ya space hai toh hata do
        parsed_data["tw_thread"] = thread_content.lstrip('-').strip()

    # 5. Extract Instagram/Facebook Caption
    ig_match = re.search(r'(?:\[?INSTA.*?CAPTION.*?\]?)(.*?)(?:\[?LINKEDIN|\[?TWITTER|\[?YOUTUBE|$)', raw_text, re.IGNORECASE | re.DOTALL)
    if ig_match:
        parsed_data["ig_caption"] = ig_match.group(1).strip()

    # 6. Extract LinkedIn Post
    li_match = re.search(r'(?:\[?LINKEDIN.*?POST.*?\]?)(.*?)(?:\[?INSTAGRAM|\[?TWITTER|\[?YOUTUBE|$)', raw_text, re.IGNORECASE | re.DOTALL)
    if li_match:
        parsed_data["li_post"] = li_match.group(1).strip()

    return parsed_data

def create_word_doc(final_output, platform, topic_name):
    doc = Document()
    
    # Professional Blue Color Define kiya
    blue_color = RGBColor(0, 112, 192) 
    
    # POINT 1: Sleek & Simple Header (No garbage prompt rules)
    main_heading = doc.add_heading(f"🎬 Creator OS Blueprint: {topic_name}", level=1)
    
    # POINT 2: Trend Research ko Exclude karna
    parts = final_output.split("### ")
    script_text, social_text = "", ""
    
    for part in parts:
        if "PREMIUM AUDIO/VISUAL" in part:
            script_text = part.replace("🎬 PREMIUM AUDIO/VISUAL RETENTION SCRIPT", "").strip()
        elif "DISTRIBUTION MICRO-ASSETS" in part:
            social_text = part.replace("📱 DISTRIBUTION MICRO-ASSETS PACKAGE", "").strip()

    # POINT 3: Script & Metadata Color Formatting (Blue & Bold for Headings, Black for Content)
    
    # --- SCRIPT PARSING ---
    if script_text:
        doc.add_heading("Premium Video Script", level=2)
        
        # Table parsing logic (Basic split by lines and pipes)
        lines = script_text.split('\n')
        for line in lines:
            if "|" in line and "---" not in line and "Timestamp" not in line:
                cols = [c.strip() for c in line.split("|") if c.strip()]
                if len(cols) >= 3:
                    p = doc.add_paragraph()
                    
                    # Timestamp (Bold & Blue)
                    ts_run = p.add_run(f"[{cols[0]}] ")
                    ts_run.bold = True
                    ts_run.font.color.rgb = blue_color
                    
                    # Visuals (Bold & Blue)
                    vis_run = p.add_run(f"Visuals: {cols[1]} \n")
                    vis_run.bold = True
                    vis_run.font.color.rgb = blue_color
                    
                    # Audio (Normal & Black)
                    aud_run = p.add_run(f"Audio: {cols[2]}")
                    aud_run.bold = False
                    
    # --- SOCIAL MEDIA METADATA PARSING ---
    if social_text:
        doc.add_heading("Social Media Assets", level=2)
        
        lines = social_text.split('\n')
        
        # Keywords jo Blue & Bold honge
        blue_headers = [
            "Title:", "Description:", "Keywords:", "Instagram Caption:", 
            "LinkedIn Post:", "Twitter Thread:", "[Option 1]", "[Option 2]", "[Option 3]", "TL;DR:"
        ]
        
        for line in lines:
            if not line.strip():
                continue
                
            p = doc.add_paragraph()
            matched_header = None
            
            # Check karna agar line me koi heading hai
            for header in blue_headers:
                if line.startswith(header):
                    matched_header = header
                    break
            
            if matched_header:
                # Heading ko Blue aur Bold karna
                h_run = p.add_run(matched_header)
                h_run.bold = True
                h_run.font.color.rgb = blue_color
                
                # Bacha hua text Black aur Normal
                content_text = line.replace(matched_header, "", 1)
                if content_text:
                    c_run = p.add_run(content_text)
                    c_run.bold = False
            else:
                # Agar normal text/hashtags hai toh Black
                c_run = p.add_run(line)
                c_run.bold = False

    # Document save karke byte stream me return karna
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()