# Playground-1
Projects in Claude Code

## CLI Task Manager

A simple command-line task manager built with Python and JSON storage.

### Usage

```bash
# Add tasks
python tasks.py add "Buy groceries"
python tasks.py add "Finish report" --priority high
python tasks.py add "Call dentist" --priority low --due 2026-04-01

# List tasks
python tasks.py list
python tasks.py list --pending
python tasks.py list --done

# Mark a task as done
python tasks.py done 1

# Delete a task
python tasks.py delete 2
```

### Running Tests

```bash
pytest test_tasks.py -v
```
