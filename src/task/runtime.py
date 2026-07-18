from __future__ import annotations

from typing import Any

from src.common.fc_event import parse_fc_event
from src.common.logger import get_logger

logger = get_logger(__name__)


def detect_invoke_source(evt: Any) -> str:
    if not isinstance(evt, dict):
        return "unknown"
    if evt.get("__invoke_source"):
        return str(evt.get("__invoke_source"))
    if evt.get("httpMethod") or evt.get("rawPath") or evt.get("path"):
        return "fc_http"
    if "payload" in evt:
        return "fc_timer"
    return "plain_payload"


def try_record_scheduled_task_execution(payload: Any, invoke_source: str) -> None:
    if not isinstance(payload, dict):
        return
    task_id = payload.get("__scheduled_task_id")
    task_name = payload.get("__scheduled_task_name")
    if task_id is None and not task_name:
        return
    try:
        from src.scheduled_task_manager import ScheduledTaskRepository

        repo = ScheduledTaskRepository()
        resolved_id = None
        if task_id is not None:
            try:
                resolved_id = int(task_id)
            except Exception:
                resolved_id = None
        if resolved_id is None and task_name:
            try:
                candidates = repo.list_tasks(include_deleted=False)
                for item in candidates:
                    if str(item.get("task_name") or "") == str(task_name):
                        resolved_id = int(item.get("task_id"))
                        break
            except Exception:
                resolved_id = None
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
    try_record_scheduled_task_execution(payload, invoke_source)
    return evt, payload, invoke_source

