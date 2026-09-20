"""Derives a service's permissions from the API files it actually has.

The endpoints are already declared twice — in the terraform routes and in the
file convention the dispatcher resolves on. A hand-written list would be a third
copy, and the first endpoint added without touching it would be an unguarded
hole nobody notices.

Mirrors `aws_python_helper.api.fetcher` in reverse: that one turns a request into
a file, this one turns the files into the requests they answer. It lives beside
the fetcher so the two cannot drift: a routing rule that changes in one would
otherwise silently stop matching in the other, and an access check that never
matches fails open or shut without anyone noticing.
"""

import os
from typing import Dict, List

from ..api.fetcher import Fetcher

# Cómo se llama el archivo según el método. `list` y `get` son ambos GET: uno
# responde la colección, el otro un elemento.
FILE_METHODS = {
    "list": "GET",
    "get": "GET",
    "post": "POST",
    "put": "PUT",
    "patch": "PATCH",
    "delete": "DELETE",
}

ALL = "*"


def discover(api_root: str, service: str) -> List[Dict[str, str]]:
    """Every endpoint this service answers, as permission records.

    The `{id}` of a route is left out on purpose: holding an id does not change
    who may call the endpoint, and leaving it out makes the mapping between a
    file and a permission exact.
    """
    found: List[Dict[str, str]] = []

    for current, _, files in os.walk(api_root):
        for filename in sorted(files):
            stem, extension = os.path.splitext(filename)
            if extension != ".py" or stem not in FILE_METHODS:
                continue

            relative = os.path.relpath(current, api_root)
            parts = [] if relative == "." else relative.split(os.sep)
            path = "/" + "/".join(parts)
            method = FILE_METHODS[stem]

            # `list` responde la colección y `get` un elemento: mismo método
            # sobre rutas distintas, así que son dos permisos, no uno.
            if stem == "get":
                path = f"{path.rstrip('/')}/{{id}}"

            found.append({
                "code": f"{service}:{method} {path}",
                "service": service,
                "method": method,
                "path": path,
                "scope": "item" if stem == "get" else "collection",
            })

    return sorted(found, key=lambda item: item["code"])


def service_wildcard(service: str) -> str:
    return f"{service}:*"


def required_for(service: str, method: str, endpoint: str, api_root: str = "api") -> str:
    """The permission a request needs.

    Asks the framework which file will answer, and names the permission after it.
    Reimplementing the routing rules here would be a second copy that drifts, and
    a permission that never matches fails open or shut without anyone noticing —
    which is the worst way for an access check to be wrong.
    """
    resolved = Fetcher(endpoint, method.lower()).file_path
    marker = os.sep + api_root + os.sep
    if marker not in resolved:
        return ""

    relative = resolved.split(marker, 1)[1]
    directory, filename = os.path.split(relative)
    stem = os.path.splitext(filename)[0]
    if stem not in FILE_METHODS:
        return ""

    path = "/" + directory.replace(os.sep, "/") if directory else "/"
    if stem == "get":
        path = f"{path.rstrip('/')}/{{id}}"
    return f"{service}:{FILE_METHODS[stem]} {path}"


def allows(granted: List[str], required: str) -> bool:
    """Whether a set of granted permissions covers the one an endpoint needs."""
    if not required:
        return False
    if ALL in granted or required in granted:
        return True
    return service_wildcard(required.split(":", 1)[0]) in granted
