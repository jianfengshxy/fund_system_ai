from __future__ import annotations

from typing import Dict, Optional


def build_headers(
    *,
    host: str,
    content_type: Optional[str] = None,
    referer: Optional[str] = None,
    accept: str = "*/*",
    accept_encoding: str = "gzip, deflate, br",
    accept_language: str = "zh-Hans-CN;q=1",
    user_agent: Optional[str] = None,
    client_info: Optional[str] = None,
    mp_version: Optional[str] = None,
    gtoken: Optional[str] = None,
    mp_instance_id: Optional[str] = None,
    traceparent: Optional[str] = None,
    tracestate: Optional[str] = None,
    connection: str = "keep-alive",
) -> Dict[str, str]:
    headers: Dict[str, str] = {
        "Connection": connection,
        "Host": host,
        "Accept": accept,
        "Accept-Encoding": accept_encoding,
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
        headers["gtoken"] = gtoken
        headers["GTOKEN"] = gtoken
    if mp_instance_id:
        headers["mp_instance_id"] = mp_instance_id
    if traceparent:
        headers["traceparent"] = traceparent
    if tracestate:
        headers["tracestate"] = tracestate
    return headers
