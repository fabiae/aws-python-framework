"""What the publisher must hand to boto3.

Runs on its own, no dependencies:

    python tests/test_sns_publisher.py

These exist because a single publish crashed in production with
`_format_message() missing 1 required positional argument: 'index'`. Every test
until then mocked `publish` itself, so the code that builds the boto3 call was
never executed — the mock was above the bug.

So here the fake is the **boto3 client**, not the publisher: everything the
publisher actually does runs.
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aws_python_helper.sns.publisher import MAX_BATCH_ENTRIES, SNSPublisher  # noqa: E402

failures = []


def check(label, condition, detail=""):
    print(f"  {'ok  ' if condition else 'FAIL'} {label}{'  ' + detail if detail else ''}")
    if not condition:
        failures.append(label)


class FakeSNS:
    """Se queja igual que boto3 ante un parámetro que SNS no acepta."""

    VALID_PUBLISH = {"TopicArn", "Message", "Subject", "MessageAttributes",
                     "MessageStructure", "MessageDeduplicationId", "MessageGroupId"}

    def __init__(self):
        self.published = []
        self.batches = []

    def publish(self, **kwargs):
        extra = set(kwargs) - self.VALID_PUBLISH
        if extra:
            raise TypeError(f"Unknown parameter in input: {sorted(extra)}")
        self.published.append(kwargs)
        return {"MessageId": f"m{len(self.published)}"}

    def publish_batch(self, TopicArn, PublishBatchRequestEntries):
        if len(PublishBatchRequestEntries) > MAX_BATCH_ENTRIES:
            raise Exception("TooManyEntriesInBatchRequest")
        for entry in PublishBatchRequestEntries:
            if "Id" not in entry:
                raise Exception("An entry in a batch needs an Id")
        self.batches.append(PublishBatchRequestEntries)
        return {"Successful": [{"MessageId": f"b{i}"} for i in range(len(PublishBatchRequestEntries))],
                "Failed": []}


class Publisher(SNSPublisher):
    pass


def publisher():
    p = Publisher("arn:aws:sns:us-east-2:1:Topic-dev")
    p._sns_client = FakeSNS()
    return p


async def main():
    print("a single message")
    p = publisher()
    result = await p.publish({"content": {"run_id": "abc", "status": "launched"}})
    sent = p._sns_client.published[0]
    check("it publishes", len(p._sns_client.published) == 1)
    check("no Id, which publish does not accept", "Id" not in sent)
    check("the body travels", json.loads(sent["Message"])["run_id"] == "abc")
    check("returns the message id", result == "m1")

    print("\na single message with attributes and subject")
    p = publisher()
    await p.publish({
        "content": {"x": 1},
        "attributes": {"service": "business"},
        "subject": "hello",
    })
    sent = p._sns_client.published[0]
    check("subject", sent.get("Subject") == "hello")
    check("attributes", "MessageAttributes" in sent)

    print("\na batch")
    p = publisher()
    ok, failed = await p.publish([{"content": {"n": i}} for i in range(188)])
    check("split into tens", len(p._sns_client.batches) == 19,
          f"batches={len(p._sns_client.batches)}")
    check("none over the limit", all(len(b) <= MAX_BATCH_ENTRIES for b in p._sns_client.batches))
    check("every entry has an Id", all("Id" in e for b in p._sns_client.batches for e in b))
    check("ids unique inside each call",
          all(len({e["Id"] for e in b}) == len(b) for b in p._sns_client.batches))
    check("all reported published", len(ok) == 188 and not failed)

    print("\na batch of one still goes as a batch")
    p = publisher()
    await p.publish([{"content": {"n": 1}}])
    check("one call", len(p._sns_client.batches) == 1)
    check("nothing through publish()", not p._sns_client.published)

    print("\na message with no content is refused, not sent")
    p = publisher()
    try:
        await p.publish({"attributes": {"service": "business"}})
        check("raises", False)
    except ValueError:
        check("raises", True)
    check("nothing published", not p._sns_client.published)


asyncio.run(main())

if failures:
    print(f"\n{len(failures)} failed: {failures}")
    raise SystemExit(1)
print("\nall good")
