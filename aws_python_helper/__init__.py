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


__all__ = [
    'API',
    'SQSConsumer',
    'MongoManager',
    'DatabaseProxy',
    'SNSPublisher',
    'FargateTask',
    'FargateExecutor',
    'Lambda',
    'fargate_handler',
    'api_handler',
    'sqs_handler',
    'lambda_handler',
]

