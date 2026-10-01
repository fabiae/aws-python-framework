"""Una fecha que sale de acá dice en qué zona está.

Mongo guarda UTC y el driver la devuelve sin marca de zona. Mandada así, quien
la lee la toma como hora local: en un navegador en UTC-5, algo que pasó hace un
minuto se mostraba como "dentro de 5 horas". No falla nada — dice otra cosa.

    ../constitution-core/venv/bin/python tests/test_json_encoder.py
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aws_python_helper.utils.json_encoder import MongoJSONEncoder

failures = []


def check(label, condition):
    print(f"  {'ok  ' if condition else 'FALLA'} {label}")
    if not condition:
        failures.append(label)


print("== una fecha sin zona sale como UTC ==")
naive = datetime(2026, 10, 1, 17, 25, 55)
salida = json.loads(json.dumps({"at": naive}, cls=MongoJSONEncoder))["at"]
print(f"    {salida}")
check("lleva la marca de zona", salida.endswith("+00:00") or salida.endswith("Z"))
check("no corre la hora", salida.startswith("2026-10-01T17:25:55"))

print("\n== una que ya la trae se respeta ==")
aware = datetime(2026, 10, 1, 17, 25, 55, tzinfo=timezone(timedelta(hours=-5)))
salida = json.loads(json.dumps({"at": aware}, cls=MongoJSONEncoder))["at"]
print(f"    {salida}")
check("conserva su propia zona", salida.endswith("-05:00"))

print("\n== y una fecha sin hora no se toca ==")
from datetime import date as _date
salida = json.loads(json.dumps({"on": _date(2026, 10, 1)}, cls=MongoJSONEncoder))["on"]
print(f"    {salida}")
check("sigue siendo una fecha", salida == "2026-10-01")

print()
if failures:
    print(f"{len(failures)} fallas")
    sys.exit(1)
print("all good")
