import streamlit as st
import requests
from datetime import datetime
from typing import List, Dict

st.set_page_config(
    page_title="AI Calendar Booking Agent",
    page_icon="🗓️",
    layout="wide"
)

st.markdown("""
<style>
    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 15px;
        border-radius: 15px 15px 5px 15px;
        margin: 10px 0;
        margin-left: 20%;
    }
    
    .assistant-message {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        color: white;
        padding: 15px;
        border-radius: 15px 15px 15px 5px;
        margin: 10px 0;
        margin-right: 20%;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 8px 16px;
    }
</style>
""", unsafe_allow_html=True)

if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []
if "booking_confirmed" not in st.session_state:
    st.session_state.booking_confirmed = False

def send_message(message: str) -> Dict:
    try:
        payload = {
            "message": message,
            "conversation_history": [
                {"role": msg["role"], "content": msg["content"]}
                for msg in st.session_state.conversation_history
            ]
        }
        
        response = requests.post("http://localhost:8000/chat", json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "response": "is server running?",
                "conversation_history": st.session_state.conversation_history,
                "booking_confirmed": False
            }
    except:
        return {
            "response": "Please make sure the backend server is running.",
            "conversation_history": st.session_state.conversation_history,
            "booking_confirmed": False
        }

def display_message(message: Dict):
    role = message["role"]
    content = message["content"]
    
    if role == "user":
        st.markdown(f'<div class="user-message"><strong>You:</strong><br>{content}</div>', 
                unsafe_allow_html=True)
    else:
        formatted_content = content.replace('\n', '<br>')
        st.markdown(f'<div class="assistant-message"><strong>AI Assistant:</strong><br>{formatted_content}</div>', 
                unsafe_allow_html=True)

st.title("🗓️ AI Calendar Booking Agent")
st.markdown("your intelligent assistant for scheduling meetings and checking availability")

with st.sidebar:
    st.header("quick Actions")
    
    quick_actions = [
        "check my availability today",
        "schedule a meeting tomorrow morning", 
        "book a meeting on Monday morning",
        "check my availability on Monday"
    ]
    
    for action in quick_actions:
        if st.button(action):
            st.session_state.conversation_history.append({
                "role": "user",
                "content": action
            })
            result = send_message(action)
            st.session_state.conversation_history.append({
                "role": "assistant",
                "content": result["response"]
            })
            if result.get("booking_confirmed"):
                st.session_state.booking_confirmed = True
            
            st.rerun()
    
    st.markdown("---")
    
    st.subheader("Current Info")
    current_time = datetime.now()
    st.write(f"Today:{current_time.strftime('%A, %B %d, %Y')}")
    st.write(f"Time:{current_time.strftime('%I:%M %p')}")
    
    st.markdown("---")
    

    if st.button("New Conversation"):
        st.session_state.conversation_history = []
        st.session_state.booking_confirmed = False
        st.rerun()

st.markdown("### Conversation")

if st.session_state.conversation_history:
    for message in st.session_state.conversation_history:
        display_message(message)
else:
    st.markdown("""
    <div class="assistant-message">
        <strong>AI Assistant:</strong><br>
        hello! I'm your AI booking assistant. I can help you:<br><br>
        <strong>Check availability</strong> - "What's my availability for Friday?"<br>
        <strong>Schedule meetings</strong> - "Book a meeting tomorrow afternoon"<br>
        <strong>Schedule calls</strong> - "Schedule a call for next Monday morning"<br><br>
        what would you like to do today?
    </div>
    """, unsafe_allow_html=True)

if st.session_state.booking_confirmed:
    st.success("booking Confirmed! Your meeting has been successfully added to your calendar!")

user_input = st.chat_input("Type your message here... (e.g., 'Check my availability tomorrow')")

if user_input:
    st.session_state.conversation_history.append({
        "role": "user",
        "content": user_input
    })
    
    with st.spinner("🤖 Processing..."):
        result = send_message(user_input)
    st.session_state.conversation_history.append({
        "role":"assistant",
        "content":result["response"]
    })
    
    if result.get("booking_confirmed"):
        st.session_state.booking_confirmed = True
    st.rerun()

with st.expander("How to use this assistant"):
    st.markdown("""
    Example requests you can make:
    
    Check Availability:
    - "Check my availability today"
    - "Do i have any free time this Friday?"
    
    Tips:
    - Be specific about dates and times
    - Use natural language - I understand "tomorrow", "Friday", "next week", etc.
    - Follow the conversation flow - I'll guide you through the booking process
    """)

st.markdown("---")
st.markdown("Note: Make sure the FastAPI backend is running")