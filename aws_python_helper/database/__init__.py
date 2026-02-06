"""
Database Module - Components to handle connections to MongoDB
"""

from .mongo_manager import MongoManager
from .database_proxy import DatabaseProxy
from .external_mongo_manager import ExternalMongoManager
from .external_database_proxy import ExternalDatabaseProxy

__all__ = ['MongoManager', 'DatabaseProxy', 'ExternalMongoManager', 'ExternalDatabaseProxy']

