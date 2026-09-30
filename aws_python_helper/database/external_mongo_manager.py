"""
External MongoDB Manager - Manager to handle connections to multiple external MongoDB clusters
"""

from motor.motor_asyncio import AsyncIOMotorClient
from typing import Dict, Optional
import os
import json
import urllib.parse
import logging

logger = logging.getLogger(__name__)


class ExternalMongoManager:
    """
    Manager to handle connections to multiple external MongoDB clusters
    
    Each cluster has its own connection and can be accessed by name.
    Connections are lazy-loaded and cached.
    """
    
    _clients: Dict[str, AsyncIOMotorClient] = {}
    _connection_strings: Dict[str, str] = {}
    _initialized: bool = False
    
    @classmethod
    def initialize(cls):
        """
        Initialize connections to external MongoDB clusters from EXTERNAL_MONGODB_CONNECTIONS env var
        
        Returns:
            True if initialized with connections, False if no connections available
        
        The environment variable EXTERNAL_MONGODB_CONNECTIONS should be a JSON array:
        [
            {
                'name': 'AnalyticsCluster',
                'connection_string': 'mongodb+srv://...'
            }
        ]
        """
        if cls._initialized:
            return len(cls._connection_strings) > 0
        
        # Read connections from environment variable
        env_value = os.getenv('EXTERNAL_MONGODB_CONNECTIONS', '')
        
        # If no environment variable, mark as initialized but no connections
        if not env_value:
            cls._initialized = True
            return False
        
        # Parse JSON from environment variable
        try:
            external_connections = json.loads(env_value)
        except json.JSONDecodeError as e:
            logger.warning(f"Could not parse EXTERNAL_MONGODB_CONNECTIONS: {e}")
            cls._initialized = True
            return False
        
        # If empty list, mark as initialized but no connections
        if not external_connections:
            cls._initialized = True
            return False
        
        # Store connection strings for each cluster
        for conn in external_connections:
            cluster_name = conn.get('name')
            connection_string = conn.get('connection_string')
            
            if not cluster_name or not connection_string:
                logger.warning(f"Invalid external connection config: {conn}")
                continue
            
            # Build connection string with credentials if available
            # Get credentials from environment (same user/password for all clusters)
            username = os.getenv('MONGO_DB_USER')
            password = os.getenv('MONGO_DB_PASSWORD')
            
            if username and password:
                # Inject credentials into connection string
                connection_string = cls._inject_credentials(connection_string, username, password)
            
            cls._connection_strings[cluster_name] = connection_string
        
        cls._initialized = True
        return len(cls._connection_strings) > 0
    
    @staticmethod
    def _inject_credentials(connection_string: str, username: str, password: str) -> str:
        """
        Inject credentials into a MongoDB connection string
        
        If the connection string already has credentials, they are replaced.
        
        Args:
            connection_string: MongoDB connection string (with or without credentials)
            username: MongoDB username
            password: MongoDB password
        
        Returns:
            Connection string with credentials injected
        """
        # Extract protocol
        if "://" in connection_string:
            protocol, rest = connection_string.split("://", 1)
            protocol = f"{protocol}://"
        else:
            protocol = "mongodb://"
            rest = connection_string
        
        # Remove existing credentials if present (format: user:pass@host)
        if "@" in rest:
            # Split at @ to get credentials and host
            _, host_part = rest.split("@", 1)
            rest = host_part
        
        # URL-encode the password
        encoded_password = urllib.parse.quote_plus(password)
        credentials = f"{username}:{encoded_password}@"
        
        # Construct final URI
        return f"{protocol}{credentials}{rest}"
    
    @classmethod
    def get_client(cls, cluster_name: str) -> Optional[AsyncIOMotorClient]:
        """
        Get MongoDB client for a specific cluster
        
        Args:
            cluster_name: Name of the cluster
        
        Returns:
            AsyncIOMotorClient for the cluster or None if not found
        
        Raises:
            RuntimeError: If ExternalMongoManager is not initialized
        """
        if not cls._initialized:
            cls.initialize()
        
        if cluster_name not in cls._connection_strings:
            return None
        
        # Lazy load client
        if cluster_name not in cls._clients:
            connection_string = cls._connection_strings[cluster_name]
            cls._clients[cluster_name] = AsyncIOMotorClient(connection_string)
            logger.info(f"Connected to external MongoDB cluster: {cluster_name}")
        
        return cls._clients[cluster_name]
    
    @classmethod
    def get_database(cls, cluster_name: str, db_name: str):
        """
        Get reference to a database in a specific cluster
        
        Args:
            cluster_name: Name of the cluster
            db_name: Name of the database
        
        Returns:
            Reference to the database of Motor
        
        Raises:
            RuntimeError: If cluster is not configured
        """
        client = cls.get_client(cluster_name)
        if client is None:
            raise RuntimeError(
                f"External MongoDB cluster '{cluster_name}' not configured. "
                f"Available clusters: {list(cls._connection_strings.keys())}"
            )
        
        return client[db_name]
    
    @classmethod
    def is_initialized(cls) -> bool:
        """
        Check if the manager is initialized
        
        Returns:
            True if initialized, False otherwise
        """
        return cls._initialized
    
    @classmethod
    def get_available_clusters(cls) -> list:
        """
        Get list of available cluster names
        
        Returns:
            List of cluster names
        """
        if not cls._initialized:
            cls.initialize()
        return list(cls._connection_strings.keys())
    
    @classmethod
    async def close(cls):
        """
        Close all connections to external MongoDB clusters
        
        Useful for testing or cleanup.
        """
        for client in cls._clients.values():
            if client:
                client.close()
        cls._clients = {}
        cls._connection_strings = {}
        cls._initialized = False
