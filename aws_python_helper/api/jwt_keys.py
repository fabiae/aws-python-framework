"""Where a service gets the key that verifies core's signatures.

Core signs; everybody else verifies. The key is public —with it you check a
signature, you cannot produce one— so the only real question is how it travels.

It used to travel as an environment variable, which meant the same public fact
sat in every service's secret. Five copies of one thing: rotating the key was
five edits and five deploys, and any one of them could be the stale one, which
fails as "invalid token" and looks like a problem with the user.

So core publishes it at `GET /jwks` —public, because a service reads it exactly
when it cannot authenticate anything yet— and the services read it from there.
Nothing to copy, nothing to keep in sync, and rotation becomes something core
does alone.
"""

import base64
import logging
import os
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

PATH = "/jwks"

# Un kid desconocido puede ser una rotación recién hecha o un token inventado.
# Volver a preguntar cubre lo primero; el piso evita que lo segundo se convierta
# en una llamada a core por cada request.
REFETCH_FLOOR_SECONDS = 60
TIMEOUT_SECONDS = 5

_keys: Dict[str, Any] = {}
_last_fetch: Optional[float] = None


def configured_key() -> Optional[str]:
    """The key pinned in the environment, if there is one.

    Core holds the pair and verifies its own tokens, so asking it to fetch over
    HTTP something it already has would be a service calling itself. It is also
    the way out: set the variable anywhere and that service stops depending on
    the endpoint.
    """
    raw = (os.getenv('JWT_PUBLIC_KEY') or '').strip()
    if not raw:
        return None
    if raw.startswith('-----BEGIN'):
        return raw
    # PEMs are multi-line, so they travel base64-encoded in env vars.
    return base64.b64decode(raw).decode('utf-8')


def reset() -> None:
    """Forget what was fetched. For tests."""
    global _last_fetch
    _keys.clear()
    _last_fetch = None


def _core_url() -> str:
    url = (os.getenv('CORE_API_URL') or '').rstrip('/')
    if not url:
        raise ValueError(
            "Neither JWT_PUBLIC_KEY nor CORE_API_URL is set: this service has no "
            "way to learn the key that verifies core's tokens."
        )
    return url


def _lookup(kid: Optional[str]) -> Optional[Any]:
    if not _keys:
        return None
    if kid:
        return _keys.get(kid)
    # Sin kid sólo hay una respuesta sensata si core publica una sola clave. Con
    # dos, elegir una sería aceptar como buena una firma que quizá no lo es.
    return next(iter(_keys.values())) if len(_keys) == 1 else None


async def _refresh() -> None:
    global _last_fetch
    _last_fetch = time.monotonic()

    import httpx
    from jwt.algorithms import RSAAlgorithm

    url = f"{_core_url()}{PATH}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.get(url)
        response.raise_for_status()
        published = response.json()
    except Exception as exc:
        raise ValueError(f"Could not read the signing keys from {url}: {exc}") from exc

    found = {}
    for entry in published.get('keys') or []:
        kid = entry.get('kid')
        if not kid:
            continue
        try:
            found[kid] = RSAAlgorithm.from_jwk(entry)
        except Exception as exc:
            # Una clave ilegible no invalida a las demás: la que sirve, sirve.
            logger.warning("Ignoring key %s published by core: %s", kid, exc)

    if not found:
        raise ValueError(f"{url} published no usable signing key")

    _keys.clear()
    _keys.update(found)
    logger.info("Signing keys loaded from core: %s", ", ".join(sorted(_keys)))


async def resolve(kid: Optional[str] = None) -> Any:
    """The key that verifies a token signed with `kid`.

    Cached for the life of the container: one call per cold start, not per
    request.
    """
    pinned = configured_key()
    if pinned:
        return pinned

    key = _lookup(kid)
    if key is not None:
        return key

    if _last_fetch is None or (time.monotonic() - _last_fetch) >= REFETCH_FLOOR_SECONDS:
        await _refresh()
        key = _lookup(kid)

    if key is None:
        raise ValueError(
            f"Core published no signing key with kid {kid!r}. "
            "A token signed with a retired key looks exactly like this."
        )
    return key
