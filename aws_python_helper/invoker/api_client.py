import logging
import os
from typing import Any, Dict, Optional

import httpx

from .exceptions import ApiClientError, ApiResponseError, ServiceNotConfiguredError

logger = logging.getLogger(__name__)

_AUTH_HEADER = "Authorization"
_BEARER_PREFIX = "Bearer"


CORE = "core"

# Lo que este contenedor ya averiguó. Vive lo que vive la lambda, que es lo que
# se quiere: un servicio redesplegado con otra URL se conoce en el próximo
# arranque en frío, no dentro de horas.
_RESOLVED: Dict[str, str] = {}


def _core_url() -> str:
    """Dónde está core. Es lo único que un servicio necesita saber de memoria.

    Todo lo demás se lo pregunta a core, que lleva el registro de quién existe y
    dónde responde. Una sola variable por servicio en vez de un mapa que había
    que escribir en el secret de cada uno y mantener sincronizado a mano.
    """
    url = (os.getenv("CORE_API_URL") or "").rstrip("/")
    if not url:
        raise ServiceNotConfiguredError(
            "CORE_API_URL is not set: this service cannot reach core, and core is "
            "where it learns about everything else."
        )
    return url


async def resolve_service_url(service_name: str) -> str:
    """La dirección de un servicio, según el registro de core."""
    if service_name == CORE:
        return _core_url()

    if service_name in _RESOLVED:
        return _RESOLVED[service_name]

    token = _resolve_token()
    headers = {_AUTH_HEADER: f"{_BEARER_PREFIX} {token}"} if token else {}

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{_core_url()}/services", headers=headers)
        response.raise_for_status()
        services = (response.json() or {}).get("services") or []

    for service in services:
        if service.get("api_url"):
            _RESOLVED[service["code"]] = service["api_url"].rstrip("/")

    url = _RESOLVED.get(service_name)
    if not url:
        known = ", ".join(sorted(_RESOLVED)) or "none"
        raise ServiceNotConfiguredError(
            f"Core does not know a service called '{service_name}'. Registered: {known}. "
            "A service appears here when it deploys."
        )
    return url


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
        CORE_API_URL          Where core answers. The only address a service
                              holds; everything else it asks core for.
        INTER_SERVICE_TOKEN   Bearer token for service-to-service calls
        AUTH_BYPASS_TOKEN     Fallback if INTER_SERVICE_TOKEN is not set
    """

    def __init__(
        self,
        service_name: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
    ):
        self._service_name = service_name
        self._base_url: Optional[str] = None
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

    async def _url(self, path: str) -> str:
        """La URL completa, resolviendo el servicio la primera vez que hace falta.

        Se resuelve al usarse y no al construirse porque preguntarle a core es
        una llamada de red, y un constructor que hace una llamada de red no se
        puede usar en ningún lado sin pensarlo.
        """
        if self._base_url is None:
            self._base_url = await resolve_service_url(self._service_name)
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
        url = await self._url(path)
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
