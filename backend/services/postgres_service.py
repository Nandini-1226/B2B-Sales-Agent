import asyncpg
import os
from typing import Optional
import uuid

class PostgresService:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Initialize connection pool when app starts"""
        db_url = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@db:5432/sales_agent"
        )
        self.pool = await asyncpg.create_pool(db_url)
    
    async def disconnect(self):
        """Close pool when app shuts down"""
        if self.pool:
            await self.pool.close()
    
    async def create_session(self, title: str = "New Chat") -> uuid.UUID:
        """Create new conversation session, return session_id"""
        session_id = uuid.uuid4()
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO sessions (session_id, title) VALUES ($1, $2)",
                session_id, title
            )
        return session_id
    
    async def add_message(self, session_id: uuid.UUID, role: str, content: str):
        """Save a message to database"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO messages (session_id, role, content) VALUES ($1, $2, $3)",
                session_id, role, content
            )
    
    async def get_session_messages(self, session_id: uuid.UUID) -> list:
        """Retrieve all messages for a session, ordered chronologically"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT role, content, created_at 
                   FROM messages 
                   WHERE session_id = $1 
                   ORDER BY created_at ASC""",
                session_id
            )
        return [dict(row) for row in rows]
    
    async def get_all_sessions(self) -> list:
        """Retrieve all session metadata (for sidebar)"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT session_id, title, created_at, updated_at 
                   FROM sessions 
                   ORDER BY created_at DESC"""
            )
        return [dict(row) for row in rows]
    
    async def delete_session(self, session_id: uuid.UUID):
        """Delete a session and all its messages"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM sessions WHERE session_id = $1",
                session_id
            )
