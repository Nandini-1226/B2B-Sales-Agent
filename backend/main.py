from fastapi import FastAPI
from contextlib import asynccontextmanager
import uuid
from services.postgres_service import PostgresService

# Initialize service
db_service = PostgresService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect to database
    await db_service.connect()
    yield
    # Shutdown: disconnect from database
    await db_service.disconnect()

app = FastAPI(lifespan=lifespan)

# API Routes
@app.post("/chat/session")
async def create_session(title: str = "New Chat"):
    """Create new conversation session"""
    session_id = await db_service.create_session(title)
    return {"session_id": str(session_id)}

@app.post("/chat/message")
async def save_message(session_id: str, role: str, content: str):
    """Save user or assistant message"""
    await db_service.add_message(uuid.UUID(session_id), role, content)
    return {"status": "saved"}

@app.get("/leads/{session_id}")
async def get_session_messages(session_id: str):
    """Retrieve all messages from a session"""
    messages = await db_service.get_session_messages(uuid.UUID(session_id))
    return {"messages": messages}

@app.get("/leads")
async def list_sessions():
    """Get all sessions for sidebar"""
    sessions = await db_service.get_all_sessions()
    return {"sessions": sessions}

@app.delete("/leads/{session_id}")
async def delete_session(session_id: str):
    """Delete a session"""
    await db_service.delete_session(uuid.UUID(session_id))
    return {"status": "deleted"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
