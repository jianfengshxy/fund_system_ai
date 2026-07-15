from __future__ import annotations

import hashlib
import hmac
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlencode


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac_sha256_hex(key: bytes, msg: bytes) -> str:
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def _utc_iso8601() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_path(path: str) -> str:
    if not path:
        return "/"
    return path if path.startswith("/") else f"/{path}"


def _canonical_query(query: dict[str, Any] | None) -> str:
    if not query:
        return ""
    normalized: dict[str, str] = {}
    for key, value in query.items():
        if value is None:
            continue
        normalized[str(key)] = str(value)
    if not normalized:
        return ""
    items = sorted(normalized.items(), key=lambda item: item[0])
    return urlencode(items, quote_via=quote, safe="~")


def _canonical_headers(headers: dict[str, str], signed_header_names: list[str]) -> str:
    lines: list[str] = []
    for name in signed_header_names:
        value = headers.get(name, "")
        lines.append(f"{name}:{value.strip()}")
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class Acs3Credentials:
    access_key_id: str
    access_key_secret: str
    security_token: str | None = None


def load_acs3_credentials() -> Acs3Credentials:
    access_key_id = (os.getenv("ALIYUN_ACCESS_KEY_ID") or os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID") or "").strip()
    access_key_secret = (
        os.getenv("ALIYUN_ACCESS_KEY_SECRET") or os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET") or ""
    ).strip()
    security_token = (os.getenv("ALIYUN_SECURITY_TOKEN") or os.getenv("ALIBABA_CLOUD_SECURITY_TOKEN") or "").strip()
    if not access_key_id or not access_key_secret:
        raise ValueError("缺少阿里云 OpenAPI 凭证：请配置 ALIYUN_ACCESS_KEY_ID / ALIYUN_ACCESS_KEY_SECRET")
    return Acs3Credentials(access_key_id=access_key_id, access_key_secret=access_key_secret, security_token=security_token or None)


def build_acs3_headers(
    *,
    method: str,
    host: str,
    path: str,
    query: dict[str, Any] | None,
    body: bytes,
    action: str,
    version: str,
    credentials: Acs3Credentials,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, str]:
    method_upper = method.upper()
    canonical_uri = _normalize_path(path)
    canonical_query = _canonical_query(query)
    payload_hash = _sha256_hex(body)
    date = _utc_iso8601()
    nonce = uuid.uuid4().hex

    headers: dict[str, str] = {
        "host": host,
        "content-type": "application/json",
        "x-acs-action": action,
        "x-acs-version": version,
        "x-acs-date": date,
        "x-acs-signature-nonce": nonce,
        "x-acs-content-sha256": payload_hash,
    }
    if credentials.security_token:
        headers["x-acs-security-token"] = credentials.security_token
    if extra_headers:
        for key, value in extra_headers.items():
            headers[str(key).lower()] = str(value)

    signed_headers = sorted(headers.keys())
    canonical_header_str = _canonical_headers(headers, signed_headers)
    canonical_request = (
        f"{method_upper}\n"
        f"{canonical_uri}\n"
        f"{canonical_query}\n"
        f"{canonical_header_str}\n"
        f"{';'.join(signed_headers)}\n"
        f"{payload_hash}"
    )
    string_to_sign = f"ACS3-HMAC-SHA256\n{_sha256_hex(canonical_request.encode('utf-8'))}"
    signature = _hmac_sha256_hex(credentials.access_key_secret.encode("utf-8"), string_to_sign.encode("utf-8"))
    authorization = (
        "ACS3-HMAC-SHA256 "
        f"Credential={credentials.access_key_id},"
        f"SignedHeaders={';'.join(signed_headers)},"
        f"Signature={signature}"
    )
    headers["authorization"] = authorization
    return headers
