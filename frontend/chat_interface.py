import uuid
import streamlit as st
import requests
import json

BACKEND = "http://localhost:8001"

st.set_page_config(
    page_title="B2B Sales Agent", 
    page_icon="🛒", 
    layout="wide"
)

st.title("🛒 B2B Sales Agent")

# Helper function for rerun across Streamlit versions
def _maybe_rerun():
    try:
        st.rerun()
    except:
        try:
            st.experimental_rerun()
        except:
            st.session_state._need_rerun = True

# Initialize session state
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "history" not in st.session_state:
    st.session_state.history = []

if "current_stage" not in st.session_state:
    st.session_state.current_stage = "discovery"

# Sidebar for session management
with st.sidebar:
    st.header("💬 Chat Sessions")
    
    try:
        res = requests.get(f"{BACKEND}/sessions", timeout=5)
        if res.status_code == 200:
            sessions = res.json().get("sessions", [])
            
            # Show current stage
            stage_emoji = "🔍" if st.session_state.current_stage == "discovery" else "💰"
            stage_name = st.session_state.current_stage.title()
            st.info(f"{stage_emoji} Current Stage: **{stage_name}**")
            
            if sessions:
                st.subheader("Previous Sessions")
                for sess in sessions[-10:]:  # Show last 10 sessions
                    title = sess.get("title", "Untitled")[:30] + "..." if len(sess.get("title", "")) > 30 else sess.get("title", "Untitled")
                    if st.button(f"📄 {title}", key=f"session-{sess.get('session_id')}"):
                        st.session_state.session_id = sess["session_id"]
                        # Load messages for this session
                        mres = requests.get(f"{BACKEND}/sessions/{sess['session_id']}")
                        if mres.status_code == 200:
                            msgs = mres.json().get("messages", [])
                            st.session_state.history = [
                                {"role": r.get("role"), "content": r.get("content")} 
                                for r in msgs
                            ]
                        else:
                            st.session_state.history = []
                        _maybe_rerun()
            else:
                st.info("No previous sessions")
                
        else:
            st.error("Cannot connect to backend")
    except requests.exceptions.ConnectionError:
        st.error("🔴 Backend not running")
    except Exception as e:
        st.error(f"Error: {e}")

# Main chat area
st.subheader("💬 Conversation")

# Display chat history
if st.session_state.history:
    for i, msg in enumerate(st.session_state.history):
        role = msg.get("role", "")
        content = msg.get("content", "")
        
        if role == "user":
            with st.chat_message("user"):
                st.write(content)
        elif role == "assistant":
            with st.chat_message("assistant"):
                st.write(content)
else:
    with st.chat_message("assistant"):
        st.write("👋 Hello! I'm your B2B sales assistant. I can help you find products and get quotes. What are you looking for today?")

# Chat input
if prompt := st.chat_input("Type your message here..."):
    # Add user message to history immediately
    st.session_state.history.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.write(prompt)
    
    # Send to backend
    try:
        payload = {
            "session_id": st.session_state.session_id,
            "content": prompt,
            "role": "user"
        }
        
        with st.spinner("🤔 Thinking..."):
            response = requests.post(f"{BACKEND}/chat/message", json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            reply = data.get("reply", "Sorry, I couldn't process that.")
            stage = data.get("stage", "discovery")
            products = data.get("products", [])
            next_questions = data.get("next_questions", [])
            
            # Update session state
            if data.get("session_id"):
                st.session_state.session_id = data["session_id"]
            st.session_state.current_stage = stage
            
            # Add assistant response to history
            st.session_state.history.append({"role": "assistant", "content": reply})
            
            # Display assistant response
            with st.chat_message("assistant"):
                st.write(reply)
                
                # Show products if any
                if products:
                    st.subheader("🛍️ Recommended Products:")
                    for product in products:
                        with st.expander(f"📦 {product.get('name', 'Unknown Product')}"):
                            if product.get('description'):
                                st.write(f"**Description:** {product['description']}")
                            if product.get('price', 0) > 0:
                                st.write(f"**Price:** ${product['price']:,.2f}")
                
            _maybe_rerun()
            
        else:
            st.error(f"❌ Error: {response.status_code} - {response.text}")
            
    except requests.exceptions.Timeout:
        st.error("⏰ Request timed out. The AI might be processing a complex query.")
    except requests.exceptions.ConnectionError:
        st.error("🔴 Cannot connect to backend. Make sure the server is running.")
    except Exception as e:
        st.error(f"❌ Unexpected error: {e}")

# Handle auto-question (for suggested questions)
if hasattr(st.session_state, 'auto_question'):
    auto_q = st.session_state.auto_question
    delattr(st.session_state, 'auto_question')
    
    # Add to history and process
    st.session_state.history.append({"role": "user", "content": auto_q})
    
    try:
        payload = {
            "session_id": st.session_state.session_id,
            "content": auto_q,
            "role": "user"
        }
        
        response = requests.post(f"{BACKEND}/chat/message", json=payload)
        if response.status_code == 200:
            data = response.json()
            reply = data.get("reply", "Sorry, I couldn't process that.")
            st.session_state.history.append({"role": "assistant", "content": reply})
            if data.get("stage"):
                st.session_state.current_stage = data["stage"]
    except:
        pass  # Fail silently for auto questions
    
    _maybe_rerun()


# Health check indicator
try:
    health_response = requests.get(f"{BACKEND}/health", timeout=2)
    if health_response.status_code == 200:
        st.sidebar.success("🟢 Backend Online")
    else:
        st.sidebar.error("🔴 Backend Issues")
except:
    st.sidebar.error("🔴 Backend Offline")
