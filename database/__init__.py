"""
Database Module - Componentes para manejar conexiones a MongoDB
"""

from .mongo_manager import MongoManager
from .database_proxy import DatabaseProxy

__all__ = ['MongoManager', 'DatabaseProxy']

