import uuid
import streamlit as st
import requests

BACKEND = "http://localhost:8000"

st.title("Sales Agent — Chat (Streamlit demo)")

if "session_id" not in st.session_state:
    # create a new ephemeral session uuid
    st.session_state.session_id = str(uuid.uuid4())

# chat sidebar history using session_id
st.sidebar.header("Chat Sessions")
res = requests.get(f"{BACKEND}/sessions")
if res.status_code == 200:
    sessions = res.json().get("sessions", [])
    for sess in sessions:
        if st.sidebar.button(sess["title"]):
            st.session_state.session_id = sess["session_id"]
            st.experimental_rerun()
else:
    st.sidebar.error("Error fetching sessions")

# delete session button
if st.sidebar.button("Delete Session"):
    res = requests.delete(f"{BACKEND}/sessions/{st.session_state.session_id}")
    if res.status_code == 200:
        st.sidebar.success("Session deleted")
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.history = []
        st.experimental_rerun()
    else:
        st.sidebar.error("Error deleting session")

with st.form("chat_form"):
    user_input = st.text_input("Type a message")
    submitted = st.form_submit_button("Send")
    if submitted and user_input.strip():
        payload = {
            "session_id": st.session_state.session_id,
            "content": user_input,
            "role": "user"
        }
        res = requests.post(f"{BACKEND}/chat/message", json=payload)
        if res.status_code != 200:
            st.error("Error connecting to backend")
