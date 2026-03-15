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
with st.sidebar:
    st.header("📂 Universal File Uploader")
    st.caption("Upload Notes, Images, or Audio files.")
    
    # We expanded the accepted file types!
    uploaded_file = st.file_uploader(
        "Drop a file here", 
        type=['txt', 'csv', 'pdf', 'docx', 'jpg', 'jpeg', 'png', 'mp3', 'wav'], 
        accept_multiple_files=False
    )
    
    if uploaded_file is not None:
        file_ext = uploaded_file.name.split('.')[-1].lower()
        st.success(f"File loaded: {uploaded_file.name}")
        
        try:
            # 1. Handle Plain Text & CSV
            if file_ext in ['txt', 'csv']:
                st.session_state.upload_type = 'text'
                st.session_state.uploaded_content = uploaded_file.read().decode("utf-8")
                st.info("Text extracted and ready!")
                
            # 2. Handle PDFs
            elif file_ext == 'pdf':
                st.session_state.upload_type = 'text'
                reader = pypdf.PdfReader(uploaded_file)
                extracted_text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
                st.session_state.uploaded_content = extracted_text
                st.info("PDF text extracted and ready!")
                
            # 3. Handle Word Documents
            elif file_ext == 'docx':
                st.session_state.upload_type = 'text'
                doc = docx.Document(uploaded_file)
                extracted_text = "\n".join([para.text for para in doc.paragraphs])
                st.session_state.uploaded_content = extracted_text
                st.info("Word document text extracted!")
                
            # 4. Handle Images (Vision)
            elif file_ext in ['jpg', 'jpeg', 'png']:
                st.session_state.upload_type = 'image'
                image = Image.open(uploaded_file)
                st.session_state.uploaded_content = image
                st.image(image, caption="Ready for AI Analysis", use_container_width=True)
                
            # 5. Handle Audio
            elif file_ext in ['mp3', 'wav']:
                st.session_state.upload_type = 'audio'
                audio_bytes = uploaded_file.read()
                mime_type = 'audio/mp3' if file_ext == 'mp3' else 'audio/wav'
                # Package it for Gemini
                st.session_state.uploaded_content = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
                st.audio(audio_bytes, format=mime_type)
                st.info("Audio loaded and ready for analysis!")
                
        except Exception as e:
            st.error(f"Failed to process file: {e}")
    
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
# --- 5. THE CHAT INTERFACE ---
# Display all past messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Capture user input
if user_prompt := st.chat_input("Ask a question or paste a link..."):
    # Show user message
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)
        
    # Generate and show AI response
    # Generate and show AI response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("*(Thinking...)*")
        
        try:
            # We put the user's text prompt into a list
            prompt_data = [user_prompt]
            
            # Check if a file is currently loaded in the sidebar
            if "uploaded_content" in st.session_state and st.session_state.uploaded_content:
                u_type = st.session_state.upload_type
                u_content = st.session_state.uploaded_content
                
                # If it's a document, we just glue the text to the prompt
                if u_type == 'text':
                    # We limit to 15,000 chars so massive PDFs don't crash the UI memory
                    prompt_data[0] = f"Reference Document:\n\n{u_content[:15000]}\n\nUser Question: {user_prompt}"
                    
                # If it's an Image or Audio, we pass the actual media file directly to Gemini's brain
                elif u_type in ['image', 'audio']:
                    prompt_data.insert(0, u_content)
            
            # Send the combined data (Text + Media) to the agent
            response = st.session_state.agent.send_message(prompt_data)
            
            message_placeholder.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            
        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            message_placeholder.error(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
