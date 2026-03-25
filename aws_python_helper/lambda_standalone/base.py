"""
Lambda Base Class - Base class for all standalone Lambda functions
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

from ..context.session import Session, set_session, get_session
from ..database.mongo_manager import MongoManager
from ..database.database_proxy import DatabaseProxy
from ..database.external_mongo_manager import ExternalMongoManager
from ..database.external_database_proxy import ExternalDatabaseProxy

class Lambda(ABC):
    """
    Base class for all standalone Lambda functions
    
    These are lambdas that are invoked directly via AWS SDK,
    not through API Gateway or other event sources.
    They can be invoked from other lambdas, Step Functions,
    or any service using the AWS SDK.
    """
    
    def __init__(self, event: Dict[str, Any], context: Any):
        """
        Initialize the Lambda with event and context
        
        Args:
            event: Lambda event with data
            context: Lambda context with request_id, etc.
        """
        self.event = event
        self.context = context
        self.logger = logging.getLogger(self.__class__.__name__)
        self._db = None
        self._external_db = None
    
    @property
    def session(self) -> Session:
        """
        Request-scoped session with state, user, and extensible properties.

        Populated automatically from the event's 'session' field.
        """
        return get_session()

    @property
    def data(self) -> Dict[str, Any]:
        """
        Access to event data
        
        Supports both formats:
        - {'data': {...}} -> returns the nested data
        - {...} -> returns the entire event
        
        Returns:
            Data from the event
        """
        if 'data' in self.event:
            return self.event['data']
        return self.event
    
    @property
    def db(self):
        """
        Access to MongoDB databases (main cluster)
        
        Lazy loads the database connection on first access.
        
        Usage:
            result = await self.db.users_db.users.find_one({'_id': user_id})
            await self.db.analytics_db.logs.insert_one({'action': 'view'})
        
        Returns:
            DatabaseProxy instance for accessing MongoDB
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
    
    async def validate(self):
        """
        Hook for data validation
        
        Override this method to implement custom validations.
        If the validation fails, raise an exception.
        
        Example:
            async def validate(self):
                if 'user_id' not in self.data:
                    raise ValueError("user_id is required")
                if not isinstance(self.data['user_id'], str):
                    raise TypeError("user_id must be a string")
        """
        pass
    
    @abstractmethod
    async def process(self) -> Any:
        """
        Main method that must be implemented by each Lambda class
        
        This is where you implement the business logic of your Lambda.
        Return any serializable data that will be included in the response.
        
        Example:
            async def process(self):
                user_id = self.data['user_id']
                user = await self.db.users_db.users.find_one({'_id': user_id})
                return {'user': user}
        
        Returns:
            Any serializable data (dict, list, str, int, etc.)
        
        Raises:
            Exception: Any error in the processing
        """
        raise NotImplementedError("You must implement the process() method")
    
    async def run(self) -> Dict[str, Any]:
        """
        Execute the complete Lambda workflow
        
        This method orchestrates the execution:
        1. Validates the input data
        2. Processes the business logic
        3. Returns the result with success flag
        
        Returns:
            Dict with 'success' flag and 'data' with the result
            Format: {'success': True, 'data': <result>}
        
        Raises:
            Exception: Any error during validation or processing
        """
        try:
            # Step 0: Setup session context
            session_data = self.event.get('session')
            if not session_data or not session_data.get('state'):
                raise ValueError("'session' with 'state' is required in the event")
            session = Session.from_dict(session_data)
            set_session(session)

            # Step 1: Validate
            await self.validate()
            # Step 2: Process
            result = await self.process()
            
            # Step 3: Return result
            return {
                'success': True,
                'data': result
            }
            
        except Exception as e:
            self.logger.exception(f"Error in Lambda execution: {e}")
            raise
