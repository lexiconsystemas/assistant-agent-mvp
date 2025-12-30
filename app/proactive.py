from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app import memory

# Proactive outreach helper (Day 6)
# Uses the in-memory `store` where available. The code is defensive when
# optional APIs are not present: it will treat missing lists as empty.


def proactive_prompt(session_id: str) -> Optional[str]:
    """Return a short proactive message for a session or None.

        Logic:
            1) If no check-in exists for TODAY (local date) => return
                 "Quick check-in: mood? energy (1-10)? focus (1-10)?"
      2) If any reminders are overdue (due_ts < now UTC and not completed) =>
         return "You have X overdue reminders. Want to review them?"
      3) If open tasks >= 3 => return "You have X open tasks. Want to pick one to focus on?"
      else return None

    Notes:
      - This function expects the global `store` in `app.memory` to provide
        `list_checkins`, `list_reminders`, and `list_tasks`. If any are missing
        the function treats them as empty lists (non-fatal).

    Minimal self-check examples (expected outputs):
      #1 No check-ins at all -> returns greeting string
      #2 One overdue reminder -> "You have 1 overdue reminders. Want to review them?"
      #3 Three open tasks -> "You have 3 open tasks. Want to pick one to focus on?"
    """

    store = memory.store
    now = datetime.now(timezone.utc)

    # 1) check-ins: if no check-in for today's local date, prompt user
    try:
        checkins = store.list_checkins(session_id=session_id)
    except AttributeError:
        checkins = []

    # determine if any checkin exists with local date == today
    today_local = datetime.now().date()
    has_today = False
    for c in checkins:
        ts = None
        if isinstance(c, dict):
            ts = c.get("ts")
        else:
            ts = getattr(c, "ts", None)
        if not ts:
            continue
        try:
            c_dt = datetime.fromisoformat(ts)
        except Exception:
            continue
        if c_dt.tzinfo is None:
            # assume UTC if no tz
            c_dt = c_dt.replace(tzinfo=timezone.utc)
        # convert to local timezone then compare date
        try:
            local_date = c_dt.astimezone().date()
        except Exception:
            local_date = c_dt.date()
        if local_date == today_local:
            has_today = True
            break

    if not has_today:
        return "Quick check-in: mood? energy (1-10)? focus (1-10)?"

    # 2) reminders overdue
    overdue_count = 0
    try:
        reminders = store.list_reminders(session_id=session_id)
    except AttributeError:
        reminders = []

    for r in reminders:
        # support both dict-like and attr-like objects
        due_ts = None
        completed = False
        if isinstance(r, dict):
            due_ts = r.get("due_ts") or r.get("due")
            completed = r.get("completed", False)
        else:
            due_ts = getattr(r, "due_ts", None) or getattr(r, "due", None)
            completed = getattr(r, "completed", False)

        if not due_ts:
            continue
        try:
            due_dt = datetime.fromisoformat(due_ts)
        except Exception:
            # ignore unparsable timestamps
            continue

        # ensure tz-aware comparison
        if due_dt.tzinfo is None:
            due_dt = due_dt.replace(tzinfo=timezone.utc)

        if (due_dt < now) and (not completed):
            overdue_count += 1

    if overdue_count > 0:
        return f"You have {overdue_count} overdue reminders. Want to review them?"

    # 3) open tasks >= 3
    try:
        tasks = store.list_tasks(session_id=session_id)
    except AttributeError:
        tasks = []

    open_tasks = 0
    for t in tasks:
        if isinstance(t, dict):
            completed = t.get("completed", False)
        else:
            completed = getattr(t, "completed", False)
        if not completed:
            open_tasks += 1

    if open_tasks >= 3:
        return f"You have {open_tasks} open tasks. Want to pick one to focus on?"

    return None
