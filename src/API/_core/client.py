from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from src.common.errors import RetriableError, ValidationError
from src.common.requests_session import session as default_session


@dataclass(frozen=True)
class ApiClient:
    session: requests.Session = default_session
    default_timeout_sec: float = 10.0
    verify_ssl: bool = False

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        data: Any = None,
        json: Any = None,
        timeout: Optional[float] = None,
        verify: Optional[bool] = None,
    ) -> requests.Response:
        try:
            resp = self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=data,
                json=json,
                timeout=self.default_timeout_sec if timeout is None else timeout,
                verify=self.verify_ssl if verify is None else verify,
            )
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as e:
            raise RetriableError(str(e))

    def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        data: Any = None,
        json: Any = None,
        timeout: Optional[float] = None,
        verify: Optional[bool] = None,
    ) -> Dict[str, Any]:
        resp = self.request(
            method,
            url,
            headers=headers,
            params=params,
            data=data,
            json=json,
            timeout=timeout,
            verify=verify,
        )
        try:
            return resp.json()
        except Exception:
            text = ""
            try:
                text = resp.content.decode("utf-8", errors="replace")
            except Exception:
                try:
                    text = resp.text
                except Exception:
                    text = ""
            raise ValidationError(f"INVALID_JSON: {text[:200]}")

    def get_json(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        verify: Optional[bool] = None,
    ) -> Dict[str, Any]:
        return self.request_json(
            "GET",
            url,
            headers=headers,
            params=params,
            timeout=timeout,
            verify=verify,
        )

    def post_json(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Any = None,
        timeout: Optional[float] = None,
        verify: Optional[bool] = None,
    ) -> Dict[str, Any]:
        return self.request_json(
            "POST",
            url,
            headers=headers,
            params=params,
            json=json,
            timeout=timeout,
            verify=verify,
        )

    def post_form(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        data: Any = None,
        timeout: Optional[float] = None,
        verify: Optional[bool] = None,
    ) -> Dict[str, Any]:
        return self.request_json(
            "POST",
            url,
            headers=headers,
            params=params,
            data=data,
            timeout=timeout,
            verify=verify,
        )


default_client = ApiClient()

