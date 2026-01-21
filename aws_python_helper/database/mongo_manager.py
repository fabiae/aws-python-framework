"""
MongoDB Manager - Manager to handle connections to multiple MongoDB databases
"""

from motor.motor_asyncio import AsyncIOMotorClient
from typing import Dict, Optional
import os
import logging
import urllib.parse

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
    
    @staticmethod
    def build_connection_string(
        host: str,
        username: str = None,
        password: str = None,
        database: str = None,
        options: str = None
    ) -> str:
        """
        Build MongoDB connection string from components
        
        Args:
            host: MongoDB host (e.g., "mongodb+srv://cluster.mongodb.net" or "localhost:27017")
            username: MongoDB username (optional)
            password: MongoDB password (optional, will be URL-encoded)
            database: Default database name (optional)
            options: Additional connection options (optional, e.g., "retryWrites=true&w=majority")
        
        Returns:
            Complete MongoDB connection string
        
        Examples:
            # Without credentials
            build_connection_string("mongodb+srv://cluster.mongodb.net")
            # -> "mongodb+srv://cluster.mongodb.net"
            
            # With credentials
            build_connection_string(
                "mongodb+srv://cluster.mongodb.net",
                username="admin",
                password="my@pass:word"
            )
            # -> "mongodb+srv://admin:my%40pass%3Aword@cluster.mongodb.net"
        """
        # Extract protocol and clean host
        if "://" in host:
            protocol, host_part = host.split("://", 1)
            protocol = f"{protocol}://"
        else:
            protocol = "mongodb://"
            host_part = host
        
        # Build credentials part
        credentials = ""
        if username and password:
            # URL-encode the password to handle special characters
            encoded_password = urllib.parse.quote_plus(password)
            credentials = f"{username}:{encoded_password}@"
        elif username:
            credentials = f"{username}@"
        
        # Build database part
        db_part = f"/{database}" if database else ""
        
        # Build options part
        options_part = f"?{options}" if options else ""
        
        # Construct final URI
        connection_string = f"{protocol}{credentials}{host_part}{db_part}{options_part}"
        
        return connection_string
    
    @classmethod
    def initialize(cls, connection_string: str = None, **kwargs):
        """
        Initialize the connection to MongoDB
        
        Only connects once. Subsequent calls do nothing.
        
        Args:
            connection_string: MongoDB connection URI.
                              If not provided, tries to build from environment variables.
            **kwargs: Optional keyword arguments to build connection string:
                     - host: MongoDB host
                     - username: MongoDB username
                     - password: MongoDB password
                     - database: Default database
                     - options: Connection options
        
        Environment variables used (in order of precedence):
            1. MONGODB_URI or MONGO_DB_URI: Complete connection string
            2. MONGO_DB_HOST + MONGO_DB_USER + MONGO_DB_PASSWORD: Build from components
        """
        if cls._client is not None:
            logger.debug("MongoManager already initialized")
            return
        
        # Try to get connection string
        conn_str = connection_string or os.getenv('MONGO_DB_URI')
        
        # If no complete URI, try to build from components
        if not conn_str:
            host = kwargs.get('host') or os.getenv('MONGO_DB_HOST')
            username = kwargs.get('username') or os.getenv('MONGO_DB_USER')
            password = kwargs.get('password') or os.getenv('MONGO_DB_PASSWORD')
            database = kwargs.get('database') or os.getenv('MONGO_DB_NAME')
            options = kwargs.get('options') or os.getenv('MONGO_DB_OPTIONS')
            
            if host:
                logger.info("Building MongoDB connection string from components")
                conn_str = cls.build_connection_string(
                    host=host,
                    username=username,
                    password=password,
                    database=database,
                    options=options
                )
            else:
                raise ValueError(
                    "MongoDB connection not configured. Provide either:\n"
                    "1. connection_string parameter, or\n"
                    "2. MONGODB_URI or MONGO_DB_URI environment variable, or\n"
                    "3. MONGO_DB_HOST (+ MONGO_DB_USER, MONGO_DB_PASSWORD) environment variables"
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

