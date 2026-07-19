from __future__ import annotations

from typing import Any

from src.common.fc_event import parse_fc_event
from src.common.logger import get_logger

logger = get_logger(__name__)


def detect_invoke_source(evt: Any) -> str:
    """Best-effort detection of how a task handler was invoked."""
    if not isinstance(evt, dict):
        return "unknown"
    if evt.get("__invoke_source"):
        return str(evt.get("__invoke_source"))
    if evt.get("httpMethod") or evt.get("rawPath") or evt.get("path"):
        return "fc_http"
    if "payload" in evt:
        return "fc_timer"
    return "plain_payload"


def _to_int(raw_value: Any) -> int | None:
    try:
        if raw_value is None or raw_value == "":
            return None
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def _string_candidates(*values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, dict):
            continue
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _extract_task_identity(evt: dict[str, Any], payload: dict[str, Any]) -> tuple[int | None, list[str], list[str]]:
    headers = evt.get("headers", {}) if isinstance(evt.get("headers"), dict) else {}
    trigger_meta = evt.get("triggerMeta", {}) if isinstance(evt.get("triggerMeta"), dict) else {}

    task_id = _to_int(payload.get("__scheduled_task_id"))
    if task_id is None:
        task_id = _to_int(evt.get("__scheduled_task_id"))

    task_names = _string_candidates(
        payload.get("__scheduled_task_name"),
        evt.get("__scheduled_task_name"),
        payload.get("task_name"),
        evt.get("task_name"),
        evt.get("triggerName"),
        evt.get("trigger_name"),
        trigger_meta.get("triggerName"),
        headers.get("x-fc-trigger-name"),
    )
    function_names = _string_candidates(
        payload.get("policy"),
        evt.get("policy"),
        evt.get("functionName"),
        evt.get("function_name"),
        trigger_meta.get("functionName"),
        headers.get("x-fc-function-name"),
    )
    return task_id, task_names, function_names


def _resolve_scheduled_task_id(
    repo: Any,
    *,
    task_id: int | None,
    task_names: list[str],
    function_names: list[str],
) -> int | None:
    if task_id is not None:
        return task_id

    for task_name in task_names:
        task = repo.get_task_by_name(task_name)
        if task and task.get("task_id") is not None:
            return int(task["task_id"])

    if not task_names and not function_names:
        return None

    candidates = repo.list_tasks(include_deleted=False)
    task_name_set = set(task_names)
    function_name_set = set(function_names)
    for item in candidates:
        if str(item.get("task_name") or "") in task_name_set:
            return int(item["task_id"])
        if str(item.get("fc_trigger_name") or "") in task_name_set:
            return int(item["task_id"])
        if str(item.get("policy") or "") in function_name_set:
            return int(item["task_id"])
        if str(item.get("fc_function_name") or "") in function_name_set:
            return int(item["task_id"])
    return None


def try_record_scheduled_task_execution(evt: Any, payload: Any, invoke_source: str) -> None:
    if not isinstance(payload, dict):
        payload = {}
    if not isinstance(evt, dict):
        evt = {}

    task_id, task_names, function_names = _extract_task_identity(evt, payload)
    if task_id is None and not task_names and not function_names:
        return

    try:
        from src.scheduled_task_manager import ScheduledTaskRepository

        repo = ScheduledTaskRepository()
        resolved_id = _resolve_scheduled_task_id(
            repo,
            task_id=task_id,
            task_names=task_names,
            function_names=function_names,
        )
        if resolved_id is None:
            return
        repo.update_execution_result(resolved_id, "SUCCESS", error_message=None)
        logger.info(
            f"[scheduled_task] 执行记录已回写 task_id={resolved_id} source={invoke_source}",
            extra={"action": "scheduled_task", "invoke_source": invoke_source},
        )
    except Exception as exc:
        logger.error(
            f"[scheduled_task] 回写执行记录失败: {exc}",
            extra={"action": "scheduled_task", "invoke_source": invoke_source},
        )


def parse_strategy_event(event: Any, action: str):
    evt, payload = parse_fc_event(event)
    invoke_source = detect_invoke_source(evt)
    logger.info(
        f"[{action}] 入口调用来源: {invoke_source}",
        extra={"action": action, "invoke_source": invoke_source},
    )
    try_record_scheduled_task_execution(evt, payload, invoke_source)
    return evt, payload, invoke_source
