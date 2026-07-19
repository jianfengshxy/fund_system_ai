from __future__ import annotations

import importlib
import traceback
from datetime import datetime
from typing import Any

from src.common.logger import get_logger

logger = get_logger(__name__)


def _build_internal_event(payload: Any) -> dict[str, Any]:
    """
    统一内部事件格式，兼容原先 FC handler 的入参风格。

    老的 FC 定时触发器会把业务参数放在 `payload` 字段里；
    新的 Python 调度器也继续沿用这个约定，并附带来源元信息，
    方便 `index.py` 在逐步迁移期间同时兼容两种调用方式。
    """
    if isinstance(payload, dict) and "raw_payload" in payload:
        normalized_payload = payload["raw_payload"]
    else:
        normalized_payload = payload
    return {
        "payload": normalized_payload,
        "__invoke_source": "python_scheduler",
        "__invoke_mode": "internal_scheduled_task",
    }


def _resolve_task_callable(task: dict[str, Any]):
    """
    统一解析数据库任务对应的可执行函数。

    这里仍然桥接到 `index.py` 中原本给 FC 定时触发器使用的函数，
    这样后台调度器和“立即执行”按钮都会走同一个入口，避免两套调用链不一致。
    """
    function_name = str(task.get("policy") or "").strip()
    handler_name = str(task.get("handler") or "").strip()

    target = _import_callable(handler_name)
    if target is not None:
        return target

    import index as index_module

    target = getattr(index_module, function_name, None)
    if target is None and handler_name:
        target = getattr(index_module, handler_name.split(".")[-1], None)
    if target is None or not callable(target):
        raise AttributeError(f"未找到可执行函数: policy={function_name}, handler={handler_name}")
    return target


def _import_callable(dotted_path: str):
    """Resolve `module.attr` handler paths declared in scheduled task configs."""
    if not dotted_path or "." not in dotted_path:
        return None

    module_path, attr_name = dotted_path.rsplit(".", 1)
    try:
        module = importlib.import_module(module_path)
    except Exception as exc:
        logger.warning("导入任务模块失败 handler=%s err=%s", dotted_path, exc)
        return None

    target = getattr(module, attr_name, None)
    if callable(target):
        return target

    logger.warning("任务模块中未找到可调用对象 handler=%s", dotted_path)
    return None


def execute_task_callable(task: dict[str, Any], payload: Any) -> dict[str, Any]:
    """同步执行一个定时任务，并返回结构化执行结果。"""
    started_at = datetime.now()
    try:
        target = _resolve_task_callable(task)
        target(_build_internal_event(payload), None)
        finished_at = datetime.now()
        return {
            "success": True,
            "status": "SUCCESS",
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
            "error_message": None,
            "source": "task_executor",
        }
    except Exception as exc:
        finished_at = datetime.now()
        error_message = f"{exc}\n{traceback.format_exc()}"
        logger.error(f"定时任务执行失败 task={task.get('task_name')}: {error_message}")
        return {
            "success": False,
            "status": "FAILED",
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
            "error_message": error_message,
            "source": "task_executor",
        }
