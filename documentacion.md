# Documentación Automática Aprovechando el Framework

---

## La idea central

El framework ya tiene una convención: **carpeta + archivo = endpoint**.
Solo hay que extender esa misma convención dos pasos más:

```
Convención actual del framework:
  src/api/land-records/address/post.py   →   POST /land-records/address

Convención nueva para docs (misma idea):
  src/schemas/land_records/address.py    →   AddressFilters   (request body)
                                         →   AddressResponse  (response body)
```

Cuando el script encuentra `POST /land-records/address`, busca automáticamente en `src/schemas/land_records/address.py` las clases `*Filters` y `*Response`. Si las encuentra, la documentación completa se genera sola.

**Resultado: cero archivos YAML externos. Cero intervención manual.**

---

## Los 3 cambios que hacen todo automático

### Cambio 1 — Agregar clase `*Response` a los schemas existentes

Los schemas de request ya existen para 3 endpoints. Solo hay que agregar los de response al mismo archivo:

**Antes (src/schemas/land_records/address.py):**
```python
class AddressFilters(BaseModel):
    town:         Optional[Union[str, List[str]]] = None
    address:      Optional[Union[str, List[str]]] = None
    address_id:   Optional[Union[str, List[str]]] = None
    type_address: Optional[Union[str, List[str]]] = None
    limit:        Optional[int] = None
```

**Después (mismo archivo, se agrega la clase Response):**
```python
class AddressFilters(BaseModel):
    town:         Optional[Union[str, List[str]]] = None
    address:      Optional[Union[str, List[str]]] = None
    address_id:   Optional[Union[str, List[str]]] = None
    type_address: Optional[Union[str, List[str]]] = None
    limit:        Optional[int] = None


class AddressItem(BaseModel):
    owner:      str
    address:    str
    town:       str

class AddressResponse(BaseModel):
    success:                 bool
    title_search_requested:  List[AddressItem]
    title_search_excluded:   List[dict]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "title_search_requested": [
                    {"owner": "JOHN DOE", "address": "107 FAIRVIEW ST, NEW BRITAIN, CT", "town": "new britain"}
                ],
                "title_search_excluded": [
                    {"owner": "JANE DOE", "address": "200 MAIN ST, HARTFORD, CT", "reason": "Already searched in the last 15 days"}
                ]
            }
        }
    )
```

---

### Cambio 2 — Crear schemas para los 6 endpoints que no los tienen

Los 6 endpoints sin schema Pydantic actualmente. Hay que crearlos (trabajo de ~1 hora total):

```
src/schemas/auth/login.py      →  LoginFilters + LoginResponse
src/schemas/auth/logout.py     →  (no body)   + LogoutResponse
src/schemas/land_records/polygons.py  →  PolygonsFilters + PolygonsResponse
src/schemas/land_records/list_keys.py →  ListKeysFilters + ListKeysResponse
src/schemas/polygons/list.py   →  (no body)   + PolygonsListResponse
src/schemas/polygons/get.py    →  (no body)   + PolygonGetResponse
```

Ejemplo para `auth/login`:
```python
# src/schemas/auth/login.py

class LoginFilters(BaseModel):
    email:    str = Field(..., example="user@example.com")
    password: str = Field(..., example="mypassword123")

class LoginUser(BaseModel):
    id:    str
    email: str
    name:  str
    role:  str

class LoginResponse(BaseModel):
    success:    bool
    token:      str
    user:       LoginUser
    expires_at: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "token": "KX5Z8j9mN-pQ2r_tU3vW4xY5z",
                "user": {"id": "507f1f77bcf86cd799439011", "email": "user@example.com", "name": "John Doe", "role": "user"},
                "expires_at": "2026-04-24T21:45:00"
            }
        }
    )
```

---

### Cambio 3 — Agregar dos atributos de clase a cada API

Esto es lo que conecta el código con la documentación. Un solo import + dos líneas por archivo:

**Antes (src/api/land-records/address/post.py):**
```python
class AddressPostAPI(API):

    def __init__(self, *args, **kwargs):
        ...
```

**Después (solo se agregan 2 líneas):**
```python
from schemas.land_records.address import AddressFilters, AddressResponse

class AddressPostAPI(API):
    request_schema  = AddressFilters   # ← el script lee esto para el request body
    response_schema = AddressResponse  # ← el script lee esto para el response body

    def __init__(self, *args, **kwargs):
        ...
```

Esto es exactamente el mismo patrón que FastAPI usa con type hints, pero adaptado al framework custom. **No rompe nada**, son atributos de clase que el framework actual simplemente ignora.

---

## El script actualizado (100% automático)

```python
#!/usr/bin/env python3
"""
generate_docs.py
Generates docs/openapi.yaml by scanning src/api/ and src/schemas/.
Zero external YAML files needed.

Convention:
  - Endpoint discovered from: src/api/{resource}/{endpoint}/{method}.py
  - Description from:         module docstring of the API file
  - Tags from:                first folder level under src/api/
  - Request schema from:      class attribute: request_schema = XFilters
  - Response schema from:     class attribute: response_schema = XResponse

Run from repo root:
    python scripts/generate_docs.py
    redocly build-docs docs/openapi.yaml -o docs/index.html
"""

import ast
import importlib
import json
import sys
from pathlib import Path

import yaml

# ── Paths ─────────────────────────────────────────────────────────────────
REPO_ROOT   = Path(__file__).parent.parent
SRC_ROOT    = REPO_ROOT / "src"
API_ROOT    = SRC_ROOT / "api"
DOCS_DIR    = REPO_ROOT / "docs"
OUTPUT_YAML = DOCS_DIR / "openapi.yaml"

sys.path.insert(0, str(SRC_ROOT))

# ── Tag mapping (auto-derived from first folder level) ────────────────────
TAG_DESCRIPTIONS = {
    "auth":          "Obtain and revoke access tokens. No Authorization header required.",
    "land-records":  "Search addresses and start the scraping process asynchronously. Results are available via /land-records/results after receiving the completion email.",
    "polygons":      "Manage geographic polygons and search land records within a polygon area.",
}

# ── Standard headers ───────────────────────────────────────────────────────
HEADER_AUTH = {
    "name": "Authorization", "in": "header", "required": True,
    "schema": {"type": "string"},
    "description": "Bearer token — `Authorization: Bearer <token>`",
    "example": "Bearer KX5Z8j9mN-pQ2r_tU3vW4xY5z",
}
HEADER_STATE = {
    "name": "constitution-state", "in": "header", "required": True,
    "schema": {"type": "string", "enum": ["connecticut"]},
    "description": "State to query. Currently only `connecticut` is supported.",
    "example": "connecticut",
}
PARAM_IDENTIFIER = {
    "name": "identifier", "in": "path", "required": True,
    "schema": {"type": "string"},
    "description": "Polygon identifier (key or name)",
}

NO_AUTH_PATHS = {"/auth/login", "/auth/logout"}
STATE_PATHS   = {
    "/land-records/address", "/land-records/results",
    "/land-records/polygons", "/land-records/dockets",
    "/land-records/list-keys", "/polygons", "/polygons/{identifier}",
}


# ── 1. File → (HTTP method, URL path, tag) ────────────────────────────────
def file_to_endpoint(api_file: Path) -> tuple[str, str, str]:
    parts   = list(api_file.relative_to(API_ROOT).parts)
    stem    = parts[-1].replace(".py", "").lower()
    folders = parts[:-1]
    tag     = folders[0] if folders else "general"

    if stem == "list":
        return "GET", "/" + "/".join(folders), tag
    if stem == "get":
        return "GET", "/" + "/".join(folders + ["{identifier}"]), tag
    return stem.upper(), "/" + "/".join(folders), tag


# ── 2. Module docstring ───────────────────────────────────────────────────
def module_docstring(filepath: Path) -> str:
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
        doc  = ast.get_docstring(tree) or ""
        lines = [l for l in doc.splitlines()
                 if not l.strip().startswith(("GET ", "POST ", "PUT ", "DELETE "))]
        return "\n".join(lines).strip()
    except Exception:
        return ""


# ── 3. Read class-level schema attributes via AST ─────────────────────────
def read_class_schemas(filepath: Path) -> tuple[str | None, str | None]:
    """
    Reads:
        request_schema  = XFilters
        response_schema = XResponse
    from the class body without importing the full application.
    Returns (request_schema_name, response_schema_name) or (None, None).
    """
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                req, res = None, None
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name):
                                if target.id == "request_schema" and isinstance(item.value, ast.Name):
                                    req = item.value.id
                                if target.id == "response_schema" and isinstance(item.value, ast.Name):
                                    res = item.value.id
                if req or res:
                    return req, res
    except Exception:
        pass
    return None, None


# ── 4. Import a class by name, given the file's import statements ──────────
def import_schema_class(filepath: Path, class_name: str):
    """
    Finds 'from schemas.X.Y import Z' in the file and imports Z.
    """
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("schemas."):
                    for alias in node.names:
                        name = alias.asname or alias.name
                        if name == class_name:
                            mod = importlib.import_module(module)
                            return getattr(mod, alias.name, None)
    except Exception:
        pass
    return None


# ── 5. Clean Pydantic v2 schema for OpenAPI 3.0 ────────────────────────────
def simplify_schema(obj):
    """Converts anyOf:[T, null] → {type:T, nullable:true} for cleaner ReDoc output."""
    if isinstance(obj, dict):
        if "anyOf" in obj:
            non_null = [t for t in obj["anyOf"] if t != {"type": "null"}]
            if len(non_null) == 1:
                obj = {**non_null[0], **{k: v for k, v in obj.items() if k != "anyOf"}, "nullable": True}
        return {k: simplify_schema(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [simplify_schema(i) for i in obj]
    return obj


# ── 6. Build the complete spec ─────────────────────────────────────────────
def build_spec() -> dict:
    paths = {}
    found_tags = set()

    api_files = sorted(f for f in API_ROOT.rglob("*.py") if f.name != "__init__.py")

    for api_file in api_files:
        method, url_path, tag = file_to_endpoint(api_file)
        description           = module_docstring(api_file)
        req_name, res_name    = read_class_schemas(api_file)

        req_class = import_schema_class(api_file, req_name) if req_name else None
        res_class = import_schema_class(api_file, res_name) if res_name else None
        found_tags.add(tag)

        # Headers
        parameters = []
        if url_path not in NO_AUTH_PATHS:
            parameters.append(HEADER_AUTH)
        if url_path in STATE_PATHS:
            parameters.append(HEADER_STATE)
        if "{identifier}" in url_path:
            parameters.append(PARAM_IDENTIFIER)

        operation = {
            "tags":        [tag],
            "summary":     description.split("\n")[0] if description else url_path,
            "description": description,
            "operationId": (
                url_path.strip("/")
                .replace("/", "_").replace("-", "_")
                .replace("{", "").replace("}", "")
                + "_" + method.lower()
            ),
            "parameters": parameters,
            "responses": {
                "400": {"description": "Bad request — missing or invalid parameters"},
                "401": {"description": "Unauthorized — missing or invalid token"},
                "422": {"description": "Validation error — check request body format"},
                "500": {"description": "Internal server error"},
            },
        }

        # Request body (from request_schema class attribute)
        if req_class and method in ("POST", "PUT", "PATCH"):
            raw   = req_class.model_json_schema()
            clean = simplify_schema(json.loads(json.dumps(raw)))
            clean.pop("title", None)
            operation["requestBody"] = {
                "required": True,
                "content": {"application/json": {"schema": clean}},
            }

        # Response body (from response_schema class attribute)
        if res_class:
            raw   = res_class.model_json_schema()
            clean = simplify_schema(json.loads(json.dumps(raw)))
            clean.pop("title", None)
            # Extract example from model_config json_schema_extra if present
            example = clean.pop("example", None)
            response_content = {"schema": clean}
            if example:
                response_content["example"] = example
            operation["responses"]["200"] = {
                "description": "Success",
                "content": {"application/json": response_content},
            }
        else:
            operation["responses"]["200"] = {"description": "Success"}

        paths.setdefault(url_path, {})[method.lower()] = operation

    # Build tags list preserving original order
    tags = [
        {
            "name":        t,
            "description": TAG_DESCRIPTIONS.get(t, ""),
        }
        for t in dict.fromkeys(  # preserve insertion order, deduplicate
            file_to_endpoint(f)[2]
            for f in sorted(f for f in API_ROOT.rglob("*.py") if f.name != "__init__.py")
        )
    ]

    return {
        "openapi": "3.0.1",
        "info": {
            "title":   "Constitution API",
            "version": "1.0.0",
            "description": (
                "API for searching and querying real estate land records.\n\n"
                "## Usage flow\n"
                "1. **Authenticate** — `POST /auth/login` → get token\n"
                "2. **Search** — `POST /land-records/address` or `POST /land-records/polygons`\n"
                "3. **Wait** — receive completion email (10–30 min)\n"
                "4. **Download** — `POST /land-records/results`"
            ),
            "contact": {"name": "Constitution Team"},
        },
        "servers": [{
            "url": "https://{api_gateway_url}",
            "description": "AWS API Gateway",
            "variables": {
                "api_gateway_url": {
                    "default":     "API_GATEWAY_URL",
                    "description": "Your AWS API Gateway base URL",
                }
            },
        }],
        "tags":  tags,
        "paths": paths,
    }


# ── Main ───────────────────────────────────────────────────────────────────
def main():
    DOCS_DIR.mkdir(exist_ok=True)

    print(f"Scanning {API_ROOT} ...")
    spec = build_spec()

    total = sum(len(v) for v in spec["paths"].values())
    print(f"Discovered {total} endpoints across {len(spec['paths'])} paths:")
    for path, methods in spec["paths"].items():
        for method, op in methods.items():
            has_req = "✓" if "requestBody" in op else "·"
            has_res = "✓" if "200" in op.get("responses", {}) and "content" in op["responses"]["200"] else "·"
            print(f"  {method.upper():6} {path:45} req:{has_req} res:{has_res}")

    OUTPUT_YAML.write_text(
        yaml.dump(spec, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"\nGenerated: {OUTPUT_YAML}")
    print("Next: redocly build-docs docs/openapi.yaml -o docs/index.html")


if __name__ == "__main__":
    main()
```

---

## Qué hace el desarrollador cuando agrega una API nueva

Solo tres pasos, todos en el mismo flujo de trabajo que ya tiene:

```
1. Crear la clase de API (lo hace igual que antes):
   src/api/land-records/new-endpoint/post.py

   - Agregar docstring de módulo (descripción que aparece en la doc)
   - Agregar los atributos de clase request_schema y response_schema

2. Crear el schema en src/schemas/ (siguiendo el patrón existente):
   src/schemas/land_records/new_endpoint.py

   - Clase NewEndpointFilters(BaseModel)  ← campos del request
   - Clase NewEndpointResponse(BaseModel) ← forma de la respuesta + ejemplo

3. git push → GitHub Actions genera openapi.yaml + index.html automáticamente
```

Ejemplo concreto — así quedaría un nuevo endpoint:

```python
# src/api/land-records/new-endpoint/post.py
"""
API to search land records by owner name.
"""
from aws_python_helper.api.base import API
from schemas.land_records.new_endpoint import NewEndpointFilters, NewEndpointResponse

class NewEndpointPostAPI(API):
    request_schema  = NewEndpointFilters   # ← script lee esto
    response_schema = NewEndpointResponse  # ← script lee esto

    async def validate(self):
        ...

    async def process(self):
        ...
```

```python
# src/schemas/land_records/new_endpoint.py
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

class NewEndpointFilters(BaseModel):
    owner: str = Field(..., example="JOHN DOE")
    limit: Optional[int] = Field(None, example=50)

class NewEndpointResponse(BaseModel):
    success: bool
    results: list

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "results": [{"owner": "JOHN DOE", "address": "107 FAIRVIEW ST"}]
            }
        }
    )
```

**El `index.html` se genera solo. Nadie toca archivos de documentación.**

---

## Qué hay que hacer ahora (una sola vez, para los 9 endpoints existentes)

| Endpoint | Acción en `src/schemas/` | Acción en el archivo API |
|---|---|---|
| POST /auth/login | Crear `auth/login.py` con `LoginFilters` + `LoginResponse` | Agregar `request_schema`, `response_schema` |
| POST /auth/logout | Crear `auth/logout.py` con `LogoutResponse` | Agregar `response_schema` |
| POST /land-records/address | Agregar `AddressResponse` al archivo existente | Agregar `response_schema` |
| POST /land-records/results | Agregar `ResultsResponse` al archivo existente | Agregar `response_schema` |
| POST /land-records/dockets | Agregar `DocketsResponse` al archivo existente | Agregar `response_schema` |
| POST /land-records/polygons | Crear `land_records/polygons.py` con `PolygonsFilters` + `PolygonsResponse` | Agregar ambos |
| POST /land-records/list-keys | Crear `land_records/list_keys.py` con `ListKeysFilters` + `ListKeysResponse` | Agregar ambos |
| GET /polygons | Crear `polygons/list.py` con `PolygonsListResponse` | Agregar `response_schema` |
| GET /polygons/{identifier} | Crear `polygons/get.py` con `PolygonGetResponse` | Agregar `response_schema` |

Esfuerzo estimado: **3-4 horas** para hacer todos los schemas de una vez. Después, el sistema se mantiene solo.

---

## Comparativa final — incluyendo esta versión

| | YAML manual | Script v1 (con responses.yaml) | **Script v2 (100% automático)** |
|---|:---:|:---:|:---:|
| Nuevo endpoint auto-documentado | ❌ | ✅ parcial | ✅ completo |
| Request body automático | ❌ | ✅ (si tiene Pydantic) | ✅ siempre |
| Response body automático | ❌ | ❌ | ✅ siempre |
| Archivos de docs a mantener | `openapi.yaml` | `responses.yaml` | **Ninguno** |
| Single source of truth | ❌ | ⚠️ | ✅ |
| Cambia el código de producción | ❌ | ❌ | Mínimo (2 líneas por clase) |

---

## GitHub Actions — sin cambios respecto al anterior

```yaml
on:
  push:
    paths:
      - "src/api/**"      # nuevo endpoint → se documenta solo
      - "src/schemas/**"  # cambio en un campo → doc se actualiza sola
      # Ya no hay docs/responses.yaml que monitorear
```

---

## Resumen en una línea

> El framework ya usa convención de carpetas para routing. Extendemos esa misma convención: cada endpoint declara `request_schema` y `response_schema` como atributos de clase. El script lee esos atributos. Cero archivos externos. La documentación vive dentro del código, al lado de la lógica que documenta.
