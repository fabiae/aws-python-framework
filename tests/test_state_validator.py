"""El caché del validador de estado, con la base falseada.

Se falsea `MongoManager`, no el validador: lo que se quiere comprobar es cuántas
veces pregunta y cuándo vuelve a preguntar.

Correr con un intérprete que tenga las dependencias del paquete:
    ../constitution-core/venv/bin/python tests/test_state_validator.py
"""

import asyncio
import sys

from aws_python_helper.context.state_validator import InvalidStateError, StateValidator
import aws_python_helper.database.mongo_manager as mongo_manager

consultas = {"n": 0}


class FakeStates:
    async def find_one(self, query):
        consultas["n"] += 1
        return {"name": query["name"]} if query["name"] == "connecticut" else None


class FakeDB:
    states = FakeStates()


mongo_manager.MongoManager.get_database = staticmethod(lambda name: FakeDB())

fallos = []


def igual(que, a, b):
    ok = a == b
    print(("  ok    " if ok else "  FALLA ") + que + ("" if ok else f"  -> {a!r} != {b!r}"))
    if not ok:
        fallos.append(que)


async def main():
    print("StateValidator")

    StateValidator.clear_cache()
    consultas["n"] = 0
    for _ in range(5):
        await StateValidator.validate("connecticut")
    igual("un estado activo se pregunta una sola vez", consultas["n"], 1)

    # Lo que antes pegaba en la base en cada request: el rechazo no se cacheaba,
    # y es el caso más común —el panel parado en un estado donde el servicio no
    # está activo—, así que cada tarjeta de la pantalla lo pagaba.
    StateValidator.clear_cache()
    consultas["n"] = 0
    rechazos = 0
    for _ in range(5):
        try:
            await StateValidator.validate("new_jersey")
        except InvalidStateError:
            rechazos += 1
    igual("un estado inactivo tambien se pregunta una sola vez", consultas["n"], 1)
    igual("y sigue devolviendo el error en todos", rechazos, 5)

    # Que se cachee no puede volverlo permanente: un estado recién activado
    # tiene que empezar a andar, y el techo de esa espera es el TTL del rechazo.
    previo = StateValidator._REJECT_TTL
    try:
        StateValidator._REJECT_TTL = 0
        consultas["n"] = 0
        try:
            await StateValidator.validate("new_jersey")
        except InvalidStateError:
            pass
        igual("vencido el TTL del rechazo, vuelve a preguntar", consultas["n"], 1)
    finally:
        StateValidator._REJECT_TTL = previo

    # Un estado que pasa a activo deja de estar rechazado, sin esperar al TTL.
    StateValidator.clear_cache()
    consultas["n"] = 0
    try:
        await StateValidator.validate("new_jersey")
    except InvalidStateError:
        pass
    await StateValidator.validate("connecticut")
    igual("el rechazo de uno no tapa al otro", consultas["n"], 2)

    StateValidator.clear_cache()
    igual("clear_cache limpia los dos",
          (StateValidator._cache, StateValidator._rejected), ({}, {}))


asyncio.run(main())
print()
print(f"{len(fallos)} FALLARON: {fallos}" if fallos else "todo en orden")
sys.exit(1 if fallos else 0)
