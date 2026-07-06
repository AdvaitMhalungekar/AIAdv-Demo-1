"""
FastAPI server for PrimeNest Realty Chatbot.
Serves the REST API and static frontend files.
"""

import os
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
import database as db
import agent
import voice_agent

load_dotenv(override=True)

# ─── Retell AI Setup ─────────────────────────────────────────────────────────

try:
    from retell import Retell
    RETELL_API_KEY = os.getenv("RETELL_API_KEY", "")
    RETELL_AGENT_ID = os.getenv("RETELL_AGENT_ID", "")
    TWILIO_FROM_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "").replace(" ", "")
    retell_client = Retell(api_key=RETELL_API_KEY) if RETELL_API_KEY else None
    if retell_client:
        print(f"[OK] Retell AI client initialized (agent: {RETELL_AGENT_ID[:8]}...)")
    else:
        print("[WARN] No RETELL_API_KEY found. Voice calling will be unavailable.")
except ImportError:
    retell_client = None
    RETELL_AGENT_ID = ""
    TWILIO_FROM_NUMBER = ""
    print("[WARN] retell-sdk not installed. Voice calling will be unavailable.")

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

class CallRequest(BaseModel):
    phone_number: str


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


# ─── Voice Call Endpoints ────────────────────────────────────────────────────

def _format_indian_phone(raw: str) -> str:
    """Normalize an Indian phone number to E.164 format (+91XXXXXXXXXX)."""
    digits = re.sub(r'\D', '', raw)
    # If they entered full number with country code
    if digits.startswith('91') and len(digits) == 12:
        return f'+{digits}'
    # If they entered 10-digit mobile number
    if len(digits) == 10:
        return f'+91{digits}'
    raise ValueError(f"Invalid Indian mobile number: {raw}")


@app.post("/api/request-call")
def request_call(req: CallRequest):
    """Initiate an outbound voice call to the user via Retell AI + Twilio."""
    if not retell_client:
        raise HTTPException(
            status_code=503,
            detail="Voice calling is not configured. Please set RETELL_API_KEY in .env"
        )

    if not RETELL_AGENT_ID:
        raise HTTPException(
            status_code=503,
            detail="No RETELL_AGENT_ID configured. Please set it in .env"
        )

    # Validate and format phone number
    try:
        to_number = _format_indian_phone(req.phone_number)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Initiate the call via Retell SDK
    try:
        call_response = retell_client.call.create_phone_call(
            from_number=TWILIO_FROM_NUMBER,
            to_number=to_number,
            override_agent_id=RETELL_AGENT_ID,
        )
        print(f"[CALL] Initiated call to {to_number}, call_id={call_response.call_id}")
        return {
            "success": True,
            "call_id": call_response.call_id,
            "message": "Call initiated! Your phone will ring shortly."
        }
    except Exception as e:
        print(f"[ERROR] Failed to initiate call: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to initiate call: {str(e)}")


@app.get("/api/call-status/{call_id}")
def get_call_status(call_id: str):
    """Check the status of a voice call."""
    if not retell_client:
        raise HTTPException(status_code=503, detail="Voice calling is not configured.")

    try:
        call = retell_client.call.retrieve(call_id)
        return {
            "call_id": call.call_id,
            "status": call.call_status,
            "start_timestamp": getattr(call, 'start_timestamp', None),
            "end_timestamp": getattr(call, 'end_timestamp', None),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Retell Custom LLM WebSocket ─────────────────────────────────────────────

@app.websocket("/llm-websocket/{call_id}")
async def retell_llm_websocket(websocket: WebSocket, call_id: str):
    """WebSocket endpoint that Retell AI connects to during active calls (prefixed path)."""
    print(f"[VOICE] Incoming WebSocket connection for call: {call_id}")
    await voice_agent.handle_retell_websocket(websocket)


@app.websocket("/{call_id}")
async def retell_llm_websocket_direct(websocket: WebSocket, call_id: str):
    """WebSocket endpoint that Retell AI connects to if the base URL was configured at root."""
    # Only handle it as a voice call websocket if it is a call ID
    if call_id.startswith("call_"):
        print(f"[VOICE] Incoming WebSocket connection for direct call: {call_id}")
        await voice_agent.handle_retell_websocket(websocket)
    else:
        await websocket.close(code=1008)



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
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000, 
        ws_ping_interval=300, 
        ws_ping_timeout=300
    )
