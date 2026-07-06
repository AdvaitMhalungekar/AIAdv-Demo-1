"""
FastAPI server for PrimeNest Realty Chatbot.
Serves the REST API and static frontend files.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import database as db
import agent

# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and seed data on first run."""
    db.initialize_database()
    if not db.is_database_seeded():
        json_path = os.path.join(os.path.dirname(__file__), "real_estate_demo_dataset.json")
        if os.path.exists(json_path):
            db.load_data_from_json(json_path)
            print("[OK] Database initialized and seeded.")
        else:
            print("[WARN] JSON dataset not found. Database will be empty.")
    else:
        print("[OK] Database already seeded.")
    yield

# ─── App Setup ────────────────────────────────────────────────────────────────

app = FastAPI(title="PrimeNest Realty Chatbot", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request/Response Models ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: int
    message: str

class ChatResponse(BaseModel):
    response: str
    session_id: int

class CreateSessionRequest(BaseModel):
    title: Optional[str] = "New Chat"


# ─── API Endpoints ───────────────────────────────────────────────────────────

@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    """Send a message and get the AI response."""
    try:
        response = agent.chat(req.session_id, req.message)
        return ChatResponse(response=response, session_id=req.session_id)
    except Exception as e:
        print(f"[ERROR] Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions")
def list_sessions():
    """Get all chat sessions."""
    sessions = db.get_all_sessions()
    return {"sessions": sessions}


@app.post("/api/sessions")
def create_session(req: CreateSessionRequest):
    """Create a new chat session."""
    session_id = db.create_chat_session(req.title)
    return {"session_id": session_id, "title": req.title}


@app.get("/api/sessions/{session_id}/messages")
def get_messages(session_id: int):
    """Get all messages for a session."""
    messages = db.get_session_messages(session_id, limit=100)
    return {"messages": messages}


@app.delete("/api/sessions/{session_id}")
def delete_session_endpoint(session_id: int):
    """Delete a session and its messages."""
    db.delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}


# ─── Static Files ────────────────────────────────────────────────────────────

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def serve_frontend():
    """Serve the main HTML page."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "PrimeNest Realty Chatbot API is running. Place static files in /static directory."}


# ─── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
