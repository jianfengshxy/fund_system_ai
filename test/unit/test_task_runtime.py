from __future__ import annotations

import types

from src.task import runtime


class FakeRepository:
    def __init__(self, *, tasks=None):
        self.tasks = tasks or []
        self.updated = []

    def get_task_by_name(self, task_name):
        for item in self.tasks:
            if item.get("task_name") == task_name:
                return item
        return None

    def list_tasks(self, include_deleted=False):
        return list(self.tasks)

    def update_execution_result(self, task_id, status, error_message=None):
        self.updated.append((task_id, status, error_message))


def test_detect_invoke_source_variants():
    assert runtime.detect_invoke_source({"httpMethod": "POST"}) == "fc_http"
    assert runtime.detect_invoke_source({"payload": {}}) == "fc_timer"
    assert runtime.detect_invoke_source({"foo": "bar"}) == "plain_payload"
    assert runtime.detect_invoke_source("raw") == "unknown"


def test_parse_strategy_event_records_by_task_name(monkeypatch):
    repo = FakeRepository(tasks=[{"task_id": 101, "task_name": "daily-sync"}])
    fake_module = types.SimpleNamespace(ScheduledTaskRepository=lambda: repo)
    monkeypatch.setitem(__import__("sys").modules, "src.scheduled_task_manager", fake_module)

    evt, payload, invoke_source = runtime.parse_strategy_event(
        {"payload": {"__scheduled_task_name": "daily-sync", "fund_code": "000001"}},
        "demo_action",
    )

    assert invoke_source == "fc_timer"
    assert payload["fund_code"] == "000001"
    assert repo.updated == [(101, "SUCCESS", None)]


def test_parse_strategy_event_records_by_fc_trigger_and_function(monkeypatch):
    repo = FakeRepository(
        tasks=[
            {
                "task_id": 202,
                "task_name": "local-name",
                "fc_trigger_name": "remote-trigger",
                "policy": "unused",
                "fc_function_name": "task.daily_task",
            }
        ]
    )
    fake_module = types.SimpleNamespace(ScheduledTaskRepository=lambda: repo)
    monkeypatch.setitem(__import__("sys").modules, "src.scheduled_task_manager", fake_module)

    runtime.parse_strategy_event(
        {
            "triggerName": "remote-trigger",
            "functionName": "task.daily_task",
            "payload": {"biz": "sync"},
        },
        "demo_action",
    )

    assert repo.updated == [(202, "SUCCESS", None)]


def test_try_record_scheduled_task_execution_ignores_missing_identity(monkeypatch):
    repo = FakeRepository()
    fake_module = types.SimpleNamespace(ScheduledTaskRepository=lambda: repo)
    monkeypatch.setitem(__import__("sys").modules, "src.scheduled_task_manager", fake_module)

    runtime.try_record_scheduled_task_execution({}, {}, "plain_payload")

    assert repo.updated == []
