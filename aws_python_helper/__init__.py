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

# All handlers
from .fargate.handler import fargate_handler
from .api.handler import lambda_handler
from .sqs.handler import sqs_handler


__all__ = [
    'API',
    'SQSConsumer',
    'MongoManager',
    'DatabaseProxy',
    'SNSPublisher',
    'FargateTask',
    'FargateExecutor',
    'fargate_handler',
    'lambda_handler',
    'sqs_handler',
]

