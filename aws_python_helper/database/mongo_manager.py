"""
MongoDB Manager - Manager to handle connections to multiple MongoDB databases
"""

from motor.motor_asyncio import AsyncIOMotorClient
from typing import Dict, Optional
import os
import logging

logger = logging.getLogger(__name__)


class MongoManager:
    """
    Manager to handle connections to multiple MongoDB databases
    
    Manages the connection to MongoDB and provides access to multiple
    databases from a single connection.
    """
    
    _client: Optional[AsyncIOMotorClient] = None
    _databases: Dict[str, any] = {}
    _connection_string: Optional[str] = None
    
    @classmethod
    def initialize(cls, connection_string: str = None):
        """
        Initialize the connection to MongoDB
        
        Only connects once. Subsequent calls do nothing.
        
        Args:
            connection_string: MongoDB connection URI.
                              If not provided, uses the MONGODB_URI environment variable
        """
        if cls._client is not None:
            logger.debug("MongoManager already initialized")
            return
        
        conn_str = connection_string or os.getenv('MONGODB_URI')
        
        if not conn_str:
            raise ValueError(
                "MongoDB connection string not provided. "
                "Pass it to initialize() or set MONGODB_URI environment variable"
            )
        
        logger.info(f"Initializing MongoDB connection")
        cls._connection_string = conn_str
        cls._client = AsyncIOMotorClient(conn_str)
        logger.info("MongoDB connection initialized successfully")
    
    @classmethod
    def get_database(cls, db_name: str):
        """
        Get reference to a database
        
        References are cached for reuse.
        
        Args:
            db_name: Name of the database
        
        Returns:
            Reference to the database of Motor
        
        Raises:
            RuntimeError: If MongoManager is not initialized
        """
        if cls._client is None:
            raise RuntimeError(
                "MongoManager not initialized. "
                "Call MongoManager.initialize() first"
            )
        
        if db_name not in cls._databases:
            logger.debug(f"Creating database reference: {db_name}")
            cls._databases[db_name] = cls._client[db_name]
        
        return cls._databases[db_name]
    
    @classmethod
    def get_client(cls) -> Optional[AsyncIOMotorClient]:
        """
        Get the MongoDB client
        
        Returns:
            Reference to the client of Motor or None if not initialized
        """
        return cls._client
    
    @classmethod
    async def close(cls):
        """
        Close the connection to MongoDB
        
        Useful for testing or cleanup.
        """
        if cls._client:
            logger.info("Closing MongoDB connection")
            cls._client.close()
            cls._client = None
            cls._databases = {}
            cls._connection_string = None
    
    @classmethod
    def is_initialized(cls) -> bool:
        """
        Check if the manager is initialized
        
        Returns:
            True if initialized, False otherwise
        """
        return cls._client is not None
    
    @classmethod
    async def ping(cls) -> bool:
        """
        Check the connection to MongoDB
        
        Returns:
            True if the connection is active, False otherwise
        """
        if not cls._client:
            return False
        
        try:
            await cls._client.admin.command('ping')
            return True
        except Exception as e:
            logger.error(f"MongoDB ping failed: {str(e)}")
            return False

