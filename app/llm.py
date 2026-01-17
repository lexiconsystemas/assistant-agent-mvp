import os
import time
from typing import List, Dict, Optional

# Try importing LLM providers
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


def generate_reply(user_message: str, session_id: str, history: Optional[List[Dict[str, str]]] = None) -> str:
    """
    Generate a reply using Claude (Anthropic) or OpenAI, with mock fallback.

    Environment variables:
    - ANTHROPIC_API_KEY: Claude API key (preferred)
    - OPENAI_API_KEY: OpenAI API key (fallback)
    - LLM_PROVIDER: "anthropic" or "openai" (optional, auto-detects based on keys)
    - LLM_MODEL: Model name (optional, defaults: claude-3-sonnet-20240229 or gpt-4)
    """
    provider = os.getenv("LLM_PROVIDER", "").lower()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    # Auto-detect provider if not specified
    if not provider:
        if anthropic_key and HAS_ANTHROPIC:
            provider = "anthropic"
        elif openai_key and HAS_OPENAI:
            provider = "openai"

    # Try Claude (Anthropic)
    if provider == "anthropic" and anthropic_key and HAS_ANTHROPIC:
        return _generate_with_claude(user_message, session_id, history, anthropic_key)

    # Try OpenAI
    if provider == "openai" and openai_key and HAS_OPENAI:
        return _generate_with_openai(user_message, session_id, history, openai_key)

    # Fallback to mock
    return _generate_mock(user_message, session_id, history)


def _generate_with_claude(
    user_message: str,
    session_id: str,
    history: Optional[List[Dict[str, str]]],
    api_key: str
) -> str:
    """Generate reply using Claude (Anthropic)."""
    try:
        client = anthropic.Anthropic(api_key=api_key)
        model = os.getenv("LLM_MODEL", "claude-3-haiku-20240307")

        # Build messages array from history
        messages = []
        if history:
            for msg in history:
                if msg.get("role") in ("user", "assistant"):
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })

        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })

        # System prompt for personal assistant
        system_prompt = """You are a helpful personal assistant. You help the user manage their tasks, reminders, and daily check-ins.

Be conversational, friendly, and concise. Keep responses brief (1-3 sentences) unless the user asks for more detail.

The user can:
- Add tasks: "add task [title]" or "todo [title]"
- Complete tasks: "complete [task_id]"
- List tasks: "list tasks" or "my tasks"
- Add reminders: "remind me to [text]" or "remind me in X minutes to [text]"
- Check in: "check in: mood=happy energy=7 focus=6 note=text"
- View dashboard: "today" or "dashboard"

For general conversation, be helpful and supportive."""

        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=system_prompt,
            messages=messages
        )

        return response.content[0].text

    except Exception as e:
        print(f"[LLM ERROR] Claude failed: {e}")
        return _generate_mock(user_message, session_id, history)


def _generate_with_openai(
    user_message: str,
    session_id: str,
    history: Optional[List[Dict[str, str]]],
    api_key: str
) -> str:
    """Generate reply using OpenAI."""
    try:
        client = openai.OpenAI(api_key=api_key)
        model = os.getenv("LLM_MODEL", "gpt-4")

        # Build messages array from history
        messages = [{
            "role": "system",
            "content": """You are a helpful personal assistant. You help the user manage their tasks, reminders, and daily check-ins.

Be conversational, friendly, and concise. Keep responses brief (1-3 sentences) unless the user asks for more detail.

The user can:
- Add tasks: "add task [title]" or "todo [title]"
- Complete tasks: "complete [task_id]"
- List tasks: "list tasks" or "my tasks"
- Add reminders: "remind me to [text]" or "remind me in X minutes to [text]"
- Check in: "check in: mood=happy energy=7 focus=6 note=text"
- View dashboard: "today" or "dashboard"

For general conversation, be helpful and supportive."""
        }]

        if history:
            for msg in history:
                if msg.get("role") in ("user", "assistant"):
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })

        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=1024
        )

        return response.choices[0].message.content

    except Exception as e:
        print(f"[LLM ERROR] OpenAI failed: {e}")
        return _generate_mock(user_message, session_id, history)


def _generate_mock(user_message: str, session_id: str, history: Optional[List[Dict[str, str]]]) -> str:
    """Mock LLM fallback for testing without API keys."""
    time.sleep(0.05)

    text = user_message.strip()
    if not text:
        return "Say something and I'll respond."

    last_user = None
    if history:
        for m in reversed(history):
            if m.get("role") == "user":
                last_user = m.get("content")
                break

    if last_user and last_user != text:
        return f"[MOCK LLM] (session={session_id}) Earlier you said: '{last_user}'. Now you said: '{text}'."

    return f"[MOCK LLM] (session={session_id}) Replying to: {text}"
