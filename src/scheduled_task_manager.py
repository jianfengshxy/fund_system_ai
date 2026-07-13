from __future__ import annotations

import calendar
import copy
import json
import os
import re
import threading
import time
import traceback
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from src.common.logger import get_logger
from src.db.database_connection import DatabaseConnection
from src.scheduled_tasks.executor import execute_task_callable

logger = get_logger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_TIMEZONE = "Asia/Shanghai"
VAR_REF_PATTERN = re.compile(r"^\$\{([^}]+)\}$")
EVERY_PATTERN = re.compile(r"^@every\s+(\d+(?:\.\d+)?)(ns|us|µs|ms|s|m|h)$", re.IGNORECASE)
MONTH_ALIASES = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}
DAY_ALIASES = {
    "SUN": 0,
    "MON": 1,
    "TUE": 2,
    "WED": 3,
    "THU": 4,
    "FRI": 5,
    "SAT": 6,
}


def _now_local(tz_name: str = DEFAULT_TIMEZONE) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def _ensure_datetime_string(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _normalize_bool(value: Any) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if value else 0
    if isinstance(value, str):
        return 1 if value.strip().lower() in {"1", "true", "yes", "on"} else 0
    return 0


def _normalize_payload_for_storage(payload: Any) -> str | None:
    if payload is None:
        return None
    if isinstance(payload, str):
        stripped = payload.strip()
        if not stripped:
            return None
        try:
            parsed = json.loads(stripped)
            return json.dumps(parsed, ensure_ascii=False, sort_keys=True)
        except Exception:
            return stripped
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _parse_payload(payload: Any) -> Any:
    if payload is None:
        return {}
    if isinstance(payload, (dict, list)):
        return payload
    if isinstance(payload, str):
        stripped = payload.strip()
        if not stripped:
            return {}
        try:
            return json.loads(stripped)
        except Exception:
            return {"raw_payload": payload}
    return payload


def _split_cron_expression(expression: str) -> tuple[str, str]:
    expr = (expression or "").strip()
    timezone = DEFAULT_TIMEZONE
    if expr.startswith("CRON_TZ="):
        parts = expr.split(None, 1)
        timezone = parts[0].split("=", 1)[1]
        expr = parts[1].strip() if len(parts) > 1 else ""
    return timezone or DEFAULT_TIMEZONE, expr


def _resolve_var_reference(document: dict[str, Any], ref_path: str) -> Any:
    current: Any = document
    for part in ref_path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        raise KeyError(f"无法解析变量引用: {ref_path}")
    return copy.deepcopy(current)


def resolve_s_yaml_value(document: dict[str, Any], value: Any) -> Any:
    if isinstance(value, str):
        match = VAR_REF_PATTERN.match(value.strip())
        if match:
            return resolve_s_yaml_value(document, _resolve_var_reference(document, match.group(1)))
        return value
    if isinstance(value, dict):
        return {key: resolve_s_yaml_value(document, item) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_s_yaml_value(document, item) for item in value]
    return value


def load_s_yaml_document(file_path: str | None = None) -> dict[str, Any]:
    target = file_path or os.path.join(PROJECT_ROOT, "s.yaml")
    with open(target, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def parse_s_yaml_to_task_entries(file_path: str | None = None) -> list[dict[str, Any]]:
    document = load_s_yaml_document(file_path=file_path)
    resources = document.get("resources", {}) or {}
    entries: list[dict[str, Any]] = []
    used_task_names: set[str] = set()

    for resource_name, resource_body in resources.items():
        props = resolve_s_yaml_value(document, (resource_body or {}).get("props", {}) or {})
        function_name = props.get("functionName") or resource_name
        handler = props.get("handler") or ""
        triggers = props.get("triggers", []) or []

        for index, trigger in enumerate(triggers):
            trigger_body = resolve_s_yaml_value(document, trigger or {})
            trigger_config = trigger_body.get("triggerConfig", {}) or {}
            trigger_type = trigger_body.get("triggerType") or ""
            original_trigger_name = trigger_body.get("triggerName") or f"{resource_name}_{index}"
            task_name = str(original_trigger_name).strip()
            if task_name in used_task_names:
                task_name = f"{task_name}__{function_name}"
            if task_name in used_task_names:
                task_name = f"{task_name}__{resource_name}_{index + 1}"
            used_task_names.add(task_name)
            payload = trigger_config.get("payload")
            description = (
                f"从 s.yaml 迁移: resource={resource_name}, "
                f"function={function_name}, trigger={original_trigger_name}, type={trigger_type}"
            )

            entries.append(
                {
                    "task_name": task_name,
                    "cron_expression": str(trigger_config.get("cronExpression") or "").strip(),
                    "policy": str(function_name).strip(),
                    "handler": str(handler).strip(),
                    "payload": _normalize_payload_for_storage(payload),
                    "description": description,
                    "is_enabled": _normalize_bool(trigger_config.get("enable", 0)),
                    "is_deleted": 0,
                }
            )

    return entries


def _parse_atom(token: str, alias_map: dict[str, int] | None = None) -> int:
    normalized = token.strip().upper()
    if alias_map and normalized in alias_map:
        return alias_map[normalized]
    return int(normalized)


def _match_field(
    value: int,
    expression: str,
    min_value: int,
    max_value: int,
    alias_map: dict[str, int] | None = None,
) -> bool:
    expr = expression.strip().upper()
    if expr in {"*", "?"}:
        return True
    for part in expr.split(","):
        item = part.strip()
        if not item:
            continue
        if "/" in item:
            start_expr, step_expr = item.split("/", 1)
            step = int(step_expr)
            if start_expr in {"*", "?"}:
                start = min_value
                end = max_value
            elif "-" in start_expr:
                left, right = start_expr.split("-", 1)
                start = _parse_atom(left, alias_map)
                end = _parse_atom(right, alias_map)
            else:
                start = _parse_atom(start_expr, alias_map)
                end = max_value
            if start <= value <= end and (value - start) % step == 0:
                return True
            continue
        if item == "L":
            if value == max_value:
                return True
            continue
        if "-" in item:
            left, right = item.split("-", 1)
            start = _parse_atom(left, alias_map)
            end = _parse_atom(right, alias_map)
            if start <= value <= end:
                return True
            continue
        if value == _parse_atom(item, alias_map):
            return True
    return False


def _business_weekday(dt: datetime) -> int:
    weekday = dt.weekday()
    return 0 if weekday == 6 else weekday + 1


def _last_day_of_month(dt: datetime) -> int:
    return calendar.monthrange(dt.year, dt.month)[1]


def _cron_fields(expression: str) -> tuple[str, list[str]]:
    timezone, raw_expr = _split_cron_expression(expression)
    parts = raw_expr.split()
    if len(parts) == 5:
        parts = ["0"] + parts
    if len(parts) == 7:
        parts = parts[:6]
    if len(parts) != 6:
        raise ValueError(f"不支持的 cron 表达式: {expression}")
    return timezone, parts


def cron_matches(dt: datetime, expression: str) -> bool:
    _timezone, fields = _cron_fields(expression)
    second, minute, hour, day_of_month, month, day_of_week = fields

    if not _match_field(dt.second, second, 0, 59):
        return False
    if not _match_field(dt.minute, minute, 0, 59):
        return False
    if not _match_field(dt.hour, hour, 0, 23):
        return False
    if day_of_month.strip().upper() == "L":
        day_match = dt.day == _last_day_of_month(dt)
    else:
        day_match = _match_field(dt.day, day_of_month, 1, 31)
    if not day_match:
        return False
    if not _match_field(dt.month, month, 1, 12, MONTH_ALIASES):
        return False
    # 兼容当前业务中的 1-5 工作日写法，数字星期按 1=周一...6=周六, 0/7=周日 处理。
    if not _match_field(_business_weekday(dt), day_of_week, 0, 7, DAY_ALIASES):
        return False
    return True


def _parse_every_expression(expression: str) -> tuple[str, timedelta] | None:
    timezone, raw_expr = _split_cron_expression(expression)
    match = EVERY_PATTERN.match(raw_expr)
    if not match:
        return None
    amount = float(match.group(1))
    unit = match.group(2).lower()
    if unit == "ns":
        delta = timedelta(microseconds=amount / 1000.0)
    elif unit in {"us", "µs"}:
        delta = timedelta(microseconds=amount)
    elif unit == "ms":
        delta = timedelta(milliseconds=amount)
    elif unit == "s":
        delta = timedelta(seconds=amount)
    elif unit == "m":
        delta = timedelta(minutes=amount)
    else:
        delta = timedelta(hours=amount)
    return timezone, delta


def compute_next_run(expression: str, from_time: datetime | None = None) -> datetime:
    every_config = _parse_every_expression(expression)
    if every_config:
        timezone, delta = every_config
        base = (from_time or _now_local(timezone)).astimezone(ZoneInfo(timezone))
        return base + delta

    timezone, _fields = _cron_fields(expression)
    current = (from_time or _now_local(timezone)).astimezone(ZoneInfo(timezone))
    probe = current.replace(microsecond=0) + timedelta(seconds=1)
    deadline = probe + timedelta(days=400)
    while probe <= deadline:
        if cron_matches(probe, expression):
            return probe
        probe += timedelta(seconds=1)
    raise ValueError(f"在允许范围内未找到下一次执行时间: {expression}")


def build_task_response(task: dict[str, Any], next_run_at: datetime | None = None, cron_error: str | None = None) -> dict[str, Any]:
    result = dict(task)
    for key, value in list(result.items()):
        result[key] = _ensure_datetime_string(value)
    result["is_enabled"] = bool(result.get("is_enabled"))
    result["is_deleted"] = bool(result.get("is_deleted"))
    result["payload_object"] = _parse_payload(result.get("payload"))
    result["next_run_at"] = next_run_at.isoformat() if next_run_at else None
    result["cron_error"] = cron_error
    return result


class ScheduledTaskRepository:
    def __init__(self) -> None:
        self.db = DatabaseConnection()

    def _fetch_all(self, sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        return self.db.execute_query(sql, params or ())

    def _fetch_one(self, sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
        rows = self.db.execute_query(sql, params)
        return rows[0] if rows else None

    def list_tasks(self, include_deleted: bool = False) -> list[dict[str, Any]]:
        sql = """
            SELECT task_id, task_name, cron_expression, policy, handler, payload, description,
                   is_enabled, last_executed_at, last_executed_status, last_error_message,
                   created_at, updated_at, is_deleted
            FROM scheduled_tasks
        """
        params: list[Any] = []
        if not include_deleted:
            sql += " WHERE is_deleted = %s"
            params.append(0)
        sql += " ORDER BY task_id ASC"
        return self._fetch_all(sql, tuple(params))

    def get_task(self, task_id: int) -> dict[str, Any] | None:
        sql = """
            SELECT task_id, task_name, cron_expression, policy, handler, payload, description,
                   is_enabled, last_executed_at, last_executed_status, last_error_message,
                   created_at, updated_at, is_deleted
            FROM scheduled_tasks
            WHERE task_id = %s
            LIMIT 1
        """
        return self._fetch_one(sql, (task_id,))

    def create_task(self, data: dict[str, Any]) -> dict[str, Any]:
        sql = """
            INSERT INTO scheduled_tasks (
                task_name, cron_expression, policy, handler, payload, description,
                is_enabled, last_executed_at, last_executed_status, last_error_message,
                created_at, updated_at, is_deleted
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, NULL, NULL, NOW(), NOW(), %s)
        """
        task_id = self.db.insert(
            sql,
            (
                data["task_name"],
                data["cron_expression"],
                data["policy"],
                data["handler"],
                _normalize_payload_for_storage(data.get("payload")),
                data.get("description"),
                _normalize_bool(data.get("is_enabled", 1)),
                _normalize_bool(data.get("is_deleted", 0)),
            ),
        )
        created = self.get_task(int(task_id))
        if created is None:
            raise ValueError("创建任务后未能读取任务记录")
        return created

    def update_task(self, task_id: int, data: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "task_name": "task_name",
            "cron_expression": "cron_expression",
            "policy": "policy",
            "handler": "handler",
            "payload": "payload",
            "description": "description",
            "is_enabled": "is_enabled",
            "is_deleted": "is_deleted",
        }
        set_clauses: list[str] = []
        params: list[Any] = []
        for key, column_name in allowed.items():
            if key not in data:
                continue
            value = data[key]
            if key == "payload":
                value = _normalize_payload_for_storage(value)
            if key in {"is_enabled", "is_deleted"}:
                value = _normalize_bool(value)
            set_clauses.append(f"{column_name} = %s")
            params.append(value)
        if not set_clauses:
            current = self.get_task(task_id)
            if current is None:
                raise ValueError("任务不存在")
            return current

        params.extend([task_id])
        sql = f"""
            UPDATE scheduled_tasks
            SET {", ".join(set_clauses)}, updated_at = NOW()
            WHERE task_id = %s
        """
        self.db.update(sql, tuple(params))
        updated = self.get_task(task_id)
        if updated is None:
            raise ValueError("更新任务后未能读取任务记录")
        return updated

    def soft_delete_task(self, task_id: int) -> dict[str, Any] | None:
        self.db.update(
            """
            UPDATE scheduled_tasks
            SET is_deleted = 1, updated_at = NOW()
            WHERE task_id = %s
            """,
            (task_id,),
        )
        return self.get_task(task_id)

    def update_execution_result(
        self,
        task_id: int,
        status: str,
        error_message: str | None = None,
        executed_at: datetime | None = None,
    ) -> None:
        executed = (executed_at or _now_local()).replace(tzinfo=None)
        self.db.update(
            """
            UPDATE scheduled_tasks
            SET last_executed_at = %s,
                last_executed_status = %s,
                last_error_message = %s,
                updated_at = NOW()
            WHERE task_id = %s
            """,
            (executed, status, error_message, task_id),
        )

    def replace_with_entries(self, entries: list[dict[str, Any]]) -> dict[str, int]:
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("TRUNCATE TABLE scheduled_tasks")
            insert_sql = """
                INSERT INTO scheduled_tasks (
                    task_name, cron_expression, policy, handler, payload, description,
                    is_enabled, last_executed_at, last_executed_status, last_error_message,
                    created_at, updated_at, is_deleted
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, NULL, NULL, NOW(), NOW(), %s)
            """
            params = [
                (
                    entry["task_name"],
                    entry["cron_expression"],
                    entry["policy"],
                    entry["handler"],
                    _normalize_payload_for_storage(entry.get("payload")),
                    entry.get("description"),
                    _normalize_bool(entry.get("is_enabled", 1)),
                    _normalize_bool(entry.get("is_deleted", 0)),
                )
                for entry in entries
            ]
            if params:
                cursor.executemany(insert_sql, params)
            conn.commit()
            return {"truncated": 1, "inserted": len(params)}
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            self.db.disconnect(conn)


class ScheduledTaskScheduler:
    def __init__(self) -> None:
        self.repository = ScheduledTaskRepository()
        self._lock = threading.RLock()
        self._runner_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._tasks: dict[int, dict[str, Any]] = {}
        self._next_run_at: dict[int, datetime | None] = {}
        self._cron_errors: dict[int, str | None] = {}
        self._running_task_ids: set[int] = set()
        self._last_reloaded_at: datetime | None = None

    def start(self) -> None:
        with self._lock:
            if self._runner_thread and self._runner_thread.is_alive():
                return
            self._stop_event.clear()
            self.reload()
            self._runner_thread = threading.Thread(target=self._run_loop, name="scheduled-task-runner", daemon=True)
            self._runner_thread.start()
            logger.info("定时任务调度器已启动")

    def stop(self) -> None:
        self._stop_event.set()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._dispatch_due_tasks()
            except Exception as exc:
                logger.error(f"调度器执行异常: {exc}\n{traceback.format_exc()}")
            self._stop_event.wait(1)

    def _compute_next_run(self, task: dict[str, Any], from_time: datetime | None = None) -> tuple[datetime | None, str | None]:
        try:
            next_run_at = compute_next_run(task["cron_expression"], from_time=from_time)
            return next_run_at, None
        except Exception as exc:
            logger.error(f"计算任务下一次执行时间失败 task={task.get('task_name')}: {exc}")
            return None, str(exc)

    def reload(self) -> dict[str, Any]:
        tasks = self.repository.list_tasks(include_deleted=False)
        now = _now_local()
        next_run_at_map: dict[int, datetime | None] = {}
        cron_errors: dict[int, str | None] = {}
        task_map: dict[int, dict[str, Any]] = {}

        for task in tasks:
            task_id = int(task["task_id"])
            task_map[task_id] = task
            if not _normalize_bool(task.get("is_enabled", 0)):
                next_run_at_map[task_id] = None
                cron_errors[task_id] = None
                continue
            next_run_at, cron_error = self._compute_next_run(task, from_time=now)
            next_run_at_map[task_id] = next_run_at
            cron_errors[task_id] = cron_error

        with self._lock:
            self._tasks = task_map
            self._next_run_at = next_run_at_map
            self._cron_errors = cron_errors
            self._last_reloaded_at = now

        return {
            "loaded_count": len(task_map),
            "enabled_count": sum(1 for task in task_map.values() if _normalize_bool(task.get("is_enabled", 0))),
            "last_reloaded_at": now.isoformat(),
        }

    def list_tasks(self, include_deleted: bool = False) -> list[dict[str, Any]]:
        if include_deleted:
            tasks = self.repository.list_tasks(include_deleted=True)
            response: list[dict[str, Any]] = []
            for task in tasks:
                task_id = int(task["task_id"])
                next_run_at, cron_error = self._compute_next_run(task) if not task.get("is_deleted") else (None, None)
                response.append(build_task_response(task, next_run_at=next_run_at, cron_error=cron_error))
            return response

        with self._lock:
            tasks = list(self._tasks.values())
            next_run_map = dict(self._next_run_at)
            cron_errors = dict(self._cron_errors)
        return [
            build_task_response(task, next_run_at=next_run_map.get(int(task["task_id"])), cron_error=cron_errors.get(int(task["task_id"])))
            for task in tasks
        ]

    def get_task(self, task_id: int) -> dict[str, Any] | None:
        task = self.repository.get_task(task_id)
        if task is None:
            return None
        next_run_at, cron_error = self._compute_next_run(task) if not task.get("is_deleted") else (None, None)
        return build_task_response(task, next_run_at=next_run_at, cron_error=cron_error)

    def create_task(self, data: dict[str, Any]) -> dict[str, Any]:
        created = self.repository.create_task(data)
        self.reload()
        return self.get_task(int(created["task_id"])) or build_task_response(created)

    def update_task(self, task_id: int, data: dict[str, Any]) -> dict[str, Any]:
        updated = self.repository.update_task(task_id, data)
        self.reload()
        return self.get_task(int(updated["task_id"])) or build_task_response(updated)

    def delete_task(self, task_id: int) -> dict[str, Any] | None:
        deleted = self.repository.soft_delete_task(task_id)
        self.reload()
        if deleted is None:
            return None
        return build_task_response(deleted, next_run_at=None, cron_error=None)

    def migrate_from_s_yaml(self, file_path: str | None = None) -> dict[str, Any]:
        entries = parse_s_yaml_to_task_entries(file_path=file_path)
        result = self.repository.replace_with_entries(entries)
        reload_result = self.reload()
        result.update(reload_result)
        result["source"] = file_path or os.path.join(PROJECT_ROOT, "s.yaml")
        return result

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            return {
                "loaded_count": len(self._tasks),
                "running_task_ids": sorted(self._running_task_ids),
                "last_reloaded_at": self._last_reloaded_at.isoformat() if self._last_reloaded_at else None,
            }

    def _refresh_cached_task(self, task_id: int) -> None:
        refreshed_task = self.repository.get_task(task_id)
        if refreshed_task is None:
            return
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id] = refreshed_task

    def run_task_now(self, task_id: int) -> dict[str, Any]:
        """
        立即执行指定任务。

        与后台调度线程一样，这里也会走统一的任务执行器，
        保证手动调试和定时触发使用同一条业务入口。
        """
        task = self.repository.get_task(task_id)
        if task is None:
            raise ValueError("任务不存在")
        if _normalize_bool(task.get("is_deleted", 0)):
            raise ValueError("任务已删除，无法执行")
        with self._lock:
            if task_id in self._running_task_ids:
                raise ValueError("任务正在执行中，请稍后再试")
            self._running_task_ids.add(task_id)
        try:
            result = self._execute_task(task, trigger_source="manual")
            refreshed_task = self.get_task(task_id)
            return {"execution": result, "task": refreshed_task}
        finally:
            with self._lock:
                self._running_task_ids.discard(task_id)

    def _dispatch_due_tasks(self) -> None:
        with self._lock:
            task_items = list(self._tasks.items())
            next_run_map = dict(self._next_run_at)
        for task_id, task in task_items:
            if not _normalize_bool(task.get("is_enabled", 0)):
                continue
            due_time = next_run_map.get(task_id)
            if due_time is None:
                continue
            timezone_name, _raw_expr = _split_cron_expression(task["cron_expression"])
            now = _now_local(timezone_name)
            if now < due_time:
                continue
            with self._lock:
                if task_id in self._running_task_ids:
                    continue
                self._running_task_ids.add(task_id)
            next_run_at, cron_error = self._compute_next_run(task, from_time=now)
            with self._lock:
                self._next_run_at[task_id] = next_run_at
                self._cron_errors[task_id] = cron_error
            worker = threading.Thread(target=self._run_task_in_thread, args=(task,), daemon=True)
            worker.start()

    def _execute_task(self, task: dict[str, Any], trigger_source: str) -> dict[str, Any]:
        task_id = int(task["task_id"])
        try:
            payload = _parse_payload(task.get("payload"))
            result = execute_task_callable(task, payload)
            error_message = result.get("error_message")
            self.repository.update_execution_result(
                task_id,
                result["status"],
                error_message[:60000] if isinstance(error_message, str) else None,
                executed_at=_now_local(),
            )
            self._refresh_cached_task(task_id)
            if result["success"]:
                logger.info(f"定时任务执行成功: {task.get('task_name')} source={trigger_source}")
            return {
                "task_id": task_id,
                "task_name": task.get("task_name"),
                "trigger_source": trigger_source,
                "status": result["status"],
                "success": result["success"],
                "duration_seconds": result.get("duration_seconds"),
                "error_message": error_message,
                "started_at": _ensure_datetime_string(result.get("started_at")),
                "finished_at": _ensure_datetime_string(result.get("finished_at")),
            }
        except Exception as exc:
            error_message = f"{exc}\n{traceback.format_exc()}"
            self.repository.update_execution_result(task_id, "FAILED", error_message[:60000], executed_at=_now_local())
            self._refresh_cached_task(task_id)
            logger.error(f"定时任务执行失败 task={task.get('task_name')}: {error_message}")
            return {
                "task_id": task_id,
                "task_name": task.get("task_name"),
                "trigger_source": trigger_source,
                "status": "FAILED",
                "success": False,
                "duration_seconds": None,
                "error_message": error_message,
                "started_at": None,
                "finished_at": None,
            }

    def _run_task_in_thread(self, task: dict[str, Any]) -> None:
        task_id = int(task["task_id"])
        try:
            self._execute_task(task, trigger_source="scheduler")
        finally:
            with self._lock:
                self._running_task_ids.discard(task_id)


_scheduler_singleton: ScheduledTaskScheduler | None = None
_scheduler_lock = threading.Lock()


def get_scheduler() -> ScheduledTaskScheduler:
    global _scheduler_singleton
    with _scheduler_lock:
        if _scheduler_singleton is None:
            _scheduler_singleton = ScheduledTaskScheduler()
    return _scheduler_singleton
