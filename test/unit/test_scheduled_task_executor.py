from __future__ import annotations

import sys
import types

from src.scheduled_tasks import executor


def test_build_internal_event_prefers_raw_payload():
    event = executor._build_internal_event({"raw_payload": {"fund_code": "000001"}})

    assert event["payload"] == {"fund_code": "000001"}
    assert event["__invoke_source"] == "python_scheduler"


def test_resolve_task_callable_prefers_handler_module(monkeypatch):
    fake_module = types.SimpleNamespace(run=lambda event, context: None)
    monkeypatch.setattr(executor.importlib, "import_module", lambda module_path: fake_module)

    target = executor._resolve_task_callable({"policy": "unused", "handler": "src.task.demo.run"})

    assert target is fake_module.run


def test_execute_task_callable_falls_back_to_index(monkeypatch):
    called = {}

    def fake_handler(event, context):
        called["event"] = event
        called["context"] = context

    monkeypatch.setitem(sys.modules, "index", types.SimpleNamespace(daily_task=fake_handler))
    monkeypatch.setattr(executor.importlib, "import_module", lambda module_path: (_ for _ in ()).throw(ImportError("boom")))

    result = executor.execute_task_callable(
        {"task_name": "daily", "policy": "daily_task", "handler": "src.task.missing.handler"},
        {"fund_code": "000001"},
    )

    assert result["success"] is True
    assert called["event"]["payload"] == {"fund_code": "000001"}
    assert called["context"] is None


def test_execute_task_callable_returns_failed_status(monkeypatch):
    def fake_handler(event, context):
        raise RuntimeError("handler exploded")

    monkeypatch.setitem(sys.modules, "index", types.SimpleNamespace(daily_task=fake_handler))
    monkeypatch.setattr(executor.importlib, "import_module", lambda module_path: (_ for _ in ()).throw(ImportError("boom")))

    result = executor.execute_task_callable(
        {"task_name": "daily", "policy": "daily_task", "handler": ""},
        {"fund_code": "000001"},
    )

    assert result["success"] is False
    assert result["status"] == "FAILED"
    assert "handler exploded" in result["error_message"]
