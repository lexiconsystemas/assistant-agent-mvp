import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, Request

from app.agent import handle_message
from app.schemas import ChatRequest, ChatResponse
from app.logging_middleware import RequestLoggingMiddleware
from app.memory import store

load_dotenv()

app = FastAPI(title="Assistant Agent MVP", version="0.2.0")
app.add_middleware(RequestLoggingMiddleware)


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


@app.get("/sessions/{session_id}/tasks")
def get_tasks(session_id: str):
    tasks = store.list_tasks(session_id=session_id)
    return {
        "session_id": session_id,
        "tasks": [t.__dict__ for t in tasks],
    }


@app.delete("/sessions/{session_id}")
def clear_session(session_id: str):
    store.clear(session_id=session_id)
    return {"status": "cleared", "session_id": session_id}


@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    session_id = payload.session_id or getattr(request.state, "session_id", None) or str(uuid.uuid4())
    request.state.session_id = session_id

    normalized_text = payload.message.strip()

    # store user message once
    store.append(session_id=session_id, role="user", content=normalized_text)

    # agent decides tool vs llm
    reply = handle_message(normalized_text, session_id)

    # store assistant once
    store.append(session_id=session_id, role="assistant", content=reply)

    return ChatResponse(
        request_id=request_id,
        session_id=session_id,
        reply=reply,
    )
