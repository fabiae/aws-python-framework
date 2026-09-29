"""What the audit stamp must never do to a write.

Runs on its own, no dependencies:

    python tests/test_audit_stamp.py

These are here because the stamp broke a write in production once: an upsert
that set `status` itself collided with the `$setOnInsert` the stamp added, and
Mongo refused the whole update with "would create a conflict at 'status'". It
failed at runtime, on one endpoint, in a log nobody was reading.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aws_python_helper.repository.audit import stamp_new, stamp_update  # noqa: E402

STATUSES = ["active", "inactive"]

failures = []


def check(label, condition, detail=""):
    mark = "ok  " if condition else "FAIL"
    print(f"  {mark} {label}{'  ' + detail if detail else ''}")
    if not condition:
        failures.append(label)


def conflicts(update):
    """Los campos que dos operadores de un mismo update escriben a la vez.

    Es lo que Mongo rechaza, y rechaza el update entero: no escribe nada.
    """
    sections = [
        (name, section) for name, section in update.items()
        if name.startswith("$") and isinstance(section, dict)
    ]
    clash = set()
    for index, (_, first) in enumerate(sections):
        for _, second in sections[index + 1:]:
            clash |= set(first) & set(second)
    return clash


print("no two operators may write the same path")
for label, update in [
    ("upsert that sets status itself", {"$set": {"name": "ct", "status": "active"}}),
    ("upsert that sets created_at itself", {"$set": {"created_at": "fixed"}}),
    ("upsert that sets created_by itself", {"$set": {"created_by": {"name": "x"}}}),
    ("plain upsert", {"$set": {"name": "ct"}}),
    ("upsert with $inc alongside", {"$set": {"name": "ct"}, "$inc": {"hits": 1}}),
]:
    result = stamp_update(dict(update), upsert=True, statuses=STATUSES, default_status="active")
    found = conflicts(result)
    check(label, not found, f"conflicts={sorted(found)}" if found else "")

print("\nthe stamp is still complete when nothing conflicts")
result = stamp_update({"$set": {"name": "ct"}}, upsert=True, statuses=STATUSES, default_status="active")
check("status on insert", result["$setOnInsert"].get("status") == "active")
check("created_at on insert", "created_at" in result["$setOnInsert"])
check("created_by on insert", "created_by" in result["$setOnInsert"])
check("updated_at always", "updated_at" in result["$set"])

print("\nthe caller's own value wins")
result = stamp_update({"$set": {"status": "inactive"}}, upsert=True, statuses=STATUSES, default_status="active")
check("status stays what the caller set", result["$set"]["status"] == "inactive")
check("no default forced on top", "status" not in result.get("$setOnInsert", {}))

print("\nwithout upsert there is no insert stamp")
result = stamp_update({"$set": {"status": "inactive"}}, upsert=False, statuses=STATUSES)
check("no $setOnInsert", "$setOnInsert" not in result)

print("\nwithout a vocabulary no status is invented")
result = stamp_update({"$set": {"name": "ct"}}, upsert=True, statuses=None)
check("no status", "status" not in result.get("$setOnInsert", {}))

print("\na pipeline update takes stages, not operators")
result = stamp_update([{"$set": {"name": "ct"}}], upsert=True, statuses=STATUSES)
check("still a list", isinstance(result, list))
check("stamp appended last", result[-1]["$set"].get("updated_at") is not None)

print("\nthe lifecycle field can be called something else")
result = stamp_new(
    {"name": "x", "status": "FORFEITED"},
    ["active", "inactive"],
    "active",
    status_field="lifecycle_status",
)
check("the collection's own status is untouched", result["status"] == "FORFEITED")
check("the framework writes its own field", result["lifecycle_status"] == "active")

result = stamp_update(
    {"$set": {"name": "x"}},
    upsert=True,
    statuses=["active"],
    default_status="active",
    status_field="lifecycle_status",
)
check("and on an upsert it stamps that one", result["$setOnInsert"]["lifecycle_status"] == "active")
check("with no path conflict", not conflicts(result))

try:
    stamp_new({"lifecycle_status": "made up"}, ["active"], status_field="lifecycle_status")
    check("a value outside the vocabulary is refused", False)
except ValueError as error:
    check("a value outside the vocabulary is refused", "lifecycle_status" in str(error),
          "and the message names the field")

if failures:
    print(f"\n{len(failures)} failed: {failures}")
    raise SystemExit(1)
print("\nall good")
