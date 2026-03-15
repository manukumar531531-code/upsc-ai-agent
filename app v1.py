import streamlit as st
import time
import tempfile
import os
import io
import pypdf
import docx
from PIL import Image
from google import genai
from google.genai import types
from duckduckgo_search import DDGS
import requests
from bs4 import BeautifulSoup
import pandas as pd
import textwrap
from fpdf import FPDF
from PIL import ImageDraw
import asyncio
import edge_tts

def create_flashcard(text, index):
    """Draws a key point onto a digital flashcard image."""
    wrapper = textwrap.TextWrapper(width=50)
    lines = wrapper.wrap(text)
    
    # Create a nice wide index card shape (600x350)
    img = Image.new('RGB', (600, 350), color=(253, 253, 248)) # Off-white card color
    d = ImageDraw.Draw(img)
    
    # Draw a colored top border for style
    d.rectangle([0, 0, 600, 20], fill=(65, 105, 225)) 
    
    # Add Card Number
    d.text((20, 40), f"Key Point {index}", fill=(100, 100, 100))
    
    # Write the text lines
    y_text = 100
    for line in lines:
        d.text((40, y_text), line, fill=(10, 10, 10))
        y_text += 25
        
    bio = io.BytesIO()
    img.save(bio, format='PNG')
    return bio.getvalue()
# --- THE FILE EXPORT FACTORY ---
def create_audio(text, speed_multiplier):
    # Convert our speed multiplier (1.5x) into the percentage format the API requires ("+50%")
    rate_percentage = int((speed_multiplier - 1.0) * 100)
    rate_str = f"+{rate_percentage}%" if rate_percentage >= 0 else f"{rate_percentage}%"
    
    # Premium Neural Voice (Indian English context)
    voice = "en-IN-NeerjaNeural" 
    
    # Streamlit requires a fresh async loop for background processing
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    communicate = edge_tts.Communicate(text, voice, rate=rate_str)
    
    audio_data = bytearray()
    
    async def get_audio():
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data.extend(chunk["data"])
                
    loop.run_until_complete(get_audio())
    return bytes(audio_data)
    
def create_pdf(text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    # FPDF struggles with emojis, so we safely encode the text to standard characters
    safe_text = text.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 7, txt=safe_text)
    return bytes(pdf.output())

def create_docx(text):
    doc = docx.Document()
    doc.add_paragraph(text)
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

def create_excel(text):
    # Splits the text by new lines so it looks clean in Excel rows
    df = pd.DataFrame({"Study Notes": text.split('\n')})
    bio = io.BytesIO()
    df.to_excel(bio, index=False, engine='openpyxl')
    return bio.getvalue()

def create_image(text):
    # Wraps the text so it doesn't run off the screen
    wrapper = textwrap.TextWrapper(width=80)
    lines = wrapper.wrap(text)
    height = len(lines) * 20 + 60
    img = Image.new('RGB', (800, max(height, 200)), color=(240, 242, 246))
    d = ImageDraw.Draw(img)
    
    y_text = 30
    for line in lines:
        d.text((30, y_text), line, fill=(10, 10, 10))
        y_text += 20
        
    bio = io.BytesIO()
    img.save(bio, format='PNG')
    return bio.getvalue()

# --- 1. PAGE SETUP & CSS ---
st.set_page_config(page_title="Advanced AI Agent", page_icon="✨", layout="centered")

# Custom CSS to make the buttons look more like the rounded Google UI
st.markdown("""
<style>
    div[data-testid="stButton"] button {
        border-radius: 20px;
        text-align: left;
        padding: 10px 20px;
    }
</style>
""", unsafe_allow_html=True)

try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = "PASTE_YOUR_API_KEY_HERE_TEMPORARILY"

client = genai.Client(api_key=api_key)

# --- (Keep your Tools here: search_current_affairs, read_webpage) ---
# --- THE UPGRADED SEARCH TOOL ---
def search_current_affairs(topic: str) -> str:
    """Searches the internet for the absolute latest data and extracts exact URLs."""
    try:
        # We use .text() instead of .news() to get a wider range of verified facts
        results = DDGS().text(topic, max_results=3, timelimit='w') # 'w' limits to the past week!
        search_data = ""
        for r in results:
            # We explicitly grab the 'href' to get the exact clickable URL
            search_data += f"Title: {r.get('title')}\nSnippet: {r.get('body')}\nSource Link: {r.get('href')}\n\n"
        return search_data if search_data else "No recent data found. Try broadening the search."
    except Exception as e:
        return f"Search failed: {e}"

# ... (Keep your read_webpage tool here) ...

# --- 2. SESSION STATE (The Upgraded Brain) ---
if "messages" not in st.session_state:
    st.session_state.messages = [] 

if "agent" not in st.session_state:
    st.session_state.agent = client.chats.create(
        model='gemini-3-flash-preview', 
        config=types.GenerateContentConfig(
            # WE INJECT THE CURRENT YEAR SO IT DOESN'T HALLUCINATE PAST DATES
            system_instruction="""You are an elite UPSC AI. The current date is March 2026.
            RULE 1: When asked about current affairs, data, or rates (like RBI), YOU MUST USE YOUR SEARCH TOOL. Do not guess.
            RULE 2: At the very end of EVERY response, include a '📚 Sources' section. You MUST output the exact, clickable URL link provided by the search tool.""",
            tools=[search_current_affairs, read_webpage], 
        )
    )

# --- 3. THE ADVANCED SIDEBAR (Fixed) ---
with st.sidebar:
    # Notice the st.rerun() in the lambda function to force the screen to refresh!
    st.button("➕ New chat", use_container_width=True, on_click=lambda: [st.session_state.messages.clear(), st.rerun()])
    
    # We use st.toast to give visual feedback that the buttons are actually working
    if st.button("🔍 Search chat", use_container_width=True): st.toast("Search feature coming soon!", icon="🔍")
    
    incognito = st.toggle("🕵️ Incognito mode")
    if incognito: st.caption("Incognito active: Chats won't be saved.")
        
    st.divider()
    if st.button("📁 My Stuff", use_container_width=True): st.toast("Opening your files...", icon="📁")
    if st.button("⚙️ Settings", use_container_width=True): st.toast("Opening settings...", icon="⚙️")
    if st.button("❓ Help", use_container_width=True): st.toast("Connecting to support...", icon="❓")

# --- 4. THE WELCOME SCREEN (Fixed) ---
# A helper function to process clicks and FORCE a screen refresh
def quick_prompt(text):
    st.session_state.messages.append({"role": "user", "content": text})
    
if len(st.session_state.messages) == 0:
    st.markdown("<h1 style='text-align: center;'>Where should we start?</h1>", unsafe_allow_html=True)
    st.write("") 
    
    col1, col2 = st.columns(2)
    with col1:
        # We now wrap the logic in our new helper function so it actually triggers the chat!
        if st.button("🖼️ Create image", use_container_width=True): 
            quick_prompt("Help me create an image.")
            st.rerun()
        if st.button("🎸 Create music", use_container_width=True): 
            quick_prompt("Help me create some music.")
            st.rerun()
        if st.button("✍️ Write anything", use_container_width=True): 
            quick_prompt("I need help writing a study schedule.")
            st.rerun()
    with col2:
        if st.button("🏏 Explore cricket", use_container_width=True): 
            quick_prompt("Give me the latest updates on the Indian cricket team.")
            st.rerun()
        if st.button("☀️ Boost my day", use_container_width=True): 
            quick_prompt("Give me a motivational quote for my UPSC preparation.")
            st.rerun()
        if st.button("🎬 Create video", use_container_width=True): 
            quick_prompt("Help me generate a video concept.")
            st.rerun()
# --- 5. THE ADVANCED CHAT HISTORY (With Actions & Tools) ---
for i, msg in enumerate(st.session_state.messages):
    avatar_icon = "🧑‍💻" if msg["role"] == "user" else "✨"
    
    with st.chat_message(msg["role"], avatar=avatar_icon):
        
        # 1. EDIT MODE
        if st.session_state.get(f"edit_mode_{i}", False):
            new_text = st.text_area("Update message:", value=msg["content"], key=f"text_area_{i}")
            edit_col1, edit_col2, _ = st.columns([1, 1, 4])
            with edit_col1:
                if st.button("✅ Save", key=f"save_edit_{i}"):
                    st.session_state.messages[i]["content"] = new_text
                    st.session_state[f"edit_mode_{i}"] = False
                    st.rerun()
            with edit_col2:
                if st.button("❌ Cancel", key=f"cancel_edit_{i}"):
                    st.session_state[f"edit_mode_{i}"] = False
                    st.rerun()
                    
        # 2. NORMAL DISPLAY MODE
        else:
            st.markdown(msg["content"])
            
            # THE 5 ACTION COLUMNS
            st.write("") 
            act_col1, act_col2, act_col3, act_col4, act_col5 = st.columns([1.2, 1.2, 1.2, 1.5, 1.5])
            
            # COLUMN 1: EDIT
            with act_col1:
                if st.button("✏️ Edit", key=f"edit_btn_{i}", help="Edit this message"):
                    st.session_state[f"edit_mode_{i}"] = True
                    st.rerun()
                    
            # COLUMN 2: SAVE AS EXPORTS
            with act_col2:
                with st.popover("💾 Save..."):
                    st.download_button("📄 PDF Document", data=create_pdf(msg["content"]), file_name=f"Note_{i}.pdf", mime="application/pdf", key=f"pdf_{i}", use_container_width=True)
                    st.download_button("📝 Word Document", data=create_docx(msg["content"]), file_name=f"Note_{i}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"docx_{i}", use_container_width=True)
                    st.download_button("📊 Excel Sheet", data=create_excel(msg["content"]), file_name=f"Note_{i}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"xls_{i}", use_container_width=True)
                    st.download_button("🖼️ Image File", data=create_image(msg["content"]), file_name=f"Note_{i}.png", mime="image/png", key=f"img_{i}", use_container_width=True)
            
            # COLUMN 3: COPY
            with act_col3:
                with st.popover("📋 Copy"):
                    st.caption("Click the copy icon top right:")
                    st.code(msg["content"], language="markdown")
                    
            # COLUMN 4: PREMIUM AUDIO
            with act_col4:
                with st.popover("🔊 Listen"):
                    selected_speed = st.radio("Speed", [1.0, 1.25, 1.5], horizontal=True, key=f"speed_{i}", label_visibility="collapsed")
                    if st.button("▶️ Play Audio", key=f"gen_audio_{i}", use_container_width=True):
                        with st.spinner("Synthesizing..."):
                            try:
                                audio_bytes = create_audio(msg["content"], selected_speed)
                                st.audio(audio_bytes, format="audio/mp3")
                            except Exception as e:
                                st.error(f"Audio failed: {e}")
                                
            # COLUMN 5: STUDY TOOLS
            with act_col5:
                with st.popover("🛠️ Tools"):
                    if st.button("🧠 Mind Map", key=f"mm_{i}", use_container_width=True):
                        st.session_state.messages.append({"role": "user", "content": f"Convert the information above into a highly structured, text-based Mind Map using bullet points."})
                        st.rerun()
                        
                    if st.button("📇 Image Cards", key=f"fc_{i}", use_container_width=True):
                        # Activate the flashcard display mode for this specific message
                        st.session_state[f"show_cards_{i}"] = True
                        st.rerun()
            
            # --- THE FLASHCARD RENDERER ---
            # If the user clicked "Image Cards", we render them directly below the buttons
            if st.session_state.get(f"show_cards_{i}", False):
                st.divider()
                st.markdown("#### 📇 Key Point Flashcards")
                
                # We extract clean sentences/bullets from the AI's output
                raw_lines = msg["content"].split('\n')
                clean_lines = [line.strip('-*# ') for line in raw_lines if len(line.strip()) > 30]
                
                # Take up to the top 4 most important points
                key_points = clean_lines[:4] 
                
                if not key_points:
                    st.warning("Not enough text to generate cards.")
                else:
                    # Create a column for each image card
                    card_cols = st.columns(len(key_points))
                    for idx, point in enumerate(key_points):
                        # Generate the image
                        card_img_bytes = create_flashcard(point, idx + 1)
                        # Display the image
                        card_cols[idx].image(card_img_bytes, use_container_width=True)
                        # Add a download button under each image
                        card_cols[idx].download_button("💾 Save Card", card_img_bytes, file_name=f"flashcard_{idx+1}.png", mime="image/png", key=f"dl_card_{i}_{idx}", use_container_width=True)
                
                # Close button to hide the cards again
                if st.button("❌ Close Cards", key=f"close_fc_{i}"):
                    st.session_state[f"show_cards_{i}"] = False
                    st.rerun()
                    
# --- 6. THE BOTTOM CONTROL BAR (Screenshot 1 Replication) ---
# We build a floating control deck right above the text input
st.write("") 
ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4 = st.columns([1, 1, 3, 1])

with ctrl_col1:
    # The "+" Button Popover (Hides the file uploader!)
    with st.popover("➕", help="Upload files"):
        uploaded_file = st.file_uploader("Upload Notes, Images, or Audio", type=['txt', 'pdf', 'jpg', 'png', 'mp3', 'mp4'])
        if uploaded_file:
            st.success(f"{uploaded_file.name} ready!")
            st.session_state.uploaded_file = uploaded_file

with ctrl_col2:
    # The Tune/Settings icon
    with st.popover("⚯", help="Chat Settings"):
        st.slider("Creativity (Temperature)", 0.0, 1.0, 0.7)

with ctrl_col3:
    # The "Pro" Dropdown
    selected_model = st.selectbox("Model", ["Pro", "Flash"], label_visibility="collapsed")

with ctrl_col4:
    # The Mic icon
    st.button("🎙️", help="Voice Input coming soon")

# --- 7. THE CHAT INPUT & LOGIC ---
if user_prompt := st.chat_input("Ask a question..."):
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    st.rerun()

# Trigger AI response if the last message was from the user
# Trigger AI response if the last message was from the user
if len(st.session_state.messages) > 0 and st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant", avatar="✨"):
        try:
            prompt_data = [st.session_state.messages[-1]["content"]]
            
            if "uploaded_file" in st.session_state and st.session_state.uploaded_file:
                prompt_data[0] = f"[File attached: {st.session_state.uploaded_file.name}] {prompt_data[0]}"
                
            # --- THE NEW THINKING UI ---
            with st.status("🧠 Agent is thinking and gathering sources...", expanded=True) as status:
                st.write("Analyzing query context...")
                st.write("Accessing web tools and reading documents if necessary...")
                
                # The AI does its processing here while the box spins
                response_stream = st.session_state.agent.send_message_stream(prompt_data)
                
                # Collapse the box and show a success message when it's ready to type
                status.update(label="💡 Answer synthesized!", state="complete", expanded=False)
                
            # The typewriter effect streams the final answer below the collapsed thinking box
            full_response = st.write_stream((chunk.text for chunk in response_stream))
            
            if not incognito:
                st.session_state.messages.append({"role": "assistant", "content": full_response})
            
        except Exception as e:
            st.error(f"Error: {e}")
