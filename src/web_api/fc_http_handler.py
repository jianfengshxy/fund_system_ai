from __future__ import annotations

import base64
import json
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

from src.API.基金信息.FundInfo import getFundInfo, updateFundEstimatedValue
from src.API.基金信息.FundRank import get_fund_volatility, get_nav_rank
from src.API.登录接口.login import ensure_user_fresh
from src.API.组合管理.SubAccountMrg import getSubAccountList, getSubAssetMultList
from src.common.aliyun_fc_openapi import FcOpenApiClient
from src.common.logger import get_logger
from src.common.constant import DEFAULT_USER
from src.domain.sub_account.sub_account import SubAccount
from src.domain.user import ApiResponse
from src.scheduled_task_manager import compute_next_run, get_scheduler
from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name
from src.service.公共服务.estimated_profit_service import calc_estimated_change

logger = get_logger(__name__)

_executor = ThreadPoolExecutor(max_workers=8)
_cache: dict[str, tuple[float, object]] = {}


def _json_response(status_code: int, data: object | None = None, headers: dict | None = None):
    base_headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Content-Disposition": "inline",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
    }
    if headers:
        base_headers.update(headers)
    body = "" if data is None else json.dumps(_jsonify(data), ensure_ascii=False)
    return {"statusCode": status_code, "headers": base_headers, "body": body}


def _ensure_datetime_string(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _jsonify(value: Any) -> Any:
    from dataclasses import asdict, is_dataclass

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return _jsonify(asdict(value))
    if isinstance(value, dict):
        return {str(k): _jsonify(v) for k, v in value.items() if not callable(v)}
    if isinstance(value, (list, tuple, set)):
        return [_jsonify(v) for v in value]
    return str(value)


def _parse_event(event):
    if isinstance(event, (bytes, bytearray)):
        event = event.decode("utf-8", errors="ignore")
    if isinstance(event, str):
        event = json.loads(event) if event.strip() else {}
    if not isinstance(event, dict):
        return {}, "", "GET"

    method = (
        event.get("httpMethod")
        or event.get("method")
        or event.get("requestContext", {}).get("http", {}).get("method")
        or "GET"
    )
    path = (
        event.get("rawPath")
        or event.get("path")
        or event.get("requestContext", {}).get("http", {}).get("path")
        or "/"
    )
    return event, str(path), str(method).upper()


def _extract_json_body(event: dict[str, Any]) -> dict[str, Any]:
    body = event.get("body")
    if body is None:
        return {}
    if event.get("isBase64Encoded") and isinstance(body, str):
        body = base64.b64decode(body).decode("utf-8", errors="ignore")
    if isinstance(body, str):
        stripped = body.strip()
        if not stripped:
            return {}
        parsed = json.loads(stripped)
        if not isinstance(parsed, dict):
            raise ValueError("请求体必须为 JSON 对象")
        return parsed
    if isinstance(body, dict):
        return body
    raise ValueError("无法解析请求体")


def _extract_query_params(event: dict[str, Any]) -> dict[str, str]:
    params = event.get("queryParameters") or event.get("queryStringParameters") or {}
    return params if isinstance(params, dict) else {}


def _validate_scheduled_task_payload(data: Any, partial: bool = False) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("请求体必须为 JSON 对象")

    required_fields = ["task_name", "cron_expression", "policy", "handler"]
    if not partial:
        missing = [field for field in required_fields if not str(data.get(field, "")).strip()]
        if missing:
            raise ValueError(f"缺少必填字段: {', '.join(missing)}")

    allowed_fields = {
        "task_name",
        "cron_expression",
        "policy",
        "handler",
        "payload",
        "description",
        "is_enabled",
        "display_priority",
    }
    normalized: dict[str, Any] = {}
    for key in allowed_fields:
        if key not in data:
            continue
        value = data[key]
        if key in {"task_name", "cron_expression", "policy", "handler"}:
            if value is None or not str(value).strip():
                raise ValueError(f"字段 `{key}` 不能为空")
            normalized[key] = str(value).strip()
        elif key == "description":
            normalized[key] = None if value in (None, "") else str(value)
        elif key == "payload":
            normalized[key] = value
        elif key == "is_enabled":
            normalized[key] = bool(value)
        elif key == "display_priority":
            if value is None or value == "":
                normalized[key] = 100
                continue
            try:
                parsed = int(value)
            except Exception as exc:
                raise ValueError("字段 `display_priority` 必须为整数") from exc
            if parsed < 0:
                raise ValueError("字段 `display_priority` 不能小于 0")
            normalized[key] = parsed

    if "cron_expression" in normalized:
        compute_next_run(normalized["cron_expression"])
    return normalized


def _apply_fc_timer_trigger(task: dict[str, Any], *, old_task_name: str | None = None) -> FcOpenApiClient:
    function_name = str(task.get("policy") or "").strip()
    trigger_name = str(task.get("task_name") or "").strip()
    if not function_name or not trigger_name:
        raise ValueError("无法同步 FC trigger：policy/task_name 为空")
    cron_expression = str(task.get("cron_expression") or "").strip()
    if not cron_expression:
        raise ValueError("无法同步 FC trigger：cron_expression 为空")

    enable = bool(task.get("is_enabled"))
    payload = task.get("payload")
    client = FcOpenApiClient()
    if old_task_name and old_task_name != trigger_name:
        client.create_timer_trigger(
            function_name=function_name,
            trigger_name=trigger_name,
            cron_expression=cron_expression,
            payload=payload,
            enable=enable,
        )
        client.delete_trigger(function_name, old_task_name)
        return client

    try:
        client.get_trigger(function_name, trigger_name)
        client.update_timer_trigger(
            function_name=function_name,
            trigger_name=trigger_name,
            cron_expression=cron_expression,
            payload=payload,
            enable=enable,
        )
        return client
    except Exception:
        client.create_timer_trigger(
            function_name=function_name,
            trigger_name=trigger_name,
            cron_expression=cron_expression,
            payload=payload,
            enable=enable,
        )
        return client


def _sync_fc_timer_trigger(task: dict[str, Any], repo, *, old_task_name: str | None = None) -> None:
    task_id = int(task.get("task_id")) if task.get("task_id") is not None else None
    client = _apply_fc_timer_trigger(task, old_task_name=old_task_name)
    if task_id is None:
        return
    function_name = str(task.get("policy") or "").strip()
    trigger_name = str(task.get("task_name") or "").strip()
    repo.update_fc_sync(
        task_id,
        fc_account_id=client.account_id,
        fc_region=client.region,
        fc_function_name=function_name,
        fc_trigger_name=trigger_name,
        fc_trigger_type="timer",
        fc_qualifier="LATEST",
        sync_status="OK",
        sync_error_message=None,
        last_synced_at=None,
    )


def _parse_task_id(path: str, action_suffix: str | None = None) -> int:
    normalized = path.rstrip("/")
    if action_suffix:
        suffix = f"/{action_suffix}"
        if not normalized.endswith(suffix):
            raise ValueError("任务路径不正确")
        normalized = normalized[: -len(suffix)]
    raw_id = normalized.rsplit("/", 1)[-1]
    try:
        return int(raw_id)
    except ValueError as exc:
        raise ValueError("任务 ID 必须为数字") from exc


def _get_sub_accounts_cached():
    cache_key = "sub_accounts"
    value = _cache.get(cache_key)
    if value and value[0] > time.time() - 30:
        return value[1]

    user = ensure_user_fresh(DEFAULT_USER, 600)
    response = getSubAccountList(user)
    try:
        if (not getattr(response, "Success", False)) or (not getattr(response, "Data", None)):
            err = str(getattr(response, "FirstError", "") or "")
            need_refresh = any(
                key in err for key in ["Token", "token", "凭证", "passport", "未登录", "请登录", "UToken", "CToken", "passportid", "权限"]
            )
            if need_refresh:
                refreshed_user = ensure_user_fresh(user, 600, True)
                response = getSubAccountList(refreshed_user)
        if (not getattr(response, "Success", False)) or (not getattr(response, "Data", None)):
            fallback_user = ("refreshed_user" in locals() and refreshed_user) or user
            fallback = getSubAssetMultList(fallback_user)
            if getattr(fallback, "Success", False) and getattr(fallback, "Data", None):
                groups = getattr(fallback.Data, "list_group", []) or []
                portfolios = []
                for group in groups:
                    portfolio = SubAccount.from_basic_info(
                        fallback_user.customer_no,
                        getattr(group, "sub_account_no", ""),
                        getattr(group, "group_name", ""),
                    )
                    try:
                        portfolio.asset_value = float(getattr(group, "total_amount_decimal", 0.0) or 0.0)
                    except Exception:
                        portfolio.asset_value = 0.0
                    portfolios.append(portfolio)
                response = ApiResponse(True, 0, portfolios, None, None)
            else:
                response = ApiResponse(True, 0, [], None, None)
    except Exception:
        response = ApiResponse(True, 0, [], None, None)

    _cache[cache_key] = (time.time(), response)
    return response


def _get_assets_cached(portfolio_name: str):
    cache_key = f"assets:{portfolio_name}"
    value = _cache.get(cache_key)
    if value and value[0] > time.time() - 30:
        return value[1]

    user = ensure_user_fresh(DEFAULT_USER, 600)
    assets = get_sub_account_asset_by_name(user, portfolio_name)
    _cache[cache_key] = (time.time(), assets)
    return assets


def _handle_portfolio_details(portfolio_name: str):
    total_assets = 0.0
    total_profit = 0.0
    estimated_portfolio_change_ratio = 0.0
    total_profit_value = 0.0
    portfolio_details = []

    user = ensure_user_fresh(DEFAULT_USER, 600)
    sub_accounts_response = _get_sub_accounts_cached()
    selected_portfolio = None
    if getattr(sub_accounts_response, "Success", False) and getattr(sub_accounts_response, "Data", None):
        for portfolio in sub_accounts_response.Data:
            if portfolio.sub_account_name == portfolio_name:
                selected_portfolio = portfolio
                break

    asset_details_list = _get_assets_cached(portfolio_name) or []
    if asset_details_list:

        def _enrich(asset):
            from src.service.基金信息.基金信息 import get_all_fund_info

            fund_info = get_all_fund_info(user, asset.fund_code)
            if not fund_info:
                asset.estimated_change = 0.0
                asset.nav_change = None
                asset.nav_date = getattr(asset, "nav_date", None)
                return asset

            asset.fund_name = getattr(fund_info, "fund_name", getattr(asset, "fund_name", None))
            asset.fund_type = getattr(fund_info, "fund_type", getattr(asset, "fund_type", None))
            asset.fund_nav = getattr(fund_info, "nav", getattr(asset, "fund_nav", None))
            asset.nav_date = getattr(fund_info, "nav_date", getattr(asset, "nav_date", None))
            asset.nav_change = getattr(fund_info, "nav_change", None)
            nav_date = str(getattr(fund_info, "nav_date", "") or "")[:10]
            est_date = str(getattr(fund_info, "estimated_time", "") or "")[:10]
            nav_change = getattr(fund_info, "nav_change", None)
            fund_type = getattr(fund_info, "fund_type", None)
            fund_name = getattr(fund_info, "fund_name", None)
            is_qdii = (str(fund_type) == "a") or ("QDII" in str(fund_name or "").upper())
            if is_qdii:
                asset.estimated_change = float(getattr(fund_info, "estimated_change", None) or 0.0)
            elif nav_date and est_date and nav_date == est_date and nav_change is not None:
                asset.estimated_change = float(nav_change or 0.0)
            else:
                asset.estimated_change = float(getattr(fund_info, "estimated_change", None) or 0.0)
            asset.estimated_time = getattr(fund_info, "estimated_time", None)
            return asset

        futures = [_executor.submit(_enrich, asset) for asset in asset_details_list]
        enriched = []
        for future in as_completed(futures):
            enriched.append(future.result())

        for asset in enriched:
            total_assets += float(getattr(asset, "asset_value", 0.0) or 0.0)
            total_profit += float(getattr(asset, "hold_profit", 0.0) or 0.0)
            total_profit_value += float(getattr(asset, "profit_value", 0.0) or 0.0)

        if total_assets > 0:
            for asset in enriched:
                weight = float(getattr(asset, "asset_value", 0.0) or 0.0) / total_assets
                estimated_portfolio_change_ratio += weight * float(getattr(asset, "estimated_change", 0.0) or 0.0)

        portfolio_details = [asset.to_dict() for asset in enriched]

    return {
        "portfolio_details": portfolio_details,
        "total_assets": total_assets,
        "total_profit": total_profit,
        "estimated_portfolio_change_ratio": estimated_portfolio_change_ratio,
        "total_profit_value": total_profit_value,
        "constant_profit": getattr(selected_portfolio, "constant_profit", 0.0) if selected_portfolio else 0.0,
        "profit_value": getattr(selected_portfolio, "profit_value", 0.0) if selected_portfolio else 0.0,
    }


def _handle_portfolios():
    sub_accounts_response = _get_sub_accounts_cached()
    portfolios = []
    data = getattr(sub_accounts_response, "Data", None)
    if isinstance(data, list):
        active_data = [portfolio for portfolio in data if (getattr(portfolio, "asset_value", 0.0) or 0.0) > 0]
        sorted_data = sorted(active_data, key=lambda item: getattr(item, "asset_value", 0.0) or 0.0, reverse=True)
        portfolios = [
            {
                "sub_account_name": portfolio.sub_account_name,
                "asset_value": getattr(portfolio, "asset_value", 0.0) or 0.0,
            }
            for portfolio in sorted_data
        ]
    return {"portfolios": portfolios, "selected_portfolio_name": portfolios[0]["sub_account_name"] if portfolios else ""}


def _handle_fund_detail(fund_code: str):
    user = ensure_user_fresh(DEFAULT_USER, 600)
    from src.service.基金信息.基金信息 import get_all_fund_info
    fund_info = get_all_fund_info(user, fund_code)
    if not fund_info:
        return None

    detail = {}
    for key in dir(fund_info):
        if key.startswith("_"):
            continue
        value = getattr(fund_info, key)
        if callable(value):
            continue
        if isinstance(value, (int, float, str, bool, list, dict)) or value is None:
            detail[key] = value
        else:
            detail[key] = str(value)
    return detail


def handler(event, _context):
    scheduler = get_scheduler()
    parsed_event, path, method = _parse_event(event)

    if method == "OPTIONS":
        return _json_response(204, None)

    try:
        if path == "/health" and method == "GET":
            state = scheduler.get_state()
            return _json_response(200, {"status": "ok", "message": "Fund System Backend API is running", "scheduler": state})

        if path == "/api/cache/clear" and method == "POST":
            _cache.clear()
            return _json_response(200, {"success": True})

        if path == "/api/scheduled-tasks" and method == "GET":
            query_params = _extract_query_params(parsed_event)
            include_deleted = str(query_params.get("include_deleted", "false")).lower() == "true"
            return _json_response(200, {"tasks": scheduler.list_tasks(include_deleted=include_deleted), "scheduler": scheduler.get_state()})

        if path == "/api/scheduled-tasks/state" and method == "GET":
            return _json_response(200, scheduler.get_state())

        if path == "/api/scheduled-tasks/reload" and method == "POST":
            return _json_response(200, {"success": True, "result": scheduler.reload()})

        if path == "/api/scheduled-tasks/migrate" and method == "POST":
            body = _extract_json_body(parsed_event)
            file_path = body.get("file_path")
            result = scheduler.migrate_from_s_yaml(file_path=file_path)
            return _json_response(200, {"success": True, "result": result})

        if path == "/api/scheduled-tasks/fc/sync-from-fc" and method == "POST":
            body = _extract_json_body(parsed_event)
            if body.get("confirm") is not True:
                raise ValueError("请传入 {\"confirm\": true} 进行确认")
            client = FcOpenApiClient()

            functions: list[dict[str, Any]] = []
            next_token = None
            while True:
                page = client.list_functions(limit=100, next_token=next_token)
                batch = (page or {}).get("functions") or []
                if isinstance(batch, list):
                    functions.extend([item for item in batch if isinstance(item, dict)])
                next_token = (page or {}).get("nextToken")
                if not next_token:
                    break

            used_task_names: set[str] = set()
            entries: list[dict[str, Any]] = []
            for fn in functions:
                function_name = str(fn.get("functionName") or "").strip()
                if not function_name:
                    continue
                trigger_page = client.list_triggers(function_name, limit=100)
                triggers = (trigger_page or {}).get("triggers") or []
                if not isinstance(triggers, list):
                    continue
                handler_name = str(fn.get("handler") or "").strip()
                if not handler_name:
                    try:
                        fn_detail = client.get_function(function_name)
                        handler_name = str((fn_detail or {}).get("handler") or "").strip()
                    except Exception:
                        handler_name = ""
                for trig in triggers:
                    if not isinstance(trig, dict):
                        continue
                    if str(trig.get("triggerType") or "") != "timer":
                        continue
                    trigger_name = str(trig.get("triggerName") or "").strip()
                    if not trigger_name:
                        continue
                    raw_trigger_config = trig.get("triggerConfig")
                    trigger_config = None
                    if isinstance(raw_trigger_config, str) and raw_trigger_config.strip():
                        try:
                            trigger_config = json.loads(raw_trigger_config)
                        except Exception:
                            trigger_config = None
                    if not isinstance(trigger_config, dict):
                        trigger_config = {}
                    cron_expression = str(trigger_config.get("cronExpression") or "").strip()
                    if not cron_expression:
                        continue
                    payload = trigger_config.get("payload")
                    enable = bool(trigger_config.get("enable", True))
                    task_name = trigger_name
                    if task_name in used_task_names:
                        task_name = f"{task_name}__{function_name}"
                    if task_name in used_task_names:
                        continue
                    used_task_names.add(task_name)
                    entries.append(
                        {
                            "task_name": task_name,
                            "cron_expression": cron_expression,
                            "policy": function_name,
                            "handler": handler_name or f"index.{function_name}",
                            "payload": payload,
                            "description": trig.get("description"),
                            "is_enabled": enable,
                            "is_deleted": 0,
                            "fc_account_id": client.account_id,
                            "fc_region": client.region,
                            "fc_function_name": function_name,
                            "fc_trigger_name": trigger_name,
                            "fc_trigger_type": "timer",
                            "fc_qualifier": str(trig.get("qualifier") or "LATEST"),
                            "sync_status": "IMPORTED",
                            "sync_error_message": None,
                        }
                    )
            # upsert：已存在的保留 display_priority 等本地字段，不存在的创建
            result = scheduler.sync_from_fc(entries)
            return _json_response(200, {"success": True, "result": result})

        if path == "/api/scheduled-tasks" and method == "POST":
            body = _extract_json_body(parsed_event)
            task_payload = _validate_scheduled_task_payload(body, partial=False)
            existing = scheduler.repository.get_task_by_name(str(task_payload.get("task_name") or "").strip())
            if existing and not existing.get("is_deleted"):
                raise ValueError("任务名已存在，请更换 task_name 或编辑已有任务")
            function_name = str(task_payload.get("policy") or "").strip()
            trigger_name = str(task_payload.get("task_name") or "").strip()
            cron_expression = str(task_payload.get("cron_expression") or "").strip()
            enable = bool(task_payload.get("is_enabled", True))
            payload = task_payload.get("payload")

            client = FcOpenApiClient()
            try:
                client.get_trigger(function_name, trigger_name)
                raise ValueError("FC 触发器已存在（同名 triggerName），请改名或先删除 FC 侧触发器")
            except ValueError:
                raise
            except Exception:
                pass
            client.create_timer_trigger(
                function_name=function_name,
                trigger_name=trigger_name,
                cron_expression=cron_expression,
                payload=payload,
                enable=enable,
            )

            created = None
            try:
                created = scheduler.repository.create_task(
                    {
                        **task_payload,
                        "fc_account_id": client.account_id,
                        "fc_region": client.region,
                        "fc_function_name": function_name,
                        "fc_trigger_name": trigger_name,
                        "fc_trigger_type": "timer",
                        "fc_qualifier": "LATEST",
                        "sync_status": "OK",
                        "sync_error_message": None,
                    }
                )
                scheduler.repository.update_fc_sync(
                    int(created["task_id"]),
                    fc_account_id=client.account_id,
                    fc_region=client.region,
                    fc_function_name=function_name,
                    fc_trigger_name=trigger_name,
                    fc_trigger_type="timer",
                    fc_qualifier="LATEST",
                    sync_status="OK",
                    sync_error_message=None,
                    last_synced_at=None,
                )
            except Exception as exc:
                try:
                    client.delete_trigger(function_name, trigger_name)
                except Exception:
                    pass
                if created and created.get("task_id") is not None:
                    try:
                        scheduler.repository.hard_delete_task(int(created["task_id"]))
                    except Exception:
                        pass
                raise ValueError(f"FC 创建成功但写入数据库失败: {exc}")

            task = scheduler.get_task(int(created["task_id"]))
            return _json_response(201, {"success": True, "task": task})

        if path.endswith("/run") and path.startswith("/api/scheduled-tasks/") and method == "POST":
            task_id = _parse_task_id(path, action_suffix="run")
            try:
                result = scheduler.run_task_now(task_id)
                return _json_response(200, {"success": True, "result": result})
            except Exception as exc:
                logger.exception(f"run_task_now failed task_id={task_id}: {exc}")
                raise

        if path.endswith("/log") and path.startswith("/api/scheduled-tasks/") and method == "GET":
            task_id = _parse_task_id(path, action_suffix="log")
            log_entry = scheduler.repository.get_task_log(task_id)
            if log_entry is None:
                return _json_response(200, {"success": True, "result": None})
            for key, value in list(log_entry.items()):
                log_entry[key] = _ensure_datetime_string(value)
            return _json_response(200, {"success": True, "result": log_entry})

        if path.startswith("/api/scheduled-tasks/") and method == "GET":
            task_id = _parse_task_id(path)
            task = scheduler.get_task(task_id)
            if task is None:
                return _json_response(404, {"error": "任务不存在"})
            return _json_response(200, {"task": task})

        if path.startswith("/api/scheduled-tasks/") and method == "PUT":
            task_id = _parse_task_id(path)
            body = _extract_json_body(parsed_event)
            task_payload = _validate_scheduled_task_payload(body, partial=True)
            before = scheduler.repository.get_task(task_id)
            if before is None:
                return _json_response(404, {"error": "任务不存在"})
            old_task_name = str(before.get("task_name") or "").strip()
            merged = dict(before)
            merged.update(task_payload)
            merged["task_id"] = task_id
            if "is_enabled" in task_payload:
                merged["is_enabled"] = bool(task_payload.get("is_enabled"))
            new_task_name = str(merged.get("task_name") or "").strip()
            old_name_for_rename = old_task_name if old_task_name != new_task_name else None

            try:
                client = _apply_fc_timer_trigger(merged, old_task_name=old_name_for_rename)
            except Exception as exc:
                raise ValueError(f"FC 更新触发器失败，数据库未变更: {exc}")

            updated = None
            try:
                updated = scheduler.update_task(task_id, task_payload)
                scheduler.repository.update_fc_sync(
                    task_id,
                    fc_account_id=client.account_id,
                    fc_region=client.region,
                    fc_function_name=str(merged.get("policy") or "").strip(),
                    fc_trigger_name=str(merged.get("task_name") or "").strip(),
                    fc_trigger_type="timer",
                    fc_qualifier="LATEST",
                    sync_status="OK",
                    sync_error_message=None,
                    last_synced_at=None,
                )
            except Exception as exc:
                try:
                    rollback_old_name = new_task_name if old_task_name != new_task_name else None
                    _apply_fc_timer_trigger(before, old_task_name=rollback_old_name)
                except Exception:
                    pass
                raise ValueError(f"FC 更新成功但写入数据库失败，已尝试回滚 FC: {exc}")

            return _json_response(200, {"success": True, "task": updated})

        if path.startswith("/api/scheduled-tasks/") and method == "DELETE":
            task_id = _parse_task_id(path)
            current = scheduler.repository.get_task(task_id)
            if current is None:
                return _json_response(404, {"error": "任务不存在"})
            function_name = str(current.get("policy") or "").strip()
            trigger_name = str(current.get("task_name") or "").strip()
            client = FcOpenApiClient()
            try:
                client.delete_trigger(function_name, trigger_name)
            except Exception as exc:
                raise ValueError(f"FC 删除触发器失败，数据库未变更: {exc}")
            try:
                task = scheduler.delete_task(task_id)
                if task is None:
                    return _json_response(404, {"error": "任务不存在"})
                return _json_response(200, {"success": True, "task": task})
            except Exception as exc:
                try:
                    _apply_fc_timer_trigger(current)
                except Exception:
                    pass
                raise ValueError(f"FC 删除成功但写入数据库失败，已尝试回滚 FC: {exc}")

        if path == "/api/portfolios" and method == "GET":
            return _json_response(200, _handle_portfolios())

        if path.startswith("/api/portfolio/") and method == "GET":
            raw_name = path[len("/api/portfolio/") :]
            portfolio_name = urllib.parse.unquote(raw_name)
            return _json_response(200, _handle_portfolio_details(portfolio_name))

        if path.startswith("/api/fund/") and method == "GET":
            fund_code = urllib.parse.unquote(path[len("/api/fund/") :])
            detail = _handle_fund_detail(fund_code)
            if detail is None:
                return _json_response(404, {"error": "未找到基金信息"})
            return _json_response(200, detail)
    except ValueError as exc:
        return _json_response(400, {"error": str(exc), "path": path, "method": method})
    except Exception as exc:
        return _json_response(500, {"error": str(exc), "path": path, "method": method})

    return _json_response(404, {"error": "NOT_FOUND", "path": path, "method": method})
