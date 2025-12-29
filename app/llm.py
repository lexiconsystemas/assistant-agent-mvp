import time
from typing import List, Dict, Optional

def generate_reply(user_message: str, session_id: str, history: Optional[List[Dict[str, str]]] = None) -> str:
    """
    MOCK LLM with context support.
    Later this becomes OpenAI/Claude without changing your API layer.
    """
    time.sleep(0.05)

    text = user_message.strip()
    if not text:
        return "Say something and I’ll respond."

    last_user = None
    if history:
        for m in reversed(history):
            if m.get("role") == "user":
                last_user = m.get("content")
                break

    if last_user and last_user != text:
        return f"[MOCK LLM] (session={session_id}) Earlier you said: '{last_user}'. Now you said: '{text}'."

    return f"[MOCK LLM] (session={session_id}) Replying to: {text}"
