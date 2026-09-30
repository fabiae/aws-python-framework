"""Las settings globales de un servicio, con el transporte falseado bajo httpx.

Se falsea una capa por debajo de nuestro código, no nuestro código: lo que se
quiere comprobar es qué pide, a quién, y qué hace cuando no le contestan.

Correr con un intérprete que tenga las dependencias del paquete:
    ../constitution-core/venv/bin/python tests/test_settings.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

from aws_python_helper import settings

failures = []


def check(label, condition):
    print(f"  {'ok  ' if condition else 'FALLA'} {label}")
    if not condition:
        failures.append(label)


class FakeCore:
    def __init__(self, body=None, fail=False):
        self.body, self.fail, self.calls, self.url = body or {}, fail, 0, None
        fake = self

        class Client:
            def __init__(self, **kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def get(self, url, headers=None):
                fake.calls += 1
                fake.url, fake.headers = url, headers
                if fake.fail:
                    raise httpx.ConnectError("core no responde")
                return httpx.Response(200, json={"settings": fake.body},
                                      request=httpx.Request("GET", url))

        httpx.AsyncClient = Client


original = httpx.AsyncClient
settings.declare([
    {"code": "scraper_timeout", "type": "number", "default": 120},
    {"code": "modo", "type": "text", "default": "normal"},
])
os.environ.update(CORE_API_URL="https://core.example", SERVICE_CODE="dockets",
                  INTER_SERVICE_TOKEN="un-token")

print("== pide las suyas, diciendo quién es ==")
core = FakeCore({"scraper_timeout": 300})
settings.reset()
check("el valor de core gana sobre el default", asyncio.run(settings.get("scraper_timeout")) == 300)
check("lo que core no manda queda en su default", asyncio.run(settings.get("modo")) == "normal")
check("pide sólo las suyas", core.url.endswith("?service=dockets"))
check("se identifica como servicio", "authorization" in (core.headers or {}))

print("\n== una sola llamada por contenedor ==")
antes = core.calls
asyncio.run(settings.get("modo"))
asyncio.run(settings.get("scraper_timeout"))
check(f"sin llamadas extra ({core.calls - antes})", core.calls == antes)

print("\n== si core no contesta, se sigue con los defaults ==")
caido = FakeCore(fail=True)
settings.reset()
check("no explota", asyncio.run(settings.get("scraper_timeout")) == 120)
antes = caido.calls
for _ in range(3):
    asyncio.run(settings.get("modo"))
check(f"y no pregunta por request ({caido.calls - antes} llamadas)", caido.calls == antes)

print("\n== sin SERVICE_CODE no puede decir quién es ==")
os.environ.pop("SERVICE_CODE", None)
os.environ.pop("NAMESPACE", None)
otro = FakeCore({"modo": "x"})
settings.reset()
check("cae al default en vez de romper", asyncio.run(settings.get("modo")) == "normal")

httpx.AsyncClient = original
print()
if failures:
    print(f"{len(failures)} fallas")
    sys.exit(1)
print("all good")
