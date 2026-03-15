import streamlit as st
import time
import tempfile
import os
import pypdf
import docx
from PIL import Image
from google import genai
from google.genai import types
from duckduckgo_search import DDGS
import requests
from bs4 import BeautifulSoup

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
def search_current_affairs(topic: str) -> str:
    try:
        results = DDGS().news(topic, max_results=3)
        return "\n\n".join([f"Headline: {r.get('title')}\nSnippet: {r.get('body')}" for r in results])
    except Exception as e: return f"Search failed: {e}"

def read_webpage(url: str) -> str:
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        return f"Extracted text:\n\n{soup.get_text(separator=' ', strip=True)[:6000]}"
    except Exception as e: return f"Failed to read link: {e}"

# --- 2. SESSION STATE ---
# --- 2. SESSION STATE (The App's Memory) ---
# This MUST come before the sidebar and chat logic!
if "messages" not in st.session_state:
    st.session_state.messages = [] # Start empty for the welcome screen

if "agent" not in st.session_state:
    st.session_state.agent = client.chats.create(
        model='gemini-3-flash-preview', 
        config=types.GenerateContentConfig(
            system_instruction="You are a highly advanced multimodal AI assistant.",
            tools=[search_current_affairs, read_webpage], 
        )
    )

# --- 3. THE ADVANCED SIDEBAR ---
with st.sidebar:
    st.button("➕ New chat", use_container_width=True, on_click=lambda: st.session_state.messages.clear())
    st.button("🔍 Search chat", use_container_width=True)
    
    # Incognito Mode Toggle
    incognito = st.toggle("🕵️ Incognito mode")
    if incognito:
        st.caption("Incognito active: Chats won't be saved to history.")
        
    st.divider()
    
    st.button("📁 My Stuff", use_container_width=True)
    st.button("⚙️ Settings", use_container_width=True)
    st.button("❓ Help", use_container_width=True)

# --- 4. THE WELCOME SCREEN (Quick Actions) ---
# If chat is empty, show the "Where should we start?" grid
if len(st.session_state.messages) == 0:
    st.markdown("<h1 style='text-align: center;'>Where should we start?</h1>", unsafe_allow_html=True)
    st.write("") # Spacer
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🖼️ Create image", use_container_width=True): st.session_state.messages.append({"role": "user", "content": "Help me create an image."})
        if st.button("🎸 Create music", use_container_width=True): st.session_state.messages.append({"role": "user", "content": "Help me create some music."})
        if st.button("✍️ Write anything", use_container_width=True): st.session_state.messages.append({"role": "user", "content": "I need help writing something."})
    with col2:
        if st.button("🏏 Explore cricket", use_container_width=True): st.session_state.messages.append({"role": "user", "content": "Give me the latest updates on cricket."})
        if st.button("☀️ Boost my day", use_container_width=True): st.session_state.messages.append({"role": "user", "content": "Tell me something positive to boost my day."})
        if st.button("🎬 Create video", use_container_width=True): st.session_state.messages.append({"role": "user", "content": "Help me generate a video."})
    
    st.write("\n\n") # Push the chat input to the bottom

# --- 5. THE ADVANCED CHAT HISTORY (With Actions) ---
for i, msg in enumerate(st.session_state.messages):
    avatar_icon = "🧑‍💻" if msg["role"] == "user" else "✨"
    
    with st.chat_message(msg["role"], avatar=avatar_icon):
        
        # 1. Check if the user clicked "Edit" for this specific message
        if st.session_state.get(f"edit_mode_{i}", False):
            # Show an interactive text box instead of normal text
            new_text = st.text_area("Update message:", value=msg["content"], key=f"text_area_{i}")
            
            # Save or Cancel buttons for the edit
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
                    
        # 2. Normal Display Mode
        else:
            st.markdown(msg["content"])
            
            # The Action Bar (Small buttons packed tightly underneath the message)
            st.write("") # Small spacer
            act_col1, act_col2, act_col3, _ = st.columns([1.2, 1.2, 1.2, 5])
            
            with act_col1:
                # EDIT BUTTON
                if st.button("✏️ Edit", key=f"edit_btn_{i}", help="Edit this message"):
                    st.session_state[f"edit_mode_{i}"] = True
                    st.rerun()
                    
            with act_col2:
                # SAVE BUTTON (Downloads to hard drive)
                st.download_button(
                    "💾 Save", 
                    data=msg["content"], 
                    file_name=f"Study_Note_{i}.txt", 
                    mime="text/plain", 
                    key=f"save_btn_{i}", 
                    help="Download as text file"
                )
                
            with act_col3:
                # COPY BUTTON (The Streamlit Clipboard Hack)
                with st.popover("📋 Copy", help="Copy to clipboard"):
                    st.caption("Click the copy icon in the top right of this box:")
                    # st.code has a built-in native clipboard copy icon!
                    st.code(msg["content"], language="markdown")
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
if len(st.session_state.messages) > 0 and st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant", avatar="✨"):
        try:
            prompt_data = [st.session_state.messages[-1]["content"]]
            
            # If a file was uploaded via the '+' button, attach it here (logic kept simple for this UI demo)
            if "uploaded_file" in st.session_state and st.session_state.uploaded_file:
                prompt_data[0] = f"[File attached: {st.session_state.uploaded_file.name}] {prompt_data[0]}"
                
            with st.spinner("Synthesizing..."):
                response_stream = st.session_state.agent.send_message_stream(prompt_data)
                
            full_response = st.write_stream((chunk.text for chunk in response_stream))
            
            # Save unless incognito is toggled
            if not incognito:
                st.session_state.messages.append({"role": "assistant", "content": full_response})
            
        except Exception as e:
            st.error(f"Error: {e}")
