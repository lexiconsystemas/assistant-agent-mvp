from typing import Dict, Any
from datetime import datetime, timezone, timedelta
from app.memory import store

def add_task_tool(session_id: str, args: Dict[str, Any]):
    title = args.get("title")
    if not title:
        return {"ok": False, "error": "Missing task title"}
    task = store.add_task(session_id, title)
    return {"ok": True, "task": task.__dict__}

def list_tasks_tool(session_id: str, args: Dict[str, Any]):
    tasks = store.list_tasks(session_id)
    return {"tasks": [t.__dict__ for t in tasks]}

def complete_task_tool(session_id: str, args: Dict[str, Any]):
    task_id = args.get("task_id")
    if not task_id:
        return {"ok": False, "error": "Missing task_id"}
    success = store.complete_task(session_id, task_id)
    return {"ok": success}


def add_reminder_tool(session_id: str, args: Dict[str, Any]):
    text = args.get("text") or args.get("title")
    minutes = args.get("minutes")
    due_ts = args.get("due_ts")
    if not text:
        return {"ok": False, "error": "Missing reminder text"}
    if minutes is not None:
        try:
            minutes = int(minutes)
            due_dt = datetime.now(timezone.utc) + timedelta(minutes=minutes)
            due_ts = due_dt.isoformat()
        except Exception:
            return {"ok": False, "error": "Invalid minutes"}

    reminder = store.add_reminder(session_id, text=text, due_ts=due_ts)
    return {"ok": True, "reminder": reminder.__dict__}


def list_reminders_tool(session_id: str, args: Dict[str, Any]):
    reminders = store.list_reminders(session_id)
    return {"reminders": [r.__dict__ for r in reminders]}


def complete_reminder_tool(session_id: str, args: Dict[str, Any]):
    reminder_id = args.get("reminder_id")
    if not reminder_id:
        return {"ok": False, "error": "Missing reminder_id"}
    ok = store.complete_reminder(session_id, reminder_id)
    return {"ok": ok}


def check_in_tool(session_id: str, args: Dict[str, Any]):
    mood = args.get("mood", "ok")
    energy = int(args.get("energy", 5))
    focus = int(args.get("focus", 5))
    note = args.get("note", "")
    chk = store.add_checkin(session_id, mood=mood, energy=energy, focus=focus, note=note)
    return {"ok": True, "checkin": chk.__dict__}


def today_summary_tool(session_id: str, args: Dict[str, Any]):
    tasks = store.list_tasks(session_id)
    reminders = store.list_reminders(session_id)
    checkins = store.list_checkins(session_id, limit=1)
    open_tasks = sum(1 for t in tasks if not t.completed)
    open_reminders = sum(1 for r in reminders if not r.completed)
    last_checkin = checkins[-1].__dict__ if checkins else None
    return {"open_tasks": open_tasks, "open_reminders": open_reminders, "last_checkin": last_checkin}

TOOLS = {
    "add_task": add_task_tool,
    "list_tasks": list_tasks_tool,
    "complete_task": complete_task_tool,
    "add_reminder": add_reminder_tool,
    "list_reminders": list_reminders_tool,
    "complete_reminder": complete_reminder_tool,
    "check_in": check_in_tool,
    "today_summary": today_summary_tool,
}

def run_tool(name: str, session_id: str, args: Dict[str, Any]):
    fn = TOOLS.get(name)
    if not fn:
        return {"ok": False, "error": f"Unknown tool {name}"}
    return fn(session_id, args)
