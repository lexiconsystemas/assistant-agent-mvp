from app.llm import generate_reply
from fastapi import FastAPI, Request
from dotenv import load_dotenv
import os
import uuid

from app.schemas import ChatRequest, ChatResponse
from app.logging_middleware import RequestLoggingMiddleware

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
    
@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request):
    # request_id from middleware
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    # prefer payload.session_id, else header x-session-id, else generate
    session_id = payload.session_id or getattr(request.state, "session_id", None) or str(uuid.uuid4())
    request.state.session_id = session_id  # keep consistent for logs/headers

    # Single pipeline (placeholder response for now)
    normalized_text = payload.message.strip()

    # For Day 2, we just echo in a controlled way
    #reply = f"Received: {normalized_text}"
    reply = generate_reply(normalized_text, session_id=session_id)


    return ChatResponse(
        request_id=request_id,
        session_id=session_id,
        reply=reply
    )