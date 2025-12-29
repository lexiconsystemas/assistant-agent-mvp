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
