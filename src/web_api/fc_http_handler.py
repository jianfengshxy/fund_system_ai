from __future__ import annotations

import base64
import json
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from src.API.基金信息.FundInfo import getFundInfo, updateFundEstimatedValue
from src.API.基金信息.FundRank import get_fund_volatility, get_nav_rank
from src.API.登录接口.login import ensure_user_fresh
from src.API.组合管理.SubAccountMrg import getSubAccountList, getSubAssetMultList
from src.common.constant import DEFAULT_USER
from src.domain.sub_account.sub_account import SubAccount
from src.domain.user import ApiResponse
from src.scheduled_task_manager import compute_next_run, get_scheduler
from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name

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
    body = "" if data is None else json.dumps(data, ensure_ascii=False)
    return {"statusCode": status_code, "headers": base_headers, "body": body}


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

    allowed_fields = {"task_name", "cron_expression", "policy", "handler", "payload", "description", "is_enabled"}
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

    if "cron_expression" in normalized:
        compute_next_run(normalized["cron_expression"])
    return normalized


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
            fund_info = getFundInfo(DEFAULT_USER, asset.fund_code)
            if fund_info:
                if (hasattr(fund_info, "fund_type") and fund_info.fund_type == "a") or (
                    hasattr(fund_info, "fund_name") and "QDII" in fund_info.fund_name.upper()
                ):
                    asset.estimated_change = 0.0
                else:
                    updated_fund = updateFundEstimatedValue(fund_info)
                    asset.estimated_change = updated_fund.estimated_change if updated_fund else 0.0
            else:
                asset.estimated_change = 0.0
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
    fund_info = getFundInfo(user, fund_code)
    if not fund_info:
        return None

    if not (
        (hasattr(fund_info, "fund_type") and fund_info.fund_type == "a")
        or (hasattr(fund_info, "fund_name") and "QDII" in fund_info.fund_name.upper())
    ):
        updateFundEstimatedValue(fund_info)

    vol_data_5 = get_fund_volatility(user, fund_info, 5)
    if vol_data_5:
        mean, _variance, _vol = vol_data_5
        fund_info.nav_5day_avg = mean

    vol_data_30 = get_fund_volatility(user, fund_info, 30)
    if vol_data_30:
        _mean, _variance, volatility = vol_data_30
        fund_info.volatility = volatility * 100

    fund_info.rank_30day = get_nav_rank(user, fund_info, 30)
    fund_info.rank_100day = get_nav_rank(user, fund_info, 100)

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
    scheduler.start()
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

        if path == "/api/scheduled-tasks" and method == "POST":
            body = _extract_json_body(parsed_event)
            task_payload = _validate_scheduled_task_payload(body, partial=False)
            task = scheduler.create_task(task_payload)
            scheduler.reload()
            return _json_response(201, {"success": True, "task": task})

        if path.endswith("/run") and path.startswith("/api/scheduled-tasks/") and method == "POST":
            task_id = _parse_task_id(path, action_suffix="run")
            result = scheduler.run_task_now(task_id)
            return _json_response(200, {"success": True, "result": result})

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
            task = scheduler.update_task(task_id, task_payload)
            scheduler.reload()
            return _json_response(200, {"success": True, "task": task})

        if path.startswith("/api/scheduled-tasks/") and method == "DELETE":
            task_id = _parse_task_id(path)
            task = scheduler.delete_task(task_id)
            if task is None:
                return _json_response(404, {"error": "任务不存在"})
            scheduler.reload()
            return _json_response(200, {"success": True, "task": task})

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

