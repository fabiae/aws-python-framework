class LambdaInvocationError(Exception):
    """Raised when boto3 fails to invoke the Lambda function."""


class LambdaResponseError(Exception):
    """Raised when the Lambda function itself returns a FunctionError."""


class ServiceNotConfiguredError(Exception):
    """Raised when a microservice name is not found in MICROSERVICE_URLS."""


class ApiClientError(Exception):
    """Raised when the HTTP request cannot be completed (network, timeout, etc.)."""


class ApiResponseError(Exception):
    """Raised when the remote API returns an HTTP 4xx/5xx response."""

    def __init__(self, message: str, status_code: int = None, response_body: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
