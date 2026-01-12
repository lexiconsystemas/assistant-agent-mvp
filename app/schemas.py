from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User input message")
    session_id: Optional[str] = Field(None, description="Client-provided session id (optional)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Extra client context")

class ChatResponse(BaseModel):
    request_id: str
    session_id: str
    reply: str

class DiscordIngestRequest(BaseModel):
    session_id: str = Field(..., description="Session ID to associate message with")
    channel_id: str = Field(..., description="Discord channel ID")
    message_id: str = Field(..., description="Discord message ID (for deduplication)")
    author: str = Field(..., description="Discord author name or ID")
    content: str = Field(..., min_length=1, description="Message content")
    ts: Optional[str] = Field(None, description="ISO timestamp (optional)")


class DiscordIngestResponse(BaseModel):
    ok: bool = Field(..., description="Success flag")
    deduped: bool = Field(..., description="True if message was already ingested")
    queued_reply: bool = Field(..., description="True if a reply was queued")
    reply_text: Optional[str] = Field(None, description="Text of reply if queued")


class DiscordInboundEvent(BaseModel):
    channel_id: str = Field(..., description="Discord channel ID")
    author: str = Field(..., description="Discord author name")
    author_id: Optional[str] = Field(None, description="Discord author ID (optional)")
    content: str = Field(..., min_length=1, description="Message content")
    message_id: str = Field(..., description="Discord message ID")
    ts: str = Field(..., description="ISO timestamp")
    raw: Dict[str, Any] = Field(default_factory=dict, description="Raw Discord message payload")


class BindDiscordChannelRequest(BaseModel):
    session_id: str = Field(..., description="Session ID to bind")
    channel_id: str = Field(..., description="Discord channel ID to bind")