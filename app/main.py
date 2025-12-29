import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, Request

from app.schemas import ChatRequest, ChatResponse
from app.logging_middleware import RequestLoggingMiddleware
from app.memory import store
from app.llm import generate_reply

load_dotenv()

app = FastAPI(title="Assistant Agent MVP", version="0.2.0")
app.add_middleware(RequestLoggingMiddleware)


load_dotenv()

app = FastAPI(title="Assistant Agent MVP", version="0.1.0")

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "assistant-agent-mvp",
        "env": os.getenv("APP_ENV", "dev"),
    }
@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    msgs = store.snapshot(session_id=session_id, limit=50)
    return {
        "session_id": session_id,
        "messages": [{"role": m.role, "content": m.content, "ts": m.ts} for m in msgs],
    }


@app.delete("/sessions/{session_id}")
def clear_session(session_id: str):
    store.clear(session_id=session_id)
    return {"status": "cleared", "session_id": session_id}
    
    
@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request):
    # request_id from middleware
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    # prefer payload.session_id, else existing session_id (middleware/header), else generate
    session_id = payload.session_id or getattr(request.state, "session_id", None) or str(uuid.uuid4())
    request.state.session_id = session_id

    normalized_text = payload.message.strip()

    # 1) load recent history BEFORE storing this message
    history_msgs = store.get_history(session_id=session_id, limit=12)
    history = [{"role": m.role, "content": m.content} for m in history_msgs]

    # 2) store user message
    store.append(session_id=session_id, role="user", content=normalized_text)

    # 3) generate reply using history
    reply = generate_reply(normalized_text, session_id=session_id, history=history)

    # 4) store assistant reply
    store.append(session_id=session_id, role="assistant", content=reply)

    return ChatResponse(
        request_id=request_id,
        session_id=session_id,
        reply=reply,
    )



    return ChatResponse(
        request_id=request_id,
        session_id=session_id,
        reply=reply
    )