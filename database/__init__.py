"""
Database Module - Components to handle connections to MongoDB
"""

from .mongo_manager import MongoManager
from .database_proxy import DatabaseProxy

__all__ = ['MongoManager', 'DatabaseProxy']

