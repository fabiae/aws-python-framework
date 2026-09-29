"""A real key, a real token, and core's own code publishing it.

The point of testing it this way: every part of this chain has a mockable seam,
and mocking any of them would have hidden the bug it was written to catch. The
key is generated here, core's controller turns it into JWKS, the transport is
faked one layer below httpx, and PyJWT verifies the signature for real.

Runs with plain `python tests/test_jwt_keys.py`.
"""

import asyncio
import base64
import importlib.util
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
import jwt as pyjwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from aws_python_helper.api import jwt_keys

# El controlador de core vive en otro repo, al lado de éste. Si no está, la
# parte que lo usa se saltea en vez de dar una falla que no es del framework.
CORE_SRC = os.path.abspath(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..", "constitution-core", "src"))
CORE = os.path.join(CORE_SRC, "api", "jwks", "list.py")

failures = []


def check(label, condition):
    print(f"  {'ok  ' if condition else 'FALLA'} {label}")
    if not condition:
        failures.append(label)


def load_core_controller():
    """Se carga por ruta, que es como lo carga el fetcher en la lambda."""
    # En la lambda el cwd es la raíz del paquete, así que `helpers` se importa
    # por nombre absoluto. Acá hay que ponerla a mano.
    if CORE_SRC not in sys.path:
        sys.path.insert(0, CORE_SRC)
    spec = importlib.util.spec_from_file_location("core_jwt_keys", os.path.abspath(CORE))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_key():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_private = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()).decode()
    pem_public = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    return pem_private, pem_public


class FakeCore:
    """Habla el idioma de httpx, no el de nuestro código."""

    def __init__(self, body, status=200):
        self.body, self.status, self.calls = body, status, 0

    def install(self):
        fake = self

        class Client:
            def __init__(self, **kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def get(self, url):
                fake.calls += 1
                if fake.status >= 400:
                    raise httpx.ConnectError("core no responde")
                return httpx.Response(fake.status, json=fake.body,
                                      request=httpx.Request("GET", url))

        httpx.AsyncClient = Client


original_client = httpx.AsyncClient
pem_private, pem_public = make_key()

if not os.path.exists(CORE):
    print(f"constitution-core no está en {CORE_SRC}: se saltea la parte de core")
    sys.exit(0)

print("== core arma el JWKS con su propio código ==")
os.environ["JWT_PRIVATE_KEY"] = pem_private
os.environ["JWT_KID"] = "core-2026"
load_core_controller()
from helpers import jwt_issuer
jwks = {"keys": [jwt_issuer.public_jwk()]}
check("publica un kid", jwks["keys"][0]["kid"] == "core-2026")
check("es una clave RSA para firmar", jwks["keys"][0]["kty"] == "RSA" and jwks["keys"][0]["alg"] == "RS256")
check("no filtra la clave privada", "PRIVATE" not in json.dumps(jwks))

print("\n== un servicio sin la clave la baja de core ==")
os.environ["CORE_API_URL"] = "https://core.example"
jwt_keys.reset()
fake = FakeCore(jwks)
fake.install()

token = pyjwt.encode({"sub": "u1", "email": "a@b.c", "iss": "constitution-core"},
                     pem_private, algorithm="RS256", headers={"kid": "core-2026"})

from aws_python_helper.api.auth_validators import JWTValidator
auth = asyncio.run(JWTValidator().validate_token(token))
check("verifica un token real firmado por core", auth["user_id"] == "u1")
check("una sola llamada a core", fake.calls == 1)

asyncio.run(JWTValidator().validate_token(token))
check("el segundo request no vuelve a preguntar", fake.calls == 1)

print("\n== una firma que no es de core no pasa ==")
_, otro_public = make_key()
otro_private, _ = make_key()
falso = pyjwt.encode({"sub": "u1", "iss": "constitution-core"}, otro_private,
                     algorithm="RS256", headers={"kid": "core-2026"})
try:
    asyncio.run(JWTValidator().validate_token(falso))
    check("rechaza una firma ajena", False)
except Exception as exc:
    check(f"rechaza una firma ajena ({type(exc).__name__})", True)

print("\n== rotación: un kid nuevo hace preguntar de nuevo ==")
nuevo_private, nuevo_public = make_key()
os.environ["JWT_PRIVATE_KEY"] = nuevo_private
os.environ["JWT_KID"] = "core-2027"
# Core cachea la clave por contenedor, que es lo correcto en una lambda. Acá hay
# que soltarla para poder simular una rotación en el mismo proceso.
jwt_issuer._private_key_cache = None
jwks_rotado = {"keys": [jwt_issuer.public_jwk()]}
fake.body = jwks_rotado
jwt_keys._last_fetch = time.monotonic() - jwt_keys.REFETCH_FLOOR_SECONDS - 1
rotado = pyjwt.encode({"sub": "u2", "iss": "constitution-core"}, nuevo_private,
                      algorithm="RS256", headers={"kid": "core-2027"})
auth = asyncio.run(JWTValidator().validate_token(rotado))
check("acepta el token de la clave nueva", auth["user_id"] == "u2")
check("volvió a preguntar una sola vez", fake.calls == 2)

print("\n== un kid inventado no dispara una llamada por request ==")
antes = fake.calls
inventado = pyjwt.encode({"sub": "x", "iss": "constitution-core"}, nuevo_private,
                         algorithm="RS256", headers={"kid": "no-existe"})
for _ in range(3):
    try:
        asyncio.run(JWTValidator().validate_token(inventado))
    except Exception:
        pass
check("el piso de tiempo aguanta", fake.calls == antes)

print("\n== la clave fijada gana, y core no se llama a sí mismo ==")
os.environ["JWT_PUBLIC_KEY"] = nuevo_public
antes = fake.calls
auth = asyncio.run(JWTValidator().validate_token(rotado))
check("usa la del ambiente", auth["user_id"] == "u2")
check("no llamó a core", fake.calls == antes)

print("\n== sin clave y sin CORE_API_URL, el error dice qué falta ==")
del os.environ["JWT_PUBLIC_KEY"]
del os.environ["CORE_API_URL"]
jwt_keys.reset()
try:
    asyncio.run(JWTValidator().validate_token(rotado))
    check("explica el problema", False)
except ValueError as exc:
    check(f"explica el problema: {exc}"[:90], "CORE_API_URL" in str(exc))

httpx.AsyncClient = original_client
print()
if failures:
    print(f"{len(failures)} fallas")
    sys.exit(1)
print("all good")
