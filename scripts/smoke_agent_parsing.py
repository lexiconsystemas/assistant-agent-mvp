#!/usr/bin/env python3
"""
Minimal smoke test for agent parsing (regex-based reminders/completions).

Runs the agent routing function directly against an in-memory store.
No HTTP, no frameworks, no external deps.
"""

import sys
from pathlib import Path

# Ensure repo root is on PYTHONPATH BEFORE importing app
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import uuid
from datetime import datetime, timezone

from app.agent import handle_message
from app import memory


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_attr(obj, key):
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key)


def find_reminder_by_text(reminders, text):
    for r in reminders:
        if get_attr(r, "text") == text:
            return r
    return None


def run_tests():
    store = memory.store
    sid = str(uuid.uuid4())
    failures = []

    # Helper: create reminder through agent so we don't touch private store fields
    def create_reminder(msg: str, expected_text: str):
        resp = handle_message(msg, sid)
        if not isinstance(resp, str):
            failures.append((msg, f"handle_message returned non-str: {type(resp)}"))
        rems = store.list_reminders(sid)
        r = find_reminder_by_text(rems, expected_text)
        return r

    # 1) timed reminder 15 minutes
    inp = "remind me in 15 minutes to buy milk"
    r = create_reminder(inp, "buy milk")
    if not r:
        failures.append((inp, "reminder not created"))
    else:
        due_ts = get_attr(r, "due_ts")
        due = datetime.fromisoformat(due_ts)
        delta_min = (due - datetime.now(timezone.utc)).total_seconds() / 60.0
        if not (13 <= delta_min <= 17):
            failures.append((inp, f"due delta minutes={delta_min:.2f} not ~15"))

    # 2) negative minutes overdue
    inp = "remind me in -5 minutes to test overdue"
    r = create_reminder(inp, "test overdue")
    if not r:
        failures.append((inp, "reminder not created"))
    else:
        due_ts = get_attr(r, "due_ts")
        due = datetime.fromisoformat(due_ts)
        if not (due < datetime.now(timezone.utc)):
            failures.append((inp, "due time not in past"))

    # 3) untimed reminder
    inp = "remind me to call mom"
    r = create_reminder(inp, "call mom")
    if not r:
        failures.append((inp, "reminder not created"))

    # 4) complete reminder <id> (use real created reminder id)
    seed_msg = "remind me to seed"
    seed_rem = create_reminder(seed_msg, "seed")
    if not seed_rem:
        failures.append((seed_msg, "seed reminder not created"))
    else:
        rid = get_attr(seed_rem, "id")
        inp = f"complete reminder {rid}"
        handle_message(inp, sid)
        rems = store.list_reminders(sid)
        updated = None
        for rr in rems:
            if get_attr(rr, "id") == rid:
                updated = rr
                break
        if not updated or not get_attr(updated, "completed"):
            failures.append((inp, "reminder not marked completed"))

    # 5) complete task <id> (use real created task id)
    task_msg = "add task smoke task"
    handle_message(task_msg, sid)
    tasks = store.list_tasks(sid)
    task = next((t for t in tasks if get_attr(t, "title") == "smoke task"), None)
    if not task:
        failures.append((task_msg, "task not created"))
    else:
        tid = get_attr(task, "id")
        inp = f"complete {tid}"
        handle_message(inp, sid)
        tasks2 = store.list_tasks(sid)
        updated_t = next((t for t in tasks2 if get_attr(t, "id") == tid), None)
        if not updated_t or not get_attr(updated_t, "completed"):
            failures.append((inp, "task not marked completed"))

    # 6) extra spacing
    inp = "remind    me    in   10   minutes   to   stretch"
    r = create_reminder(inp, "stretch")
    if not r:
        failures.append((inp, "reminder not created with spaced input"))

    # Report
    if failures:
        for inp, reason in failures:
            print(f"[FAIL] {inp} -> {reason}")
        return 2

    print("[PASS] all parsing smoke tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_tests())
