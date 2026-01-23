"""
Lambda Base Class - Base class for all standalone Lambda functions
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

from ..database.mongo_manager import MongoManager
from ..database.database_proxy import DatabaseProxy

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
        Access to MongoDB databases
        
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
            self.logger.info(f"Starting Lambda execution: {self.__class__.__name__}")
            
            # Step 1: Validate
            await self.validate()
            self.logger.debug("Validation passed")
            
            # Step 2: Process
            result = await self.process()
            self.logger.info(f"Lambda execution completed successfully")
            
            # Step 3: Return result
            return {
                'success': True,
                'data': result
            }
            
        except Exception as e:
            self.logger.exception(f"Error in Lambda execution: {e}")
            raise
