import json
import logging
import os
from typing import Any, Dict

import boto3

from .exceptions import LambdaInvocationError, LambdaResponseError

logger = logging.getLogger(__name__)


class LambdaInvoker:
    """
    Utility for invoking AWS Lambda functions from within the framework.

    Handles serialization, error detection, and response parsing so callers
    never receive None or raw boto3 objects.

    Usage:
        invoker = LambdaInvoker()

        # Synchronous — waits for the result
        result = invoker.invoke("my-function-name", payload={"key": "value"})

        # Asynchronous fire-and-forget
        invoker.invoke_async("my-function-name", payload={"key": "value"})
    """

    def __init__(self):
        self._client = None

    @property
    def _boto_client(self):
        if self._client is None:
            self._client = boto3.client(
                "lambda",
                region_name=os.getenv("AWS_REGION", "us-east-2"),
            )
        return self._client

    def invoke(self, function_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synchronous Lambda invocation (RequestResponse).

        Args:
            function_name: Name or ARN of the Lambda function.
            payload: Dict to send as the event body.

        Returns:
            Parsed response dict from the Lambda.

        Raises:
            LambdaInvocationError: If boto3 fails to reach the function.
            LambdaResponseError: If the function itself throws an unhandled exception.
        """
        try:
            response = self._boto_client.invoke(
                FunctionName=function_name,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload),
            )
        except Exception as exc:
            logger.error("Failed to invoke lambda %s: %s", function_name, exc)
            raise LambdaInvocationError(f"Failed to invoke {function_name}: {exc}") from exc

        if response.get("FunctionError"):
            raw = json.loads(response["Payload"].read())
            logger.error("Lambda %s returned FunctionError: %s", function_name, raw)
            raise LambdaResponseError(f"Lambda {function_name} returned error: {raw}")

        return json.loads(response["Payload"].read())

    def invoke_async(self, function_name: str, payload: Dict[str, Any]) -> None:
        """
        Asynchronous Lambda invocation (Event / fire-and-forget).

        Args:
            function_name: Name or ARN of the Lambda function.
            payload: Dict to send as the event body.

        Raises:
            LambdaInvocationError: If boto3 fails to dispatch the event.
        """
        try:
            self._boto_client.invoke(
                FunctionName=function_name,
                InvocationType="Event",
                Payload=json.dumps(payload),
            )
            logger.info("Async invocation dispatched to %s", function_name)
        except Exception as exc:
            logger.error("Failed to async invoke lambda %s: %s", function_name, exc)
            raise LambdaInvocationError(
                f"Failed to async invoke {function_name}: {exc}"
            ) from exc
