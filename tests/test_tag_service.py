import pytest
from diary.models import CreateTaskRequest


class TestListAllTags:
    def test_no_tags(self, tag_service):
        assert tag_service.list_all_tags() == []

    def test_multiple_tags(self, tag_service, task_service):
        task_service.create_task(CreateTaskRequest(title="T1", tags=["backend", "auth"]))
        task_service.create_task(CreateTaskRequest(title="T2", tags=["frontend"]))
        tags = tag_service.list_all_tags()
        names = [t.name for t in tags]
        assert names == ["auth", "backend", "frontend"]  # alphabetical

    def test_tags_ordered_alphabetically(self, tag_service, task_service):
        task_service.create_task(CreateTaskRequest(title="T1", tags=["zebra", "alpha", "middle"]))
        tags = tag_service.list_all_tags()
        names = [t.name for t in tags]
        assert names == sorted(names)


class TestSetTaskTags:
    def test_set_on_empty(self, tag_service, task_service):
        task = task_service.create_task(CreateTaskRequest(title="No tags"))
        result = tag_service.set_task_tags(task.id, ["backend", "auth"])
        names = [t.name for t in result]
        assert sorted(names) == ["auth", "backend"]

    def test_replace_existing(self, tag_service, task_service):
        task = task_service.create_task(CreateTaskRequest(title="Has tags", tags=["old"]))
        result = tag_service.set_task_tags(task.id, ["new"])
        names = [t.name for t in result]
        assert names == ["new"]

    def test_reuses_existing_tag_rows(self, tag_service, task_service, db):
        task_service.create_task(CreateTaskRequest(title="T1", tags=["shared"]))
        task2 = task_service.create_task(CreateTaskRequest(title="T2"))
        tag_service.set_task_tags(task2.id, ["shared", "unique"])
        tag_count = db.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
        assert tag_count == 2  # "shared" reused, "unique" new

    def test_set_empty_removes_all(self, tag_service, task_service):
        task = task_service.create_task(CreateTaskRequest(title="Clear", tags=["a", "b"]))
        result = tag_service.set_task_tags(task.id, [])
        assert result == []

    def test_orphaned_tags_cleaned(self, tag_service, task_service, db):
        task = task_service.create_task(CreateTaskRequest(title="Only user", tags=["orphan"]))
        tag_service.set_task_tags(task.id, [])
        orphan_count = db.execute("SELECT COUNT(*) FROM tags WHERE name = 'orphan'").fetchone()[0]
        assert orphan_count == 0

    def test_nonexistent_task(self, tag_service):
        with pytest.raises(ValueError):
            tag_service.set_task_tags("nonexistent", ["tag"])

    def test_duplicate_names(self, tag_service, task_service):
        task = task_service.create_task(CreateTaskRequest(title="Dupes"))
        result = tag_service.set_task_tags(task.id, ["same", "same"])
        names = [t.name for t in result]
        assert names == ["same"]
