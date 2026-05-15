"""
AWS Python Framework
"""

__version__ = "0.1.0"

# All classes
from .api.base import API
from .sqs.consumer_base import SQSConsumer
from .database.mongo_manager import MongoManager
from .database.database_proxy import DatabaseProxy
from .sns.publisher import SNSPublisher
from .fargate.task_base import FargateTask
from .fargate.executor import FargateExecutor
from .lambda_standalone.base import Lambda

# All handlers
from .fargate.handler import fargate_handler
from .api.handler import api_handler
from .sqs.handler import sqs_handler
from .lambda_standalone.handler import lambda_handler

# Utils
from .utils.json_encoder import MongoJSONEncoder, mongo_json_dumps
from .utils.serializer import serialize_mongo_types

# Repository
from .repository.base import Repository

# Context
from .context.session import Session, get_session, set_session
from .context.state_validator import StateValidator, InvalidStateError

# Invoker
from .invoker import (
    LambdaInvoker,
    ApiClient,
    LambdaInvocationError,
    LambdaResponseError,
    ServiceNotConfiguredError,
    ApiClientError,
    ApiResponseError,
)


__all__ = [
    'API',
    'SQSConsumer',
    'MongoManager',
    'DatabaseProxy',
    'SNSPublisher',
    'FargateTask',
    'FargateExecutor',
    'Lambda',
    'Repository',
    'fargate_handler',
    'api_handler',
    'sqs_handler',
    'lambda_handler',
    'MongoJSONEncoder',
    'mongo_json_dumps',
    'serialize_mongo_types',
    'Session',
    'get_session',
    'set_session',
    'StateValidator',
    'InvalidStateError',
    'LambdaInvoker',
    'ApiClient',
    'LambdaInvocationError',
    'LambdaResponseError',
    'ServiceNotConfiguredError',
    'ApiClientError',
    'ApiResponseError',
]

