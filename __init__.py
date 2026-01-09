"""
Lambda Framework - Mini framework para Python AWS Lambda
"""

__version__ = "0.1.0"

from .api.base import API
from .api.handler import lambda_handler
from .sqs.consumer_base import SQSConsumer
from .database.mongo_manager import MongoManager
from .database.database_proxy import DatabaseProxy

__all__ = [
    'API',
    'lambda_handler',
    'SQSConsumer',
    'MongoManager',
    'DatabaseProxy'
]

