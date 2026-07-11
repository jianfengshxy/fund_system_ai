import json
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.API.基金信息.FundInfo import getFundInfo, updateFundEstimatedValue
from src.API.基金信息.FundRank import get_fund_volatility, get_nav_rank
from src.API.登录接口.login import ensure_user_fresh
from src.API.组合管理.SubAccountMrg import getSubAccountList, getSubAssetMultList
from src.common.constant import DEFAULT_USER
from src.domain.sub_account.sub_account import SubAccount
from src.domain.user import ApiResponse
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


def _get_sub_accounts_cached():
    k = "sub_accounts"
    v = _cache.get(k)
    if v and v[0] > time.time() - 30:
        return v[1]

    u = ensure_user_fresh(DEFAULT_USER, 600)
    resp = getSubAccountList(u)
    try:
        if (not getattr(resp, "Success", False)) or (not getattr(resp, "Data", None)):
            err = str(getattr(resp, "FirstError", "") or "")
            need_refresh = any(
                x in err for x in ["Token", "token", "凭证", "passport", "未登录", "请登录", "UToken", "CToken", "passportid", "权限"]
            )
            if need_refresh:
                u2 = ensure_user_fresh(u, 600, True)
                resp = getSubAccountList(u2)
        if (not getattr(resp, "Success", False)) or (not getattr(resp, "Data", None)):
            u_fallback = ("u2" in locals() and u2) or u
            fallback = getSubAssetMultList(u_fallback)
            if getattr(fallback, "Success", False) and getattr(fallback, "Data", None):
                groups = getattr(fallback.Data, "list_group", []) or []
                lst = []
                for g in groups:
                    sa = SubAccount.from_basic_info(
                        u_fallback.customer_no, getattr(g, "sub_account_no", ""), getattr(g, "group_name", "")
                    )
                    try:
                        sa.asset_value = float(getattr(g, "total_amount_decimal", 0.0) or 0.0)
                    except Exception:
                        sa.asset_value = 0.0
                    lst.append(sa)
                resp = ApiResponse(True, 0, lst, None, None)
            else:
                resp = ApiResponse(True, 0, [], None, None)
    except Exception:
        resp = ApiResponse(True, 0, [], None, None)

    _cache[k] = (time.time(), resp)
    return resp


def _get_assets_cached(portfolio_name: str):
    k = f"assets:{portfolio_name}"
    v = _cache.get(k)
    if v and v[0] > time.time() - 30:
        return v[1]
    u = ensure_user_fresh(DEFAULT_USER, 600)
    lst = get_sub_account_asset_by_name(u, portfolio_name)
    _cache[k] = (time.time(), lst)
    return lst


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
        def _enrich(a):
            fi = getFundInfo(DEFAULT_USER, a.fund_code)
            if fi:
                if (hasattr(fi, "fund_type") and fi.fund_type == "a") or (
                    hasattr(fi, "fund_name") and "QDII" in fi.fund_name.upper()
                ):
                    a.estimated_change = 0.0
                else:
                    ufi = updateFundEstimatedValue(fi)
                    a.estimated_change = ufi.estimated_change if ufi else 0.0
            else:
                a.estimated_change = 0.0
            return a

        futures = [_executor.submit(_enrich, a) for a in asset_details_list]
        enriched = []
        for f in as_completed(futures):
            enriched.append(f.result())

        for a in enriched:
            total_assets += float(getattr(a, "asset_value", 0.0) or 0.0)
            total_profit += float(getattr(a, "hold_profit", 0.0) or 0.0)
            total_profit_value += float(getattr(a, "profit_value", 0.0) or 0.0)

        if total_assets > 0:
            for a in enriched:
                w = float(getattr(a, "asset_value", 0.0) or 0.0) / total_assets
                estimated_portfolio_change_ratio += w * float(getattr(a, "estimated_change", 0.0) or 0.0)

        portfolio_details = [a.to_dict() for a in enriched]

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
        active_data = [p for p in data if (getattr(p, "asset_value", 0.0) or 0.0) > 0]
        sorted_data = sorted(active_data, key=lambda x: getattr(x, "asset_value", 0.0) or 0.0, reverse=True)
        portfolios = [{"sub_account_name": p.sub_account_name, "asset_value": getattr(p, "asset_value", 0.0) or 0.0} for p in sorted_data]
    return {"portfolios": portfolios, "selected_portfolio_name": portfolios[0]["sub_account_name"] if portfolios else ""}


def _handle_fund_detail(fund_code: str):
    user = ensure_user_fresh(DEFAULT_USER, 600)
    fi = getFundInfo(user, fund_code)
    if not fi:
        return None

    if not ((hasattr(fi, "fund_type") and fi.fund_type == "a") or (hasattr(fi, "fund_name") and "QDII" in fi.fund_name.upper())):
        updateFundEstimatedValue(fi)

    vol_data_5 = get_fund_volatility(user, fi, 5)
    if vol_data_5:
        mean, _variance, _vol = vol_data_5
        fi.nav_5day_avg = mean

    vol_data_30 = get_fund_volatility(user, fi, 30)
    if vol_data_30:
        _mean, _variance, volatility = vol_data_30
        fi.volatility = volatility * 100  # 净值标准差转为百分比

    fi.rank_30day = get_nav_rank(user, fi, 30)
    fi.rank_100day = get_nav_rank(user, fi, 100)

    detail = {}
    for key in dir(fi):
        if key.startswith("_"):
            continue
        v = getattr(fi, key)
        if callable(v):
            continue
        if isinstance(v, (int, float, str, bool, list, dict)) or v is None:
            detail[key] = v
        else:
            detail[key] = str(v)
    return detail


def handler(event, context):
    _evt, path, method = _parse_event(event)

    if method == "OPTIONS":
        return _json_response(204, None)

    if path == "/health" and method == "GET":
        return _json_response(200, {"status": "ok", "message": "Fund System Backend API is running"})

    if path == "/api/cache/clear" and method == "POST":
        _cache.clear()
        return _json_response(200, {"success": True})

    if path == "/api/portfolios" and method == "GET":
        try:
            return _json_response(200, _handle_portfolios())
        except Exception as e:
            return _json_response(500, {"error": str(e)})

    if path.startswith("/api/portfolio/") and method == "GET":
        raw_name = path[len("/api/portfolio/") :]
        portfolio_name = urllib.parse.unquote(raw_name)
        try:
            return _json_response(200, _handle_portfolio_details(portfolio_name))
        except Exception as e:
            return _json_response(500, {"error": str(e)})

    if path.startswith("/api/fund/") and method == "GET":
        fund_code = urllib.parse.unquote(path[len("/api/fund/") :])
        try:
            detail = _handle_fund_detail(fund_code)
            if detail is None:
                return _json_response(404, {"error": "未找到基金信息"})
            return _json_response(200, detail)
        except Exception as e:
            return _json_response(500, {"error": str(e)})

    return _json_response(404, {"error": "NOT_FOUND", "path": path, "method": method})
