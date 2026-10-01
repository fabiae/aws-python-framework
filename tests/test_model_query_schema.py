"""Lo que el payload manda llega al código, o se pierde en silencio.

El schema usa `extra="ignore"`, así que un parámetro que no esté declarado
**desaparece sin error**. Ya pasó dos veces: `database` hacía que la consulta
fuera a la base equivocada y devolviera vacío, y `service` hacía que el recorte
por servicio se midiera contra uno vacío y no saliera nada.

Las dos veces el síntoma fue el mismo: todo "funciona", la respuesta es 200, y
lo que falta es justo lo que se pidió.

Correr con un intérprete que tenga las dependencias del paquete:
    ../constitution-core/venv/bin/python tests/test_model_query_schema.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aws_python_helper.model_query.base import _ModelQuerySchema

failures = []


def check(label, condition):
    print(f"  {'ok  ' if condition else 'FALLA'} {label}")
    if not condition:
        failures.append(label)


print("== cada parámetro documentado sobrevive al schema ==")
parsed = _ModelQuerySchema(
    collection="regions",
    database="core",
    service="dockets",
    pipeline=[{"$match": {"slug": "x"}}],
    skip=10,
)
for campo, esperado in (
    ("collection", "regions"),
    ("database", "core"),
    ("service", "dockets"),
    ("skip", 10),
):
    check(f"{campo} = {esperado!r}", getattr(parsed, campo) == esperado)

print("\n== y lo que no está declarado sí se descarta ==")
# Es el comportamiento buscado: lo que sobra se ignora. El problema nunca fue
# que ignore, sino declarar de menos.
otro = _ModelQuerySchema(collection="regions", inventado="x")
check("un parámetro inventado no explota", not hasattr(otro, "inventado"))

print()
if failures:
    print(f"{len(failures)} fallas")
    sys.exit(1)
print("all good")
