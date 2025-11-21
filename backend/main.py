import os
import sys
import logging
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
import uuid
from backend.services.postgres_service import PostgresService
from backend.models.pydantic_model import MessageIn, ConversationResponse
from backend.agents.conversation_manager import handle_user_message
import asyncpg

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Require DATABASE_URL to be set
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable is not set.")
    print("Set it to your Postgres connection string, for example:")
    print("  postgresql://<user>:<password>@localhost:5432/<database>")
    print("On Windows (PowerShell): $Env:DATABASE_URL = \"postgresql://dev:dev@localhost:5432/app\"")
    print("On Windows (cmd): set DATABASE_URL=postgresql://dev:dev@localhost:5432/app")
    sys.exit(1)

# Initialize service
db_service = PostgresService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect to database
    try:
        await db_service.connect()
        # Quick privilege check
        try:
            async with db_service.pool.acquire() as conn:
                await conn.fetchrow("SELECT 1 FROM sessions LIMIT 1")
        except asyncpg.exceptions.UndefinedTableError:
            pass  # Table doesn't exist yet
        except asyncpg.exceptions.InsufficientPrivilegeError:
            print("ERROR: Database user lacks privileges on 'sessions' table.")
            print("Grant privileges or re-run schema as the application user.")
            raise
    except Exception as e:
        logging.exception("Failed to connect to database.")
        raise RuntimeError(f"Database connection failed: {e}") from e
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

@app.post("/chat/message", response_model=dict)
async def process_message(payload: dict):
    """Process user message and return AI response"""
    try:
        # Extract message data
        session_id_str = payload.get("session_id")
        content = payload.get("content", "")
        role = payload.get("role", "user")
        
        if not content.strip():
            raise HTTPException(status_code=400, detail="Message content cannot be empty")
        
        # Handle session ID
        if not session_id_str:
            new_session_id = await db_service.create_session()
            session_id = new_session_id
        else:
            session_id = uuid.UUID(session_id_str)
            exists = await db_service.session_exists(session_id)
            if not exists:
                await db_service.create_session_with_id(session_id)

        # Process message through conversation manager
        if role == "user":
            # Check if database is connected
            if not db_service.pool:
                raise HTTPException(
                    status_code=503, 
                    detail="Database not connected. Make sure DATABASE_URL is set and PostgreSQL is running."
                )
            
            response = await handle_user_message(
                session_id=session_id,
                content=content,
                db_service=db_service  # Pass the connected database service
            )
            
            return {
                "status": "success",
                "session_id": str(session_id),
                "reply": response.message,
                "stage": response.stage.value,
                "products": [p.model_dump() for p in response.products],
                "next_questions": response.next_questions
            }
        else:
            # Just store assistant message
            await db_service.add_message(session_id, role, content)
            return {
                "status": "saved",
                "session_id": str(session_id)
            }
            
    except Exception as e:
        logging.exception("Error processing message")
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

@app.get("/sessions/{session_id}")
async def get_session_messages(session_id: str):
    """Retrieve all messages from a session"""
    try:
        messages = await db_service.get_session_messages(uuid.UUID(session_id))
        return {"messages": messages}
    except Exception as e:
        logging.exception("Error retrieving session messages")
        raise HTTPException(status_code=500, detail=f"Error retrieving messages: {str(e)}")

@app.get("/sessions")
async def list_sessions():
    """Get all sessions for sidebar"""
    try:
        sessions = await db_service.get_all_sessions()
        return {"sessions": sessions}
    except Exception as e:
        logging.exception("Error retrieving sessions")
        raise HTTPException(status_code=500, detail=f"Error retrieving sessions: {str(e)}")

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session"""
    try:
        await db_service.delete_session(uuid.UUID(session_id))
        return {"status": "deleted"}
    except Exception as e:
        logging.exception("Error deleting session")
        raise HTTPException(status_code=500, detail=f"Error deleting session: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "B2B Sales Agent API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
