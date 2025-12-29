import os
import time

SYSTEM_PROMPT = (
    "You are an assistant agent MVP. Be concise, accurate, and helpful. "
    "If you don't know something, say so."
)

def generate_reply(user_message: str, session_id: str | None = None) -> str:
    """
    MOCK LLM: deterministic, cheap, and testable.
    Keeps the same interface we'll use when swapping to a real provider.
    """
    mode = os.getenv("LLM_MODE", "mock").lower()

    # Simulate a little inference latency so you can feel timing/logging behavior
    time.sleep(0.05)

    if mode != "mock":
        # Future-proofing: this is where provider routing would go.
        # For now, always behave as mock.
        pass

    text = user_message.strip()

    # Tiny bit of "assistant behavior" so it doesn't feel like pure echo.
    if not text:
        return "Say something and I’ll respond."

    if len(text) > 500:
        return "That’s a lot of text. For now, keep it under 500 characters."

    # Simple structured response
    return f"[MOCK LLM] Session={session_id or 'none'} | Replying to: {text}"
