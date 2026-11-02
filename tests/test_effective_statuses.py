"""Las tres formas de declarar el vocabulario de `status`."""

from aws_python_helper.repository.audit import DEFAULT_STATUSES
from aws_python_helper.repository.base import Repository


class SinDeclarar(Repository):
    """Se queda con los dos de siempre."""

    @property
    def collection_name(self):
        return "sin"


class CicloPropio(Repository):
    """Reemplaza: `active` no significaría nada para una búsqueda."""

    @property
    def collection_name(self):
        return "busquedas"

    @property
    def statuses(self):
        return ["queued", "in_progress", "complete", "failed"]


class CicloExtra(Repository):
    """Suma: una venta nace `new` y además puede darse de baja."""

    @property
    def collection_name(self):
        return "ventas"

    @property
    def extra_statuses(self):
        return ["new"]


class SinCiclo(Repository):
    """Una colección donde un ciclo de vida no significa nada."""

    @property
    def collection_name(self):
        return "tokens"

    @property
    def statuses(self):
        return None


class ExtraRepetido(Repository):
    """Agrega uno que ya estaba: no se duplica."""

    @property
    def collection_name(self):
        return "repetido"

    @property
    def extra_statuses(self):
        return ["new", "active"]


def test_sin_declarar_quedan_los_default():
    assert SinDeclarar().effective_statuses == list(DEFAULT_STATUSES)
    assert SinDeclarar().default_status == "active"


def test_statuses_reemplaza_a_los_default():
    assert CicloPropio().effective_statuses == [
        "queued", "in_progress", "complete", "failed",
    ]
    assert "active" not in CicloPropio().effective_statuses


def test_extra_se_suma_a_los_default():
    assert CicloExtra().effective_statuses == ["new", "active", "inactive"]


def test_el_primero_es_con_el_que_nace():
    assert CicloPropio().default_status == "queued"
    assert CicloExtra().default_status == "new"


def test_sin_ciclo_no_valida_nada():
    assert SinCiclo().effective_statuses is None
    assert SinCiclo().default_status is None


def test_un_extra_que_ya_era_default_no_se_repite():
    assert ExtraRepetido().effective_statuses == ["new", "active", "inactive"]
