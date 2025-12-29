from app.tools import run_tool
from app.llm import generate_reply
from app.memory import store

def handle_message(text: str, session_id: str):
    lower = text.lower().strip()

    # ADD TASK
    if lower.startswith(("add task", "todo", "remember to")):
        title = text.split(" ", 2)[-1] if lower.startswith("add task") else text.split(" ", 1)[-1]
        result = run_tool("add_task", session_id, {"title": title})
        return f"Task added: {title}"

    # LIST TASKS
    if "list tasks" in lower or "my tasks" in lower:
        result = run_tool("list_tasks", session_id, {})
        if not result["tasks"]:
            return "You have no tasks."
        return "\n".join(
            [f"{t['id']} | {'✓' if t['completed'] else '•'} {t['title']}" for t in result["tasks"]]
        )

    # COMPLETE TASK
    if lower.startswith("complete"):
        task_id = text.split()[-1]
        result = run_tool("complete_task", session_id, {"task_id": task_id})
        return "Task completed." if result["ok"] else "Task not found."

    # FALLBACK: LLM
    history = [{"role": m.role, "content": m.content}
               for m in store.get_history(session_id, limit=12)]

    return generate_reply(text, session_id=session_id, history=history)
