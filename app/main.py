import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.agent import handle_message
from app.schemas import ChatRequest, ChatResponse, DiscordIngestRequest, DiscordIngestResponse, DiscordInboundEvent, BindDiscordChannelRequest
from app.logging_middleware import RequestLoggingMiddleware
from app.memory import store, InboundMessage
from app.proactive import proactive_prompt
from app.tools import run_tool
from datetime import datetime, timezone

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


@app.get("/sessions/{session_id}/proactive")
def get_proactive(session_id: str):
    """Return a small proactive outreach message or null.

    Response shape: {"message": <string or null>}
    """
    msg = proactive_prompt(session_id=session_id)
    return {"message": msg}


@app.get("/sessions/{session_id}/reminders")
def get_reminders(session_id: str):
    reminders = store.list_reminders(session_id=session_id)
    return {"session_id": session_id, "reminders": [r.__dict__ for r in reminders]}


@app.get("/sessions/{session_id}/checkins")
def get_checkins(session_id: str):
    c = store.list_checkins(session_id=session_id)
    return {"session_id": session_id, "checkins": [ck.__dict__ for ck in c]}


@app.get("/sessions/{session_id}/dashboard")
def get_dashboard(session_id: str):
    # use the today_summary tool for consistent business logic
    res = run_tool("today_summary", session_id, {})
    return {"session_id": session_id, "dashboard": res}


@app.post("/sessions/{session_id}/proactive/tick")
def proactive_tick(session_id: str):
    """Run proactive evaluation once and queue an outbound message if needed.

    Returns: {"queued": bool, "message": <string or null>}
    """
    msg = proactive_prompt(session_id=session_id)
    if not msg:
        return {"queued": False, "message": None}

    # avoid duplicate spam: if last outbox message has same text within 60 minutes, skip
    last = None
    out = store.list_outbox(session_id=session_id, limit=1)
    if out:
        last = out[-1]
    if last:
        try:
            last_ts = datetime.fromisoformat(last.ts)
            if last.text == msg and (datetime.now(timezone.utc) - last_ts).total_seconds() < 3600:
                return {"queued": False, "message": None}
        except Exception:
            pass

    queued = store.add_outbox(session_id=session_id, text=msg, reason="proactive_tick")
    return {"queued": True, "message": queued.text}


@app.get("/sessions/{session_id}/outbox")
def get_outbox(session_id: str):
    msgs = store.list_outbox(session_id=session_id)
    return {"session_id": session_id, "outbox": [m.__dict__ for m in msgs]}


@app.post("/sessions/{session_id}/outbox/{message_id}/delivered")
def outbox_delivered(session_id: str, message_id: str):
    """Mark an outbox message delivered.

    Returns {"ok": true/false}
    """
    ok = store.mark_delivered(session_id=session_id, message_id=message_id)
    return {"ok": bool(ok)}


@app.post("/sessions/{session_id}/outbox/{message_id}/attempt")
def outbox_attempt(session_id: str, message_id: str):
    """Increment attempt counter for an outbox message.

    Returns {"ok": true/false, "attempts": <int|null>}
    """
    attempts = store.increment_outbox_attempt(session_id=session_id, message_id=message_id)
    if attempts < 0:
        return {"ok": False, "attempts": None}
    return {"ok": True, "attempts": attempts}


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


@app.post("/integrations/discord/ingest", response_model=DiscordIngestResponse)
async def discord_ingest(payload: DiscordIngestRequest, request: Request):
    """Ingest a Discord message: store inbound, run agent, queue reply.

    Handles deduplication via message_id to prevent repeated processing.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    session_id = payload.session_id
    request.state.session_id = session_id

    # Deduplication check
    if store.has_inbound_id(session_id, payload.message_id):
        print(f"[DISCORD] request_id={request_id} session_id={session_id} deduped message_id={payload.message_id}")
        return DiscordIngestResponse(ok=True, deduped=True, queued_reply=False, reply_text=None)

    # Store inbound message
    store.add_inbound(
        session_id=session_id,
        author=payload.author,
        text=payload.content,
        source="discord",
        channel_id=payload.channel_id,
        inbound_id=payload.message_id,
    )

    # Append to chat history as user message
    store.append(session_id=session_id, role="user", content=payload.content)

    # Run agent routing
    reply_text = handle_message(payload.content, session_id)

    # Store assistant reply and queue to outbox if present
    store.append(session_id=session_id, role="assistant", content=reply_text)
    
    queued_reply = False
    if reply_text and reply_text.strip():
        store.add_outbox(session_id=session_id, text=reply_text, reason="discord_reply")
        queued_reply = True

    print(f"[DISCORD] request_id={request_id} session_id={session_id} ingested message_id={payload.message_id} queued_reply={queued_reply}")

    return DiscordIngestResponse(
        ok=True,
        deduped=False,
        queued_reply=queued_reply,
        reply_text=reply_text if queued_reply else None,
    )


@app.post("/sessions/{session_id}/bindings/discord")
async def bind_discord_channel(session_id: str, payload: BindDiscordChannelRequest, request: Request):
    """Bind a Discord channel to a session.

    Returns: {"ok": true}
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    request.state.session_id = session_id

    store.bind_discord_channel(session_id=session_id, channel_id=payload.channel_id)
    print(f"[BIND] request_id={request_id} session_id={session_id} bound to discord channel={payload.channel_id}")

    return {"ok": True}


@app.post("/integrations/discord/inbound")
async def ingest_inbound_discord(payload: DiscordInboundEvent, request: Request):
    """Ingest an inbound Discord message.

    Resolves session_id from bindings OR accepts hardcoded session (MVP).
    Creates InboundMessage, stores it, updates last activity, calls agent, and queues reply.

    Returns: {"ok": bool, "session_id": str, "ingested": bool, "reply_text": optional[str]}
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    # MVP: hardcode or lookup session by channel binding
    # For now, lookup via channel_id binding (requires pre-bind call)
    session_id = None
    # In a real system, iterate through bindings to find session by channel_id
    # For MVP, we'll accept an optional query param or environment var
    session_id = os.getenv("DISCORD_SESSION_ID", None)
    
    if not session_id:
        print(f"[INBOUND] request_id={request_id} no session_id configured (set DISCORD_SESSION_ID env var)")
        return {"ok": False, "session_id": None, "ingested": False, "reply_text": None}

    request.state.session_id = session_id

    # Check for duplicate
    if store.has_inbound_id(session_id, payload.message_id):
        print(f"[INBOUND] request_id={request_id} session_id={session_id} deduped message_id={payload.message_id}")
        return {"ok": True, "session_id": session_id, "ingested": False, "reply_text": None}

    # Create and store inbound message
    msg = InboundMessage(
        id=payload.message_id,
        source="discord",
        author=payload.author,
        text=payload.content.strip(),
        ts=payload.ts,
        raw=payload.raw or {},
    )
    store.append_inbound(session_id=session_id, msg=msg)
    store.set_last_user_activity(session_id=session_id, ts_iso=payload.ts)

    print(f"[INBOUND] request_id={request_id} session_id={session_id} stored message_id={payload.message_id} from {payload.author}")

    # Call agent to generate reply
    reply_text = handle_message(payload.content, session_id)

    # Queue reply if present
    queued_reply = False
    if reply_text and reply_text.strip():
        store.add_outbox(session_id=session_id, text=reply_text, reason="inbound_discord_reply")
        queued_reply = True
        print(f"[INBOUND] request_id={request_id} session_id={session_id} queued reply: {reply_text[:60]}...")

    return {
        "ok": True,
        "session_id": session_id,
        "ingested": True,
        "reply_text": reply_text if queued_reply else None,
    }


@app.get("/sessions/{session_id}/inbox")
def get_inbox(session_id: str):
    """Debug endpoint: list inbound messages for a session.

    Returns: {"session_id": str, "inbox": []}
    """
    msgs = store.list_inbound(session_id=session_id, limit=50)
    return {
        "session_id": session_id,
        "inbox": [{"id": m.id, "source": m.source, "author": m.author, "text": m.text, "ts": m.ts} for m in msgs],
    }


app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")
