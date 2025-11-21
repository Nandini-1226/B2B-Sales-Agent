import os
import sys
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
import uuid
from backend.services.postgres_service import PostgresService
from backend.models.pydantic_model import MessageIn
from backend.agents.product_retriever import hybrid_search
import asyncpg

# New: require DATABASE_URL to be set (fail fast with guidance)
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
        # quick privilege check: ensure we can read from sessions (or that table exists)
        try:
            async with db_service.pool.acquire() as conn:
                await conn.fetchrow("SELECT 1 FROM sessions LIMIT 1")
        except asyncpg.exceptions.UndefinedTableError:
            # table doesn't exist — the runner should have applied create_tables.sql; continue
            pass
        except asyncpg.exceptions.InsufficientPrivilegeError:
            print("ERROR: connected to Postgres but the DB user lacks privileges on 'sessions'.")
            print("If you created the database with a different owner, grant privileges or re-run the schema as the application user.")
            print("As a superuser, run (psql):")
            print("  GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO <app_user>;")
            print("  GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO <app_user>;")
            raise
    except Exception as e:
        logging.exception("Failed to connect to Postgres. Check DATABASE_URL and that the database is reachable.")
        # Raise a clearer RuntimeError so startup stops with an informative message
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

@app.post("/chat/message")
async def save_message(json: dict):
    """Save user or assistant message"""
    message_in = MessageIn.model_validate(json)
    # ensure session exists (create if missing) to avoid foreign key violations
    session_id_str = json.get("session_id")
    if not session_id_str:
        # create a new session and attach message to it
        new_sid = await db_service.create_session()
        sid = new_sid
    else:
        sid = uuid.UUID(session_id_str)
        exists = await db_service.session_exists(sid)
        if not exists:
            # create session record with provided id so FK is satisfied
            await db_service.create_session_with_id(sid)

    await db_service.add_message(sid, json.get("role"), json.get("content"))
    # generate a simple assistant reply using retrieval
    try:
        products = await hybrid_search(json.get("content", ""), top_k=3)
    except Exception:
        products = []

    if products:
        reply = f"I found {len(products)} products that might match. Example: {products[0].get('name', '')}"
    else:
        reply = "I couldn't find matching products — can you rephrase?"

    await db_service.add_message(sid, "assistant", reply)
    return {"status": "saved", "reply": reply, "session_id": str(sid)}

@app.get("/sessions/{session_id}")
async def get_session_messages(session_id: str):
    """Retrieve all messages from a session"""
    messages = await db_service.get_session_messages(uuid.UUID(session_id))
    return {"messages": messages}

@app.get("/sessions")
async def list_sessions():
    """Get all sessions for sidebar"""
    sessions = await db_service.get_all_sessions()
    return {"sessions": sessions}

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session"""
    await db_service.delete_session(uuid.UUID(session_id))
    return {"status": "deleted"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
