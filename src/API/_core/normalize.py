from __future__ import annotations

from typing import Any, Dict, Optional


def _get_first(d: Dict[str, Any], keys: list[str]) -> Any:
    for k in keys:
        if k in d:
            return d.get(k)
    return None


def is_success(data: Dict[str, Any]) -> bool:
    v = _get_first(data, ["Success", "success", "Succeed", "succeed", "IsSuccess", "isSuccess"])
    return bool(v)


def error_code(data: Dict[str, Any]) -> Any:
    return _get_first(data, ["ErrorCode", "ErrCode", "errorCode", "errCode", "code"])


def error_message(data: Dict[str, Any]) -> str:
    v = _get_first(
        data,
        ["FirstError", "firstError", "ErrMsg", "ErrorMessage", "Message", "message", "msg"],
    )
    return "" if v is None else str(v)


def is_empty_ok(data: Dict[str, Any]) -> bool:
    code = error_code(data)
    return code == 0 or str(code) == "0"


def is_auth_error(
    data: Optional[Dict[str, Any]] = None,
    *,
    status_code: Optional[int] = None,
    text: str = "",
) -> bool:
    msg = ""
    if data:
        msg = error_message(data)
        try:
            if not msg:
                msg = str(data)
        except Exception:
            msg = ""
    hay = (msg or "") + " " + (text or "")
    keywords = ["Token", "token", "凭证", "passport", "未登录", "请登录", "UToken", "CToken", "passportid", "权限"]
    if any(k in hay for k in keywords):
        return True
    if status_code in (401, 403):
        return True
    return False

