from __future__ import annotations

from typing import Dict, Optional


def build_headers(
    *,
    host: str,
    content_type: Optional[str] = None,
    referer: Optional[str] = None,
    accept: str = "*/*",
    accept_language: str = "zh-Hans-CN;q=1",
    user_agent: Optional[str] = None,
    client_info: Optional[str] = None,
    mp_version: Optional[str] = None,
    gtoken: Optional[str] = None,
    connection: str = "keep-alive",
) -> Dict[str, str]:
    headers: Dict[str, str] = {
        "Connection": connection,
        "Host": host,
        "Accept": accept,
        "Accept-Language": accept_language,
    }
    if content_type:
        headers["Content-Type"] = content_type
    if referer:
        headers["Referer"] = referer
    if user_agent:
        headers["User-Agent"] = user_agent
    if client_info:
        headers["clientInfo"] = client_info
    if mp_version:
        headers["MP-VERSION"] = mp_version
    if gtoken:
        headers["GTOKEN"] = gtoken
    return headers

