import uuid
import streamlit as st
import requests

BACKEND = "http://localhost:8000"

st.title("Sales Agent — Chat (Streamlit demo)")

# helper: call the available rerun API across Streamlit versions
def _maybe_rerun():
    try:
        st.experimental_rerun()
    except Exception:
        try:
            st.experimental_request_rerun()
        except Exception:
            # last-resort: set a sentinel in session_state to force UI update
            st.session_state._need_rerun = True

# initialize session state
if "session_id" not in st.session_state:
    # create a new ephemeral session uuid
    st.session_state.session_id = str(uuid.uuid4())

if "history" not in st.session_state:
    st.session_state.history = []

# chat sidebar history using session_id
st.sidebar.header("Chat Sessions")
res = requests.get(f"{BACKEND}/sessions")
if res.status_code == 200:
    sessions = res.json().get("sessions", [])
    for sess in sessions:
        # use a unique key per session button to avoid duplicate element ids
        btn_key = f"session-{sess.get('session_id')}"
        if st.sidebar.button(sess.get("title", "Untitled"), key=btn_key):
            st.session_state.session_id = sess["session_id"]
            # load messages for this session into history
            mres = requests.get(f"{BACKEND}/sessions/{sess['session_id']}")
            if mres.status_code == 200:
                msgs = mres.json().get("messages", [])
                st.session_state.history = [{"role": r.get("role"), "content": r.get("content")} for r in msgs]
            else:
                st.session_state.history = []
            _maybe_rerun()
else:
    st.sidebar.error("Error fetching sessions")

# delete session button (unique key)
if st.sidebar.button("Delete Session", key="delete-session"):
    res = requests.delete(f"{BACKEND}/sessions/{st.session_state.session_id}")
    if res.status_code == 200:
        st.sidebar.success("Session deleted")
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.history = []
        st.experimental_rerun()
    else:
        st.sidebar.error("Error deleting session")

# show chat history
st.subheader("Conversation")
for msg in st.session_state.history:
    role = msg.get("role", "")
    content = msg.get("content", "")
    if role == "user":
        st.markdown(f"**You:** {content}")
    else:
        st.markdown(f"**Assistant:** {content}")

with st.form("chat_form"):
    user_input = st.text_input("Type a message")
    submitted = st.form_submit_button("Send")
    if submitted and user_input.strip():
        payload = {
            "session_id": st.session_state.session_id,
            "content": user_input,
            "role": "user"
        }
        # append user message locally immediately
        st.session_state.history.append({"role": "user", "content": user_input})
        res = requests.post(f"{BACKEND}/chat/message", json=payload)
        if res.status_code != 200:
            st.error("Error connecting to backend")
        else:
            data = res.json()
            reply = data.get("reply")
            sid = data.get("session_id")
            if sid:
                st.session_state.session_id = sid
            if reply:
                st.session_state.history.append({"role": "assistant", "content": reply})
                # rerun to display updated history
                _maybe_rerun()
