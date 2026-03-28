import json
import os
from datetime import datetime

DEFAULT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks.json")


def load_tasks(filepath=DEFAULT_FILE):
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r") as f:
        return json.load(f)


def save_tasks(tasks, filepath=DEFAULT_FILE):
    with open(filepath, "w") as f:
        json.dump(tasks, f, indent=2)


def _next_id(tasks):
    if not tasks:
        return 1
    return max(t["id"] for t in tasks) + 1


def add_task(title, priority="medium", due=None, filepath=DEFAULT_FILE):
    tasks = load_tasks(filepath)
    task = {
        "id": _next_id(tasks),
        "title": title,
        "done": False,
        "priority": priority,
        "due": due,
        "created": datetime.now().isoformat(),
    }
    tasks.append(task)
    save_tasks(tasks, filepath)
    return task


def complete_task(task_id, filepath=DEFAULT_FILE):
    tasks = load_tasks(filepath)
    for task in tasks:
        if task["id"] == task_id:
            task["done"] = True
            save_tasks(tasks, filepath)
            return task
    return None


def delete_task(task_id, filepath=DEFAULT_FILE):
    tasks = load_tasks(filepath)
    for i, task in enumerate(tasks):
        if task["id"] == task_id:
            removed = tasks.pop(i)
            save_tasks(tasks, filepath)
            return removed
    return None


def list_tasks(filter_status=None, filepath=DEFAULT_FILE):
    tasks = load_tasks(filepath)
    if filter_status == "done":
        return [t for t in tasks if t["done"]]
    elif filter_status == "pending":
        return [t for t in tasks if not t["done"]]
    return tasks
