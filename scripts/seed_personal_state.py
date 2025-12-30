"""
Seed personal session state for proactive testing.

This script talks to a RUNNING assistant-agent-mvp server over HTTP using
`requests`. It POSTs conversational messages to `/chat` to create a session
and add tasks, reminders, and a check-in so the `/sessions/{session_id}/proactive`
endpoint can be exercised.

Run from the repository root after starting the server (uvicorn):

        python -m pip install requests
        uvicorn app.main:app --reload --port 8000
        python scripts/seed_personal_state.py

Simulation profile (how it mimics a real day):
- 3 tasks: one completed (already done), two open — simulates a backlog.
- 2 reminders: one overdue (missed), one future — simulates actionable items.
- 1 check-in: mood/energy/focus + note — simulates a recent user status update.
"""

import requests
from datetime import datetime, timedelta, timezone


BASE = "http://127.0.0.1:8000"


def post_chat(message: str, session_id: str | None = None):
    payload = {"message": message}
    if session_id:
        payload["session_id"] = session_id
    r = requests.post(f"{BASE}/chat", json=payload)
    r.raise_for_status()
    return r.json()


def get_json(path: str):
    r = requests.get(f"{BASE}{path}")
    r.raise_for_status()
    return r.json()


def main():
    # 1) create session via /chat
    print("Posting initial hello to /chat to create a session...")
    res = post_chat("hello")
    session_id = res.get("session_id")
    print("session_id:", session_id)

    # 2) add 3 tasks
    post_chat("add task Buy groceries", session_id=session_id)
    post_chat("add task Walk the dog", session_id=session_id)
    post_chat("add task Finish report", session_id=session_id)

    # get tasks and complete one
    tasks = get_json(f"/sessions/{session_id}/tasks").get("tasks", [])
    if tasks:
        first_id = tasks[0]["id"]
        post_chat(f"complete {first_id}", session_id=session_id)

    # 3) add 2 reminders (one overdue, one future)
    # use negative minutes to create an overdue reminder
    post_chat("remind me in -1440 minutes to Provider appointment", session_id=session_id)
    post_chat("remind me in 2880 minutes to Call back client", session_id=session_id)

    # 4) add 1 check-in
    post_chat("check in: mood=content energy=7 focus=6 note=Had a productive morning", session_id=session_id)

    # 5) fetch proactive
    proactive = get_json(f"/sessions/{session_id}/proactive")
    print("Proactive response:", proactive)

    print("\nSeeding complete. session_id:", session_id)


if __name__ == "__main__":
    print("Ensure the server is running: uvicorn app.main:app --reload --port 8000")
    main()
