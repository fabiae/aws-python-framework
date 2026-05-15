import json
import logging
import os
from typing import Any, Dict, Optional

import httpx

from .exceptions import ApiClientError, ApiResponseError, ServiceNotConfiguredError

logger = logging.getLogger(__name__)

_AUTH_HEADER = "Authorization"
_BEARER_PREFIX = "Bearer"


def _resolve_service_url(service_name: str) -> str:
    raw = os.getenv("MICROSERVICE_URLS", "")
    if not raw:
        raise ServiceNotConfiguredError(
            "MICROSERVICE_URLS environment variable is not set"
        )
    try:
        urls = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ServiceNotConfiguredError(
            "MICROSERVICE_URLS is not valid JSON"
        ) from exc

    url = urls.get(service_name)
    if not url:
        available = ", ".join(urls.keys()) or "none"
        raise ServiceNotConfiguredError(
            f"Service '{service_name}' not found in MICROSERVICE_URLS. Available: {available}"
        )
    return url.rstrip("/")


def _resolve_token() -> Optional[str]:
    token = os.getenv("INTER_SERVICE_TOKEN") or os.getenv("AUTH_BYPASS_TOKEN")
    if not token:
        logger.warning(
            "No inter-service token found. Set INTER_SERVICE_TOKEN or AUTH_BYPASS_TOKEN."
        )
    return token


class ApiClient:
    """
    HTTP client for inter-service communication.

    Resolves the target service URL from the MICROSERVICE_URLS environment variable
    and automatically attaches the inter-service auth token (INTER_SERVICE_TOKEN,
    falling back to AUTH_BYPASS_TOKEN).

    Usage:
        client = ApiClient("dockets")
        result = await client.post("/search", body={"keys": [...]})
        result = await client.get("/dockets/123")

        # Extra headers (e.g. constitution-state) merged with the default ones
        client = ApiClient("dockets", headers={"constitution-state": "CT"})

    Environment variables:
        MICROSERVICE_URLS     JSON map of service name → base URL
                              e.g. {"dockets": "https://api.example.com/"}
        INTER_SERVICE_TOKEN   Bearer token for service-to-service calls
        AUTH_BYPASS_TOKEN     Fallback if INTER_SERVICE_TOKEN is not set
    """

    def __init__(
        self,
        service_name: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
    ):
        self._base_url = _resolve_service_url(service_name)
        self._timeout = timeout
        self._headers = self._build_default_headers(headers or {})
        self.logger = logging.getLogger(self.__class__.__name__)

    def _build_default_headers(self, extra: Dict[str, str]) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        token = _resolve_token()
        if token:
            headers[_AUTH_HEADER] = f"{_BEARER_PREFIX} {token}"
        headers.update(extra)
        return headers

    def _url(self, path: str) -> str:
        return f"{self._base_url}/{path.lstrip('/')}"

    async def get(self, path: str, params: Optional[Dict] = None) -> Any:
        """GET request — single resource."""
        return await self._request("GET", path, params=params)

    async def list(self, path: str, params: Optional[Dict] = None) -> Any:
        """GET request — collection / list."""
        return await self._request("GET", path, params=params)

    async def post(self, path: str, body: Optional[Dict] = None) -> Any:
        """POST request."""
        return await self._request("POST", path, body=body)

    async def put(self, path: str, body: Optional[Dict] = None) -> Any:
        """PUT request."""
        return await self._request("PUT", path, body=body)

    async def patch(self, path: str, body: Optional[Dict] = None) -> Any:
        """PATCH request."""
        return await self._request("PATCH", path, body=body)

    async def delete(self, path: str, body: Optional[Dict] = None) -> Any:
        """DELETE request."""
        return await self._request("DELETE", path, body=body)

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        body: Optional[Dict] = None,
    ) -> Any:
        url = self._url(path)
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(
                    method,
                    url,
                    params=params,
                    json=body,
                    headers=self._headers,
                )
        except httpx.TimeoutException as exc:
            self.logger.error("Timeout calling %s %s", method, url)
            raise ApiClientError(f"Timeout calling {method} {url}") from exc
        except Exception as exc:
            self.logger.error("Error calling %s %s: %s", method, url, exc)
            raise ApiClientError(f"Error calling {method} {url}: {exc}") from exc

        if response.status_code >= 400:
            self.logger.error(
                "%s %s returned %d: %s", method, url, response.status_code, response.text
            )
            raise ApiResponseError(
                f"{method} {url} returned {response.status_code}",
                status_code=response.status_code,
                response_body=response.text,
            )

        try:
            return response.json()
        except Exception:
            return response.text
