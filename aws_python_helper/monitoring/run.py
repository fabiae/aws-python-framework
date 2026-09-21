"""Reporting that a process started and finished, in one line.

Two hand-written publishes would work, and the second one would get forgotten on
the path that matters: the failure. So the boundary is a context manager — enter
and it says it started, leave and it says how it went, exception included.

Nothing here can raise into the caller. Monitoring must never be able to break
the thing it monitors: a topic that does not exist, credentials that are wrong,
SNS being slow are all reasons to lose a record, never reasons to fail a run that
otherwise worked.
"""

import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..sns.publisher import SNSPublisher

logger = logging.getLogger(__name__)

LAUNCHED = "launched"
RUNNING = "running"
SUCCESS = "success"
FAILED = "failed"

TOPIC_ENV = "PROCESS_RUNS_TOPIC_ARN"


class ProcessRunPublisher(SNSPublisher):
    pass


class RunReporter:
    """Lo que el proceso usa adentro del bloque para contar cómo le fue."""

    __slots__ = ("run_id", "process_code", "counters", "scope", "_error")

    def __init__(self, run_id: str, process_code: str):
        self.run_id = run_id
        self.process_code = process_code
        self.counters: Dict[str, Any] = {}
        self.scope: Optional[str] = None
        self._error: Optional[str] = None

    def count(self, name: str, amount: int = 1) -> None:
        """Suma a un contador. Lo que se mida con esto se define en el proceso."""
        self.counters[name] = self.counters.get(name, 0) + amount


async def _publish(payload: Dict[str, Any]) -> None:
    """Manda el evento, y si no se puede lo deja en el log y sigue.

    Se espera a que salga en lugar de dispararlo y seguir: una lambda se congela
    apenas devuelve, y una tarea suelta que todavía no corrió se pierde entera.
    Son milisegundos contra perder el registro.
    """
    topic = os.getenv(TOPIC_ENV, "")
    if not topic:
        logger.warning(
            "%s is not set, so run %s of %s was not reported",
            TOPIC_ENV, payload.get("run_id"), payload.get("process_code"),
        )
        return

    try:
        await ProcessRunPublisher(topic).publish({"content": _clean(payload)})
    except Exception as error:
        # A propósito no se vuelve a lanzar: perder el registro de una ejecución
        # es malo, tumbar la ejecución por no poder registrarla es peor.
        logger.error("Could not report run %s: %s", payload.get("run_id"), error)


def _clean(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@asynccontextmanager
async def process_run(
    process_code: str,
    *,
    run_id: Optional[str] = None,
    scope: Optional[str] = None,
    resource_arn: Optional[str] = None,
    request_id: Optional[str] = None,
):
    """Reporta el principio y el final de una ejecución.

    Usage:
        async with process_run("business-region-sync-ct") as run:
            run.count("regions_received")

    El proceso tiene que estar registrado en core; si no lo está, el evento se
    descarta allá y queda en su log. Eso es a propósito: lo que nadie declaró no
    se está vigilando, y registrarlo solo llenaría la pantalla de ejecuciones que
    nadie puede configurar.
    """
    reporter = RunReporter(run_id or str(uuid.uuid4()), process_code)
    started_at = _now()

    await _publish({
        "run_id": reporter.run_id,
        "process_code": process_code,
        "status": LAUNCHED,
        "started_at": started_at,
        "scope": scope,
        # Lo único que AWS deja en el ambiente. El ARN completo y el id de la
        # invocación viven en el `context` del handler, que acá no se tiene: quien
        # lo tenga los pasa por `resource_arn` y `request_id`.
        "resource_arn": resource_arn or os.getenv("AWS_LAMBDA_FUNCTION_NAME") or None,
        "request_id": request_id,
    })

    try:
        yield reporter
    except Exception as error:
        await _publish({
            "run_id": reporter.run_id,
            "process_code": process_code,
            "status": FAILED,
            "started_at": started_at,
            "finished_at": _now(),
            "error": f"{type(error).__name__}: {error}"[:2000],
            "counters": reporter.counters,
            "scope": reporter.scope or scope,
            "request_id": request_id,
        })
        # La excepción sigue su camino: el monitoreo anota lo que pasó, no lo
        # decide. Tragarla acá convertiría una falla en un éxito silencioso.
        raise
    else:
        await _publish({
            "run_id": reporter.run_id,
            "process_code": process_code,
            "status": SUCCESS,
            "started_at": started_at,
            "finished_at": _now(),
            "counters": reporter.counters,
            "scope": reporter.scope or scope,
            "request_id": request_id,
        })
