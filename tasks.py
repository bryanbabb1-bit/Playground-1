#!/usr/bin/env python3
import argparse
import sys
from task_store import add_task, complete_task, delete_task, list_tasks

# ANSI colors
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
DIM = "\033[2m"
RESET = "\033[0m"

PRIORITY_COLORS = {"high": RED, "medium": YELLOW, "low": DIM}


def format_task(task):
    check = f"{GREEN}[x]{RESET}" if task["done"] else "[ ]"
    pri = task.get("priority", "medium")
    pri_color = PRIORITY_COLORS.get(pri, "")
    pri_label = f"{pri_color}({pri}){RESET}"
    due = f" due:{task['due']}" if task.get("due") else ""
    title = f"{DIM}{task['title']}{RESET}" if task["done"] else task["title"]
    return f"  {check} {task['id']:>3}. {title} {pri_label}{due}"


def cmd_add(args):
    task = add_task(args.title, priority=args.priority, due=args.due)
    print(f"Added task {task['id']}: {task['title']}")


def cmd_list(args):
    filter_status = None
    if args.done:
        filter_status = "done"
    elif args.pending:
        filter_status = "pending"

    tasks = list_tasks(filter_status=filter_status)
    if not tasks:
        print("No tasks found.")
        return

    print()
    for task in tasks:
        print(format_task(task))
    print()
    done_count = sum(1 for t in tasks if t["done"])
    print(f"  {done_count}/{len(tasks)} completed")


def cmd_done(args):
    task = complete_task(args.id)
    if task:
        print(f"Completed: {task['title']}")
    else:
        print(f"Task {args.id} not found.", file=sys.stderr)
        sys.exit(1)


def cmd_delete(args):
    task = delete_task(args.id)
    if task:
        print(f"Deleted: {task['title']}")
    else:
        print(f"Task {args.id} not found.", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="CLI Task Manager")
    sub = parser.add_subparsers(dest="command")

    # add
    p_add = sub.add_parser("add", help="Add a new task")
    p_add.add_argument("title", help="Task description")
    p_add.add_argument("--priority", choices=["low", "medium", "high"], default="medium")
    p_add.add_argument("--due", help="Due date (e.g. 2026-04-01)")
    p_add.set_defaults(func=cmd_add)

    # list
    p_list = sub.add_parser("list", help="List tasks")
    p_list.add_argument("--done", action="store_true", help="Show only completed tasks")
    p_list.add_argument("--pending", action="store_true", help="Show only pending tasks")
    p_list.set_defaults(func=cmd_list)

    # done
    p_done = sub.add_parser("done", help="Mark a task as done")
    p_done.add_argument("id", type=int, help="Task ID")
    p_done.set_defaults(func=cmd_done)

    # delete
    p_del = sub.add_parser("delete", help="Delete a task")
    p_del.add_argument("id", type=int, help="Task ID")
    p_del.set_defaults(func=cmd_delete)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
