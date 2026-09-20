"""
Automatic audit stamping for every write.

Records answer "who last touched this, and when" without any repository having to
remember to fill it in. The four fields —created_at, created_by, updated_at,
updated_by— are injected by wrapping the Motor collection, so call sites keep
using `self.collection.insert_one(...)` exactly as before.

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


def _system_actor() -> Dict[str, str]:
    """The process doing the writing, when no person is behind it."""
    service = os.getenv('SERVICE_CODE') or os.getenv('NAMESPACE') or 'constitution'
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


def stamp_new(document: Dict[str, Any]) -> Dict[str, Any]:
    """The four fields on a document being created.

    Whatever the caller set explicitly wins: this fills gaps, it does not
    overrule a repository that knows better.
    """
    if not isinstance(document, dict):
        return document

    now, who = _now(), current_actor()
    document.setdefault(CREATED_AT, now)
    document.setdefault(UPDATED_AT, now)
    document.setdefault(CREATED_BY, who)
    document.setdefault(UPDATED_BY, who)
    return document


def _merge_into_set(update: Dict[str, Any], values: Dict[str, Any], operator: str) -> None:
    section = update.get(operator)
    if not isinstance(section, dict):
        section = {}
        update[operator] = section
    for key, value in values.items():
        section.setdefault(key, value)


def stamp_update(
    update: Union[Dict[str, Any], List[Dict[str, Any]]],
    upsert: bool = False,
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
        return stamp_new(dict(update))

    update = dict(update)
    _merge_into_set(update, touched, '$set')
    if upsert:
        # Si termina insertando, el registro nace ahora: created_* sólo en ese caso.
        _merge_into_set(update, {CREATED_AT: now, CREATED_BY: who}, '$setOnInsert')
    return update


class AuditedCollection:
    """A Motor collection that stamps who wrote and when.

    Only the write methods are intercepted; everything else —find, aggregate,
    count_documents, create_index— passes straight through untouched.

    `bulk_write` is deliberately left alone: its operations carry their own
    filters and updates, and silently rewriting them would be harder to predict
    than asking for the stamp explicitly.
    """

    __slots__ = ('_collection',)

    def __init__(self, collection: Any):
        object.__setattr__(self, '_collection', collection)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._collection, name)

    def __repr__(self) -> str:
        return f'AuditedCollection({self._collection!r})'

    async def insert_one(self, document: Dict[str, Any], *args: Any, **kwargs: Any):
        return await self._collection.insert_one(stamp_new(document), *args, **kwargs)

    async def insert_many(self, documents: Any, *args: Any, **kwargs: Any):
        return await self._collection.insert_many(
            [stamp_new(document) for document in documents], *args, **kwargs
        )

    async def update_one(self, filter: Any, update: Any, *args: Any, **kwargs: Any):
        return await self._collection.update_one(
            filter, stamp_update(update, kwargs.get('upsert', False)), *args, **kwargs
        )

    async def update_many(self, filter: Any, update: Any, *args: Any, **kwargs: Any):
        return await self._collection.update_many(
            filter, stamp_update(update, kwargs.get('upsert', False)), *args, **kwargs
        )

    async def find_one_and_update(self, filter: Any, update: Any, *args: Any, **kwargs: Any):
        return await self._collection.find_one_and_update(
            filter, stamp_update(update, kwargs.get('upsert', False)), *args, **kwargs
        )

    async def replace_one(self, filter: Any, replacement: Any, *args: Any, **kwargs: Any):
        return await self._collection.replace_one(
            filter, stamp_new(dict(replacement)), *args, **kwargs
        )

    async def find_one_and_replace(self, filter: Any, replacement: Any, *args: Any, **kwargs: Any):
        return await self._collection.find_one_and_replace(
            filter, stamp_new(dict(replacement)), *args, **kwargs
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
