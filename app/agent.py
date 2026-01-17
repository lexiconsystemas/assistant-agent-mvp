from app.tools import run_tool
from app.llm import generate_reply
from app.memory import store
import re


def handle_message(text: str, session_id: str):
    msg = text.strip()
    # normalize internal spacing for robust parsing (but preserve original `text`/`msg` for outputs)
    msg_norm = re.sub(r"\s+", " ", msg)
    lower = msg_norm.lower()

    # ADD TASK
    if lower.startswith(("add task", "todo", "remember to")):
        title = text.split(" ", 2)[-1] if lower.startswith("add task") else text.split(" ", 1)[-1]
        result = run_tool("add_task", session_id, {"title": title})
        return f"Task added: {title}"

    # REMINDERS: regex-based parsing for robustness
    if lower.startswith("remind me"):
        # Timed: "remind me in N minutes to X" (N may be negative)
        m = re.match(r"^\s*remind\s+me\s+in\s+([+-]?\d+)\s+minutes?\s+to\s+(.+?)\s*$", msg_norm, re.IGNORECASE)
        if m:
            try:
                minutes = int(m.group(1))
                text_after = m.group(2).strip(" .!?")
                result = run_tool("add_reminder", session_id, {"text": text_after, "minutes": minutes})
                return f"Reminder set in {minutes} minutes: {text_after}"
            except Exception:
                pass

        # Untimed: "remind me to X"
        m2 = re.match(r"^\s*remind\s+me\s+to\s+(.+?)\s*$", msg_norm, re.IGNORECASE)
        if m2:
            text_after = m2.group(1).strip(" .!?")
            result = run_tool("add_reminder", session_id, {"text": text_after})
            return f"Reminder set: {text_after}"

    # LIST REMINDERS
    if "list reminders" in lower or "my reminders" in lower:
        res = run_tool("list_reminders", session_id, {})
        if not res.get("reminders"):
            return "You have no reminders."
        return "\n".join([f"{r['id']} | {'✓' if r['completed'] else '•'} {r['text']} (due {r['due_ts']})" for r in res["reminders"]])

    # COMPLETE REMINDER (explicit)
    m_rem = re.match(r"^\s*complete\s+reminder\s+(\S+)\s*$", msg_norm, re.IGNORECASE)
    if m_rem:
        rid = m_rem.group(1)
        res = run_tool("complete_reminder", session_id, {"reminder_id": rid})
        return "Reminder completed." if res.get("ok") else "Reminder not found."

    # CHECK-IN: "check in: mood=happy energy=7 focus=6 note=Did stuff"
    if lower.startswith("check in"):
        # accept both 'check in:' and 'check in '
        # attempt key=value parsing
        rest = text.split("check in", 1)[-1].strip(" :")
        parts = [p.strip() for p in rest.split() if p.strip()]
        kv = {}
        for p in parts:
            if "=" in p:
                k, v = p.split("=", 1)
                kv[k.strip().lower()] = v.strip()
        mood = kv.get("mood", "ok")
        energy = int(kv.get("energy", 5))
        focus = int(kv.get("focus", 5))
        note = kv.get("note", "")
        res = run_tool("check_in", session_id, {"mood": mood, "energy": energy, "focus": focus, "note": note})
        return "Check-in recorded." if res.get("ok") else "Failed to record check-in."

    # DASHBOARD / TODAY
    if lower in ("today", "dashboard", "what's my plan", "whats my plan"):
        res = run_tool("today_summary", session_id, {})
        last = res.get("last_checkin")
        last_s = f"last check-in mood={last['mood']} energy={last['energy']}" if last else "no recent check-in"
        return f"Open tasks: {res.get('open_tasks')} | Open reminders: {res.get('open_reminders')} | {last_s}"

    # LIST TASKS
    if "list tasks" in lower or "my tasks" in lower:
        result = run_tool("list_tasks", session_id, {})
        if not result["tasks"]:
            return "You have no tasks."
        return "\n".join(
            [f"{t['id']} | {'✓' if t['completed'] else '•'} {t['title']}" for t in result["tasks"]]
        )

    # COMPLETE TASK (but not 'complete reminder')
    m_task = re.match(r"^\s*complete\s+(\S+)\s*$", text, re.IGNORECASE)
    if m_task:
        task_id = m_task.group(1)
        # ensure this wasn't the 'complete reminder' case already handled
        if not re.match(r"^reminder$", task_id, re.IGNORECASE):
            result = run_tool("complete_task", session_id, {"task_id": task_id})
            return "Task completed." if result.get("ok") else "Task not found."

    # FALLBACK: LLM
    history = [{"role": m["role"], "content": m["content"]}
               for m in store.get_history(session_id, limit=12)]

    return generate_reply(text, session_id=session_id, history=history)


def handle_inbound(text: str, session_id: str, source: str = "discord") -> str:
    """Handle inbound messages from external channels.

    This delegates to `handle_message` for now but provides a seam for
    future channel-specific behavior (different prompts, routing, etc.).
    """
    return handle_message(text, session_id)
