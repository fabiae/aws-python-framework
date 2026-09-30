"""
Framework-managed fields on every write: who, when, and what state.

Records answer "who last touched this, and when" without any repository having to
remember to fill it in. The four audit fields —created_at, created_by,
updated_at, updated_by— plus `status` are injected by wrapping the Motor
collection, so call sites keep using `self.collection.insert_one(...)` exactly as
before.

`status` is the lifecycle of a record, uniform across every entity so a listing
can show it without knowing what it is looking at. Two values by default, active
and inactive; a repository declaring `statuses` gets its own set. A value outside
that set is refused rather than stored: a status nobody expected reaches a panel
as an unknown label and a query as a silent mismatch.

Not every write comes from a person. A scraper, a queue consumer or a scheduled
task writes too, and the stamp says so: "nobody knows" and "the system did it"
are different answers.

Author is stored denormalised —id plus the name as it read at the time— so
reading a record never needs a second query, and renaming someone later does not
rewrite history.
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from ..context.session import get_session

USER = 'user'
SYSTEM = 'system'

CREATED_AT = 'created_at'
CREATED_BY = 'created_by'
UPDATED_AT = 'updated_at'
UPDATED_BY = 'updated_by'
STATUS = 'status'

ACTIVE = 'active'
INACTIVE = 'inactive'
DEFAULT_STATUSES = [ACTIVE, INACTIVE]


def _system_actor() -> Dict[str, str]:
    """The process doing the writing, when no person is behind it."""
    service = os.getenv('SERVICE_CODE') or os.getenv('NAMESPACE') or 'system'
    # Cada entrypoint deja su rastro: la lambda su nombre, el task el suyo.
    process = (
        os.getenv('PROCESS_NAME')
        or os.getenv('AWS_LAMBDA_FUNCTION_NAME')
        or os.getenv('TASK_NAME')
        or service
    )
    return {'type': SYSTEM, 'id': service, 'name': process}


def current_actor() -> Dict[str, str]:
    """Who is writing right now, according to the request-scoped session."""
    try:
        session = get_session()
    except Exception:
        return _system_actor()

    user = getattr(session, 'user', None) if session else None
    if not isinstance(user, dict):
        return _system_actor()

    user_id = user.get('_id') or user.get('id') or user.get('user_id')
    if not user_id:
        return _system_actor()

    name = user.get('name') or user.get('email') or str(user_id)
    return {'type': USER, 'id': str(user_id), 'name': name}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class InvalidStatusError(ValueError):
    """A status the repository does not declare."""


def _check_status(
    value: Any, statuses: Optional[List[str]], field: str = STATUS
) -> None:
    if statuses and value is not None and value not in statuses:
        raise InvalidStatusError(
            f"'{value}' is not a valid value for '{field}'. "
            f"Declared: {', '.join(statuses)}"
        )


def stamp_new(
    document: Dict[str, Any],
    statuses: Optional[List[str]] = None,
    default_status: Optional[str] = None,
    status_field: str = STATUS,
) -> Dict[str, Any]:
    """The framework fields on a document being created.

    Whatever the caller set explicitly wins: this fills gaps, it does not
    overrule a repository that knows better. What it does not let pass is a
    status outside the declared set.
    """
    if not isinstance(document, dict):
        return document

    now, who = _now(), current_actor()
    document.setdefault(CREATED_AT, now)
    document.setdefault(UPDATED_AT, now)
    document.setdefault(CREATED_BY, who)
    document.setdefault(UPDATED_BY, who)

    if statuses:
        document.setdefault(status_field, default_status or statuses[0])
        _check_status(document.get(status_field), statuses, status_field)
    return document


def _merge_into_set(update: Dict[str, Any], values: Dict[str, Any], operator: str) -> None:
    section = update.get(operator)
    if not isinstance(section, dict):
        section = {}
        update[operator] = section
    for key, value in values.items():
        section.setdefault(key, value)


def _written_elsewhere(update: Dict[str, Any], key: str, operator: str) -> bool:
    """Si otro operador de esta misma actualización ya escribe ese campo.

    Mongo rechaza el update entero si dos operadores tocan la misma ruta —
    `$set: {status}` junto a `$setOnInsert: {status}` da "would create a
    conflict at 'status'" — y el sello no tiene por qué ser el que lo provoque.
    Si el llamador ya escribe el campo, el insert va a quedar con su valor, así
    que el sello ahí sobra.
    """
    for other, section in update.items():
        if other == operator or not other.startswith('$') or not isinstance(section, dict):
            continue
        if key in section:
            return True
    return False


def stamp_update(
    update: Union[Dict[str, Any], List[Dict[str, Any]]],
    upsert: bool = False,
    statuses: Optional[List[str]] = None,
    default_status: Optional[str] = None,
    status_field: str = STATUS,
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """The two 'updated' fields on a modification, and the 'created' ones on an upsert.

    An update can also be an aggregation pipeline, and a pipeline takes stages,
    not operators: there the stamp goes as one more `$set` stage at the end.
    """
    now, who = _now(), current_actor()
    touched = {UPDATED_AT: now, UPDATED_BY: who}

    if isinstance(update, list):
        # En un pipeline `$set` es una etapa y pisa lo anterior a propósito: va al
        # final para que el sello no lo tape una etapa posterior.
        return update + [{'$set': {UPDATED_AT: now, UPDATED_BY: who}}]

    if not isinstance(update, dict):
        return update

    # Un reemplazo entero —sin operadores— es un documento, no una modificación.
    if update and not any(key.startswith('$') for key in update):
        return stamp_new(dict(update), statuses, default_status, status_field)

    update = dict(update)
    if statuses:
        for operator in ('$set', '$setOnInsert'):
            section = update.get(operator)
            if isinstance(section, dict) and status_field in section:
                _check_status(section[status_field], statuses, status_field)

    _merge_into_set(update, touched, '$set')
    if upsert:
        # Si termina insertando, el registro nace ahora: created_* y el estado
        # inicial sólo en ese caso.
        born = {CREATED_AT: now, CREATED_BY: who}
        if statuses:
            born[status_field] = default_status or statuses[0]
        born = {
            key: value
            for key, value in born.items()
            if not _written_elsewhere(update, key, '$setOnInsert')
        }
        _merge_into_set(update, born, '$setOnInsert')
    return update


class AuditedCollection:
    """A Motor collection that fills in who wrote, when, and the record's status.

    Only the write methods are intercepted; everything else —find, aggregate,
    count_documents, create_index— passes straight through untouched.

    `bulk_write` is deliberately left alone: its operations carry their own
    filters and updates, and silently rewriting them would be harder to predict
    than asking for the stamp explicitly.
    """

    __slots__ = ('_collection', '_statuses', '_default_status', '_status_field')

    def __init__(
        self,
        collection: Any,
        statuses: Optional[List[str]] = None,
        default_status: Optional[str] = None,
        status_field: str = STATUS,
    ):
        object.__setattr__(self, '_collection', collection)
        object.__setattr__(self, '_statuses', statuses)
        object.__setattr__(self, '_default_status', default_status)
        object.__setattr__(self, '_status_field', status_field)

    def _new(self, document: Dict[str, Any]) -> Dict[str, Any]:
        return stamp_new(document, self._statuses, self._default_status, self._status_field)

    def _update(self, update: Any, upsert: bool) -> Any:
        return stamp_update(
            update, upsert, self._statuses, self._default_status, self._status_field
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._collection, name)

    def __repr__(self) -> str:
        return f'AuditedCollection({self._collection!r})'

    async def insert_one(self, document: Dict[str, Any], *args: Any, **kwargs: Any):
        return await self._collection.insert_one(self._new(document), *args, **kwargs)

    async def insert_many(self, documents: Any, *args: Any, **kwargs: Any):
        return await self._collection.insert_many(
            [self._new(document) for document in documents], *args, **kwargs
        )

    async def update_one(self, filter: Any, update: Any, *args: Any, **kwargs: Any):
        return await self._collection.update_one(
            filter, self._update(update, kwargs.get('upsert', False)), *args, **kwargs
        )

    async def update_many(self, filter: Any, update: Any, *args: Any, **kwargs: Any):
        return await self._collection.update_many(
            filter, self._update(update, kwargs.get('upsert', False)), *args, **kwargs
        )

    async def find_one_and_update(self, filter: Any, update: Any, *args: Any, **kwargs: Any):
        return await self._collection.find_one_and_update(
            filter, self._update(update, kwargs.get('upsert', False)), *args, **kwargs
        )

    async def replace_one(self, filter: Any, replacement: Any, *args: Any, **kwargs: Any):
        return await self._collection.replace_one(
            filter, self._new(dict(replacement)), *args, **kwargs
        )

    async def find_one_and_replace(self, filter: Any, replacement: Any, *args: Any, **kwargs: Any):
        return await self._collection.find_one_and_replace(
            filter, self._new(dict(replacement)), *args, **kwargs
        )


def public_audit(document: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Leaves the audit fields ready to show: name and type, dates in ISO.

    The author travels as name plus type because a panel has to tell a person
    from a process, not just print a string.
    """
    if not isinstance(document, dict):
        return document

    document = dict(document)
    for field in (CREATED_BY, UPDATED_BY):
        value = document.get(field)
        if isinstance(value, dict):
            document[field] = {'name': value.get('name'), 'type': value.get('type', USER)}
    for field in (CREATED_AT, UPDATED_AT):
        value = document.get(field)
        if isinstance(value, datetime):
            # Sin tzinfo Mongo devuelve naive, y el navegador lo leería como hora local.
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            document[field] = value.isoformat()
    return document
