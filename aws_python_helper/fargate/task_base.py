"""
Fargate Task Base - Base class for Fargate tasks

Provides a similar interface to SQSConsumer to implement
tasks that run in Fargate containers.
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any

import json
from ..context.session import Session, set_session, get_session
from ..database.mongo_manager import MongoManager
from ..database.database_proxy import DatabaseProxy
from ..database.external_mongo_manager import ExternalMongoManager
from ..database.external_database_proxy import ExternalDatabaseProxy

class FargateTask(ABC):
    """
    Base class for Fargate tasks
    
    Similar to SQSConsumer, provides structure to execute
    business logic in Fargate containers.

    Features:
        - Access to environment variables via self.envs
        - Access to MongoDB via self.db (lazy loading)
        - Integrated logging
        - Automatic error handling
    """
    
    def __init__(self, envs: Dict[str, str] = None):
        """
        Initializes the task
        
        Args:
            envs: Environment variables passed to the task (optional)
                  If not provided, read from the system
        """
        self.envs = envs or {}
        self.logger = logging.getLogger(self.__class__.__name__)
        self._db = None
        self._external_db = None
        
    @property
    def session(self) -> Session:
        """
        Request-scoped session with state, user, and extensible properties.

        Populated automatically from the SESSION environment variable
        passed by FargateExecutor.
        """
        return get_session()

    @property
    def db(self):
        """
        Access to MongoDB databases (main cluster)
        
        Returns:
            DatabaseProxy with access to MongoDB
        """
        if self._db is None:
            self._db = DatabaseProxy(MongoManager)
        return self._db
    
    @property
    def external_db(self):
        """
        Access to external MongoDB clusters
        
        Returns None if EXTERNAL_MONGODB_CONNECTIONS environment variable is not set.
        
        Usage:
            if self.external_db:
                result = await self.external_db.ClusterDockets.smart_data.addresses.find_one({...})
                await self.external_db.ClusterDockets.core.users.insert_one({...})
        
        Returns:
            ExternalDatabaseProxy instance for accessing external clusters, or None if not configured
        """
        if self._external_db is None:
            # Initialize external connections if not already done
            if not ExternalMongoManager.is_initialized():
                has_connections = ExternalMongoManager.initialize()
                if not has_connections:
                    # No external connections available, return None
                    return None
            else:
                # Check if there are any connections available
                if len(ExternalMongoManager.get_available_clusters()) == 0:
                    return None
            
            self._external_db = ExternalDatabaseProxy()
        return self._external_db
    
    def get_env(self, key: str, default: Any = None) -> str:
        """
        Gets an environment variable
        
        Searches first in self.envs (passed explicitly),
        then in os.environ (system variables).
        
        Args:
            key: Name of the variable
            default: Default value if not exists
        
        Returns:
            Value of the variable or default
        """
        # First search in envs passed explicitly
        if key in self.envs:
            return self.envs[key]
        
        # Then search in system (uppercase and lowercase)
        value = os.getenv(key.upper())
        if value is not None:
            return value
        
        value = os.getenv(key.lower())
        if value is not None:
            return value
        
        return default
    
    def require_env(self, key: str) -> str:
        """
        Gets a required environment variable
        
        Args:
            key: Name of the variable
        
        Returns:
            Value of the variable
        
        Raises:
            ValueError: If the variable does not exist
        """
        value = self.get_env(key)
        if value is None:
            raise ValueError(f"Required environment variable '{key}' not found")
        return value
    
    @abstractmethod
    async def execute(self):
        """
        Main logic of the task
        
        This method must be implemented by each specific task.
        
        Raises:
            NotImplementedError: If not implemented
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement execute()")
    
    async def run(self):
        """
        Executes the task with error handling
        
        Calls execute() with logging and automatic error handling.
        
        Returns:
            True if executed successfully, False otherwise
        """
        try:
            # Setup session context from env var (passed by FargateExecutor)
            session_json = self.require_env("SESSION")
            session = Session.from_dict(json.loads(session_json))
            set_session(session)

            await self.execute()
            return True
            
        except Exception as e:
            self.logger.error(
                f"Task failed: {self.__class__.__name__}",
                exc_info=True
            )
            raise

