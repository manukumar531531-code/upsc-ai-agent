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
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("*(Thinking...)*")
        
        try:
            response = st.session_state.agent.send_message(user_prompt)
            message_placeholder.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            message_placeholder.error(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
