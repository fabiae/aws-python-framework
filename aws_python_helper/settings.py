"""Las settings globales de un servicio: las que no dependen de ningún estado.

El código declara **qué settings existen** y su default; el valor lo pone una
persona en el panel. Si el valor viniera del código sería una variable de
entorno con más pasos, y si la declaración viniera del panel nadie garantizaría
que el nombre coincide con lo que el código lee.

Se anuncian al desplegarse, en el mismo lugar que los permisos: las dos cosas
son parte de lo que el servicio *es*, se derivan del código, y core las
sincroniza —lo que ya no está declarado, se va—.

    # en el servicio
    SETTINGS = [
        {"code": "scraper_timeout", "type": "number", "default": 120,
         "label": "Timeout del scraper"},
    ]

    # donde haga falta el valor
    from aws_python_helper import settings
    timeout = await settings.get("scraper_timeout")

Una llamada a core por cold start, no por request. Si core no responde se usa el
default declarado, que es mejor que no arrancar: una setting es un ajuste, no un
requisito.
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PATH = "/services/settings"
TIMEOUT_SECONDS = 5
# Si core no contestó, no se vuelve a preguntar en cada request.
RETRY_FLOOR_SECONDS = 60

_values: Optional[Dict[str, Any]] = None
_last_try: Optional[float] = None
_defaults: Dict[str, Any] = {}


def declare(settings: List[Dict[str, Any]]) -> None:
    """Los defaults del código, para poder responder sin core.

    Lo llama el servicio al arrancar con su propia lista, la misma que publica.
    """
    _defaults.clear()
    for item in settings:
        if item.get("code"):
            _defaults[item["code"]] = item.get("default")


def reset() -> None:
    """Olvida lo traído. Para tests."""
    global _values, _last_try
    _values, _last_try = None, None


def _core_url() -> str:
    url = (os.getenv("CORE_API_URL") or "").rstrip("/")
    if not url:
        raise ValueError("CORE_API_URL is not set: this service cannot read its settings")
    return url


def _service_code() -> str:
    """Quién soy, con el mismo nombre con el que me registré en core."""
    code = (os.getenv("SERVICE_CODE") or os.getenv("NAMESPACE") or "").strip().lower()
    if not code:
        raise ValueError("SERVICE_CODE is not set: this service cannot say who it is")
    return code


async def _fetch() -> Dict[str, Any]:
    import httpx

    token = os.getenv("INTER_SERVICE_TOKEN") or ""
    url = f"{_core_url()}{PATH}?service={_service_code()}"
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        response = await client.get(url, headers={"authorization": f"Bearer {token}"})
    response.raise_for_status()
    body = response.json()
    return body.get("settings") or {}


async def all() -> Dict[str, Any]:
    """Todas las settings de este servicio, una vez por contenedor."""
    global _values, _last_try

    if _values is not None:
        return _values

    if _last_try is not None and (time.monotonic() - _last_try) < RETRY_FLOOR_SECONDS:
        return dict(_defaults)

    _last_try = time.monotonic()
    try:
        _values = {**_defaults, **await _fetch()}
    except Exception as exc:
        # Sin settings el servicio corre con sus defaults. Quedarse sin arrancar
        # porque core no contestó sería peor que el ajuste que no se aplicó.
        logger.warning("Could not read settings from core, using declared defaults: %s", exc)
        return dict(_defaults)

    return _values


async def get(code: str, default: Any = None) -> Any:
    """El valor de una setting, o su default declarado."""
    values = await all()
    value = values.get(code)
    return _defaults.get(code, default) if value is None else value
