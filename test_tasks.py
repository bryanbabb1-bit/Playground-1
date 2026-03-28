import os
import tempfile
import pytest
from task_store import add_task, complete_task, delete_task, list_tasks, load_tasks


@pytest.fixture
def tmp_file():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.unlink(path)  # start with no file
    yield path
    if os.path.exists(path):
        os.unlink(path)


def test_add_task(tmp_file):
    task = add_task("Buy groceries", filepath=tmp_file)
    assert task["id"] == 1
    assert task["title"] == "Buy groceries"
    assert task["done"] is False
    assert task["priority"] == "medium"


def test_add_multiple_tasks(tmp_file):
    add_task("Task 1", filepath=tmp_file)
    task2 = add_task("Task 2", filepath=tmp_file)
    assert task2["id"] == 2
    assert len(load_tasks(tmp_file)) == 2


def test_complete_task(tmp_file):
    add_task("Finish report", filepath=tmp_file)
    result = complete_task(1, filepath=tmp_file)
    assert result["done"] is True
    tasks = load_tasks(tmp_file)
    assert tasks[0]["done"] is True


def test_complete_nonexistent_task(tmp_file):
    assert complete_task(999, filepath=tmp_file) is None


def test_delete_task(tmp_file):
    add_task("Temporary task", filepath=tmp_file)
    deleted = delete_task(1, filepath=tmp_file)
    assert deleted["title"] == "Temporary task"
    assert len(load_tasks(tmp_file)) == 0


def test_delete_nonexistent_task(tmp_file):
    assert delete_task(999, filepath=tmp_file) is None


def test_list_filter_done(tmp_file):
    add_task("Done task", filepath=tmp_file)
    add_task("Pending task", filepath=tmp_file)
    complete_task(1, filepath=tmp_file)

    done = list_tasks(filter_status="done", filepath=tmp_file)
    assert len(done) == 1
    assert done[0]["title"] == "Done task"

    pending = list_tasks(filter_status="pending", filepath=tmp_file)
    assert len(pending) == 1
    assert pending[0]["title"] == "Pending task"

    all_tasks = list_tasks(filepath=tmp_file)
    assert len(all_tasks) == 2


def test_add_with_priority_and_due(tmp_file):
    task = add_task("Urgent thing", priority="high", due="2026-04-01", filepath=tmp_file)
    assert task["priority"] == "high"
    assert task["due"] == "2026-04-01"
