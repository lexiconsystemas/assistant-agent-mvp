from typing import Dict, Any
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

TOOLS = {
    "add_task": add_task_tool,
    "list_tasks": list_tasks_tool,
    "complete_task": complete_task_tool,
}

def run_tool(name: str, session_id: str, args: Dict[str, Any]):
    fn = TOOLS.get(name)
    if not fn:
        return {"ok": False, "error": f"Unknown tool {name}"}
    return fn(session_id, args)
