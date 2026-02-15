from __future__ import annotations

from typing import Any, Dict, Optional

from src.common.constant import MOBILE_KEY, PHONE_TYPE, SERVER_VERSION


def get_passport_id(user: Any) -> str:
    return (
        getattr(user, "passport_id", None)
        or getattr(user, "passport_uid", None)
        or getattr(user, "passportId", None)
        or getattr(user, "customer_no", None)
        or ""
    )


def get_user_id(user: Any) -> str:
    return getattr(user, "passport_uid", None) or getattr(user, "customer_no", None) or ""


def build_auth_fields(
    user: Any,
    *,
    server_version: str = SERVER_VERSION,
    phone_type: str = PHONE_TYPE,
    mobile_key: str = MOBILE_KEY,
    include_passport: bool = True,
    include_lowercase: bool = False,
    override_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    uid = override_user_id or get_user_id(user)
    base: Dict[str, Any] = {
        "CToken": getattr(user, "c_token", ""),
        "UToken": getattr(user, "u_token", ""),
        "CustomerNo": getattr(user, "customer_no", ""),
        "UserId": uid,
        "MobileKey": mobile_key,
        "PhoneType": phone_type,
        "ServerVersion": server_version,
        "Version": server_version,
    }
    if include_passport:
        base["Passportid"] = get_passport_id(user)
    if include_lowercase:
        base.update(
            {
                "ctoken": base["CToken"],
                "utoken": base["UToken"],
                "customerNo": base["CustomerNo"],
                "userId": base["UserId"],
                "mobileKey": base["MobileKey"],
                "phoneType": base["PhoneType"],
                "serverVersion": base["ServerVersion"],
                "version": base["Version"],
                "deviceid": mobile_key,
            }
        )
    return base

