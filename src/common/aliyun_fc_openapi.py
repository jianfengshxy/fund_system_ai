from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlencode

import requests

from src.common.aliyun_acs3 import Acs3Credentials, build_acs3_headers, load_acs3_credentials
from src.common.logger import get_logger

logger = get_logger(__name__)


class FcOpenApiClient:
    def __init__(
        self,
        *,
        account_id: str | None = None,
        region: str | None = None,
        credentials: Acs3Credentials | None = None,
        timeout_seconds: int = 15,
    ) -> None:
        self.account_id = (account_id or os.getenv("ALIYUN_ACCOUNT_ID") or "1238993556817547").strip()
        self.region = (region or os.getenv("ALIYUN_REGION") or "cn-shanghai").strip()
        self.credentials = credentials or load_acs3_credentials()
        self.timeout_seconds = timeout_seconds
        self.host = f"{self.account_id}.{self.region}.fc.aliyuncs.com"
        self.base_url = f"https://{self.host}"

    def _request(
        self,
        *,
        action: str,
        method: str,
        path: str,
        query: dict[str, Any] | None = None,
        body_obj: Any | None = None,
        extra_headers: dict[str, str] | None = None,
        raw_response: bool = False,
    ) -> Any:
        body_bytes = b""
        if body_obj is not None:
            body_bytes = json.dumps(body_obj, ensure_ascii=False).encode("utf-8")
        headers = build_acs3_headers(
            method=method,
            host=self.host,
            path=path,
            query=query,
            body=body_bytes,
            action=action,
            version="2023-03-30",
            credentials=self.credentials,
            extra_headers=extra_headers,
        )
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urlencode({k: v for k, v in query.items() if v is not None})}"
        response = requests.request(
            method=method.upper(),
            url=url,
            headers=headers,
            data=body_bytes if body_bytes else None,
            timeout=self.timeout_seconds,
        )
        if raw_response:
            return response
        if response.status_code >= 400:
            raise RuntimeError(f"FC OpenAPI 调用失败 status={response.status_code} body={response.text[:2000]}")
        if not response.text:
            return None
        try:
            return response.json()
        except Exception:
            return response.text

    def list_triggers(self, function_name: str, *, prefix: str | None = None, limit: int = 100) -> Any:
        return self._request(
            action="ListTriggers",
            method="GET",
            path=f"/2023-03-30/functions/{function_name}/triggers",
            query={"prefix": prefix, "limit": limit},
            body_obj=None,
        )

    def list_functions(self, *, prefix: str | None = None, limit: int = 100, next_token: str | None = None) -> Any:
        return self._request(
            action="ListFunctions",
            method="GET",
            path="/2023-03-30/functions",
            query={"prefix": prefix, "limit": limit, "nextToken": next_token},
            body_obj=None,
        )

    def get_function(self, function_name: str) -> Any:
        return self._request(
            action="GetFunction",
            method="GET",
            path=f"/2023-03-30/functions/{function_name}",
            query=None,
            body_obj=None,
        )

    def get_trigger(self, function_name: str, trigger_name: str) -> Any:
        return self._request(
            action="GetTrigger",
            method="GET",
            path=f"/2023-03-30/functions/{function_name}/triggers/{trigger_name}",
            query=None,
            body_obj=None,
        )

    def create_timer_trigger(
        self,
        *,
        function_name: str,
        trigger_name: str,
        cron_expression: str,
        payload: str | dict[str, Any] | None,
        enable: bool,
        qualifier: str = "LATEST",
        description: str | None = None,
    ) -> Any:
        payload_str: str = ""
        if isinstance(payload, dict):
            payload_str = json.dumps(payload, ensure_ascii=False)
        elif isinstance(payload, str):
            payload_str = payload
        trigger_config = {"cronExpression": cron_expression, "payload": payload_str, "enable": bool(enable)}
        body = {
            "triggerName": trigger_name,
            "triggerType": "timer",
            "qualifier": qualifier,
            "triggerConfig": json.dumps(trigger_config, ensure_ascii=False),
        }
        if description:
            body["description"] = description
        return self._request(
            action="CreateTrigger",
            method="POST",
            path=f"/2023-03-30/functions/{function_name}/triggers",
            query=None,
            body_obj=body,
        )

    def update_timer_trigger(
        self,
        *,
        function_name: str,
        trigger_name: str,
        cron_expression: str,
        payload: str | dict[str, Any] | None,
        enable: bool,
        qualifier: str = "LATEST",
        description: str | None = None,
    ) -> Any:
        payload_str: str = ""
        if isinstance(payload, dict):
            payload_str = json.dumps(payload, ensure_ascii=False)
        elif isinstance(payload, str):
            payload_str = payload
        trigger_config = {"cronExpression": cron_expression, "payload": payload_str, "enable": bool(enable)}
        body = {"qualifier": qualifier, "triggerConfig": json.dumps(trigger_config, ensure_ascii=False)}
        if description is not None:
            body["description"] = description
        return self._request(
            action="UpdateTrigger",
            method="PUT",
            path=f"/2023-03-30/functions/{function_name}/triggers/{trigger_name}",
            query=None,
            body_obj=body,
        )

    def delete_trigger(self, function_name: str, trigger_name: str) -> Any:
        return self._request(
            action="DeleteTrigger",
            method="DELETE",
            path=f"/2023-03-30/functions/{function_name}/triggers/{trigger_name}",
            query=None,
            body_obj=None,
        )

    def invoke_function(
        self,
        function_name: str,
        payload: Any = None,
        *,
        qualifier: str = "LATEST",
        timeout_seconds: int = 600,
    ) -> dict[str, Any]:
        """同步调用 FC 函数（InvokeFunction），返回执行结果。

        与 _request 不同，InvokeFunction 的 body 是原始 payload 字符串（非 JSON 包装），
        且需要读取响应头中的 x-fc-request-id，因此独立实现。

        Returns:
            {"request_id": str, "status_code": int, "body": Any, "raw_body": str}
        """
        body_bytes = b""
        if payload is not None:
            if isinstance(payload, str):
                body_bytes = payload.encode("utf-8")
            else:
                body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        acs_headers = build_acs3_headers(
            method="POST",
            host=self.host,
            path=f"/2023-03-30/functions/{function_name}/invocations",
            query={"qualifier": qualifier},
            body=body_bytes,
            action="InvokeFunction",
            version="2023-03-30",
            credentials=self.credentials,
            extra_headers={"x-fc-invocation-type": "Sync"},
        )
        url = f"{self.base_url}/2023-03-30/functions/{function_name}/invocations?qualifier={qualifier}"
        response = requests.request(
            method="POST",
            url=url,
            headers=acs_headers,
            data=body_bytes if body_bytes else None,
            timeout=timeout_seconds,
        )

        request_id = response.headers.get("x-fc-request-id", "")
        if response.status_code >= 400:
            raise RuntimeError(
                f"FC InvokeFunction 调用失败 status={response.status_code} "
                f"request_id={request_id} body={response.text[:2000]}"
            )

        raw_body = response.text
        try:
            body = json.loads(raw_body) if raw_body.strip() else {}
        except Exception:
            body = {"raw_output": raw_body}

        return {"request_id": request_id, "status_code": response.status_code, "body": body, "raw_body": raw_body}
