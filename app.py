import tempfile
import os
import io
import pypdf
import docx
from PIL import Image
import streamlit as st
import time
from google import genai
from google.genai import types
from duckduckgo_search import DDGS
import requests
from bs4 import BeautifulSoup

# --- 1. PAGE SETUP ---
st.set_page_config(page_title="Multimodal Study Agent", page_icon="🤖", layout="centered")
st.title("📚 UPSC AI Study Assistant")
st.caption("Powered by Gemini 2.5 Flash. Search the web, scrape links, and get formatted study notes.")

# --- 2. SECURE API KEY INITIALIZATION ---
# Streamlit will look for the key in a hidden secrets.toml file when published
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    # Fallback for local testing (Replace with your key ONLY for local testing, remove before publishing)
    api_key = "PASTE_YOUR_API_KEY_HERE_TEMPORARILY"

client = genai.Client(api_key=api_key)

# --- 3. THE TOOLS (Web-Safe Versions) ---
def search_current_affairs(topic: str) -> str:
    """Searches the internet for recent news."""
    try:
        results = DDGS().news(topic, max_results=3)
        search_data = ""
        for result in results:
            search_data += f"Headline: {result.get('title')}\nSnippet: {result.get('body')}\nSource: {result.get('source')}\n\n"
        return search_data if search_data else "No recent news found."
    except Exception as e:
        return f"Search failed: {e}"

def read_webpage(url: str) -> str:
    """Scrapes readable text from a standard URL."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return f"Website blocked access (Error code: {response.status_code})."
        soup = BeautifulSoup(response.text, 'html.parser')
        text_content = soup.get_text(separator=' ', strip=True)
        return f"Extracted text:\n\n{text_content[:6000]}"
    except Exception as e:
        return f"Failed to read link: {e}"

# --- 4. SESSION STATE (The App's Memory) ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hello! I am ready to help you study. Drop a link or ask a question."}]

if "agent" not in st.session_state:
    st.session_state.agent = client.chats.create(
        # THE UPGRADE: Swap 'gemini-2.5-flash' for the newest model available to your API key
        model='gemini-3.0-flash', # Or try 'gemini-3.1-pro' if your API tier supports it
        config=types.GenerateContentConfig(
            system_instruction="""You are a public UPSC study assistant. 
            Format all answers clearly using Markdown.
            Use your tools to search the web or read URLs when necessary.""",
            tools=[search_current_affairs, read_webpage], 
        )
    )
# --- 4.5. THE MULTIMODAL SIDEBAR ---
# --- 4.5. THE MULTIMODAL SIDEBAR (Video & Binary Upgraded) ---
with st.sidebar:
    st.header("📂 Universal File Uploader")
    st.caption("Upload Notes, Images, Audio, or Video files.")
    
    # We added MP4 to the list
    uploaded_file = st.file_uploader(
        "Drop a file here", 
        type=['txt', 'csv', 'pdf', 'docx', 'jpg', 'jpeg', 'png', 'mp3', 'wav', 'mp4'], 
        accept_multiple_files=False
    )
    
    if uploaded_file is not None:
        file_ext = uploaded_file.name.split('.')[-1].lower()
        st.success(f"File recognized: {uploaded_file.name}")
        
        try:
            # 1. Plain Text & CSV (Bulletproof Encoding)
            if file_ext in ['txt', 'csv']:
                st.session_state.upload_type = 'text'
                raw_bytes = uploaded_file.read()
                try:
                    text_content = raw_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    text_content = raw_bytes.decode("latin-1")
                st.session_state.uploaded_content = text_content
                st.info("Text extracted and ready!")
                
            # 2. PDF Files (Binary Text Extraction)
            elif file_ext == 'pdf':
                st.session_state.upload_type = 'text'
                reader = pypdf.PdfReader(uploaded_file)
                extracted_text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
                st.session_state.uploaded_content = extracted_text
                st.info("PDF text extracted and ready!")
                
            # 3. Word Documents (Binary Text Extraction)
            elif file_ext == 'docx':
                st.session_state.upload_type = 'text'
                doc = docx.Document(uploaded_file)
                extracted_text = "\n".join([para.text for para in doc.paragraphs])
                st.session_state.uploaded_content = extracted_text
                st.info("Word document text extracted!")
                
            # 4. Images
            elif file_ext in ['jpg', 'jpeg', 'png']:
                st.session_state.upload_type = 'image'
                image = Image.open(uploaded_file)
                st.session_state.uploaded_content = image
                st.image(image, caption="Ready for AI Analysis", use_container_width=True)
                
            # 5. Heavy Media (Audio & Video) - Requires Cloud Upload
            elif file_ext in ['mp3', 'wav', 'mp4']:
                st.session_state.upload_type = 'cloud_media'
                st.info(f"Uploading {file_ext.upper()} to Gemini servers... Please wait.")
                
                # We save the file temporarily to the server's hard drive
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as tmp_file:
                    tmp_file.write(uploaded_file.read())
                    tmp_file_path = tmp_file.name
                
                # Upload the physical file to Google's API
                gemini_file = client.files.upload(file=tmp_file_path)
                
                # If it's a video, we MUST wait for Google to process the frames
                if file_ext == 'mp4':
                    st.warning("Video uploaded. Processing frames (this takes a moment)...")
                    while gemini_file.state.name == "PROCESSING":
                        time.sleep(3)
                        gemini_file = client.files.get(name=gemini_file.name)
                        
                st.session_state.uploaded_content = gemini_file
                st.success("Media processed and ready for analysis!")
                
                # Clean up the temporary file so we don't clog the server
                os.remove(tmp_file_path)
                
        except Exception as e:
            st.error(f"Failed to process file: {e}")
            
    # --- THE CLEAR MEMORY BUTTON ---
    st.divider()  # Adds a clean visual line to separate the uploader from the button
    
    if st.button("🗑️ Clear Memory & Cloud Files", use_container_width=True):
        # 1. Delete heavy media from Google's servers
        if "uploaded_content" in st.session_state and st.session_state.get("upload_type") == "cloud_media":
            try:
                gemini_file = st.session_state.uploaded_content
                client.files.delete(name=gemini_file.name)
                print(f"[System: 🗑️ Deleted {gemini_file.name} from cloud storage.]")
            except Exception as e:
                st.error(f"Failed to delete cloud file: {e}")
                
        # 2. Wipe the Streamlit app's memory (Chat history & context)
        for key in list(st.session_state.keys()):
            del st.session_state[key]
            
        st.success("Memory completely cleared! Refreshing UI...")
        time.sleep(1)  # Brief pause so you can see the success message
        st.rerun()     # Instantly reloads the page to a blank slate
    
    # What happens when the user drops a file
    if uploaded_file is not None:
        st.success(f"File '{uploaded_file.name}' loaded successfully!")
        
        # Read the file's contents
        try:
            document_text = uploaded_file.read().decode("utf-8")
            
            # Save the text to the app's memory so the AI can access it
            st.session_state.uploaded_context = document_text
            st.info("Document text extracted and ready for the AI!")
            
        except Exception as e:
            st.error(f"Failed to read file: {e}")
# --- 7. THE ADVANCED CHAT INTERFACE (Streaming Upgrade) ---

# 1. Display past messages with custom Avatars
for msg in st.session_state.messages:
    # Set the icon based on who is talking
    avatar_icon = "🧑‍💻" if msg["role"] == "user" else "✨"
    with st.chat_message(msg["role"], avatar=avatar_icon):
        st.markdown(msg["content"])

if user_prompt := st.chat_input("Ask a question, analyze a file, or paste a link..."):
    # Add user message to memory and display it
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(user_prompt)
        
    # Build the AI's streaming response
    with st.chat_message("assistant", avatar="✨"):
        try:
            prompt_data = [user_prompt]
            
            # Inject context if a file is uploaded in the sidebar
            if "uploaded_content" in st.session_state and st.session_state.uploaded_content:
                u_type = st.session_state.upload_type
                u_content = st.session_state.uploaded_content
                
                if u_type == 'text':
                    prompt_data[0] = f"Reference Document:\n\n{u_content[:15000]}\n\nUser Question: {user_prompt}"
                elif u_type in ['image', 'cloud_media']:
                    prompt_data.insert(0, u_content)
            
            # THE UPGRADE: The smooth loading spinner
            with st.spinner("Synthesizing answer..."):
                # We use send_message_stream instead of send_message
                response_stream = st.session_state.agent.send_message_stream(prompt_data)
                
            # THE UPGRADE: st.write_stream automatically creates the real-time typewriter effect!
            full_response = st.write_stream((chunk.text for chunk in response_stream))
            
            # Save the fully generated response to memory
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            st.error(error_msg) # Uses a modern red error box instead of plain text
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
