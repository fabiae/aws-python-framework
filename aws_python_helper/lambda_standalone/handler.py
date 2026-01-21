"""
Lambda Handler - Generic reusable handler for standalone Lambda functions
"""

import asyncio
import logging
import json
from typing import Dict, Any, Callable

from .fetcher import LambdaFetcher
from ..utils.serializer import serialize_mongo_types
from ..database.mongo_manager import MongoManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def lambda_handler(lambda_name: str) -> Callable:
    """
    Factory that returns a handler for a specific lambda
    
    This pattern allows creating specific handlers for each lambda
    while keeping the code DRY.
    
    Usage in src/handlers/lambda_handler.py:
        from aws_python_helper.lambda_standalone.handler import lambda_handler
        
        generate_route_handler = lambda_handler('generate-route')
        sync_carrier_handler = lambda_handler('sync-carrier')
        
        __all__ = ['generate_route_handler', 'sync_carrier_handler']
    
    Args:
        lambda_name: Name of the lambda in kebab-case (must exist in src/lambdas/)
    
    Returns:
        Configured handler function for that lambda
    """
    
    def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """
        Generic handler for standalone Lambda functions
        
        These are lambdas invoked directly via AWS SDK, not through
        API Gateway or other event sources.
        
        Args:
            event: Lambda event with data
            context: Lambda context with request_id, etc.
        
        Returns:
            Result of lambda execution with format:
            {'success': True, 'data': <result>} or
            {'success': False, 'error': <error_message>}
        """

        print(f"Event: {json.dumps(event)}")
        print(f"Context: {context}")
    
        # Log the request
        request_id = context.aws_request_id if context else 'local'
        logger.info(f"Lambda Handler - Request ID: {request_id}")
        logger.info(f"Lambda: {lambda_name}")
        logger.debug(f"Event: {event}")
        
        # Initialize MongoDB connection (only once, reused in subsequent invocations)
        try:
            if not MongoManager.is_initialized():
                logger.info("Initializing MongoDB connection")
                MongoManager.initialize()
        except Exception as e:
            logger.warning(f"MongoDB initialization skipped: {e}")
        
        try:
            # Load lambda class
            fetcher = LambdaFetcher(lambda_name)
            lambda_instance = fetcher.get_lambda(event, context)
            
            # Execute lambda
            # Use get_event_loop() instead of asyncio.run() to avoid closing the loop
            # This is important for AWS Lambda container reuse with Motor/MongoDB
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            result = loop.run_until_complete(lambda_instance.run())
            
            # Serialize MongoDB types to JSON-serializable types
            # AWS Lambda will serialize the return value to JSON, so we need to ensure
            # all MongoDB types (ObjectId, datetime, etc.) are converted first
            result = serialize_mongo_types(result)
            
            logger.info(f"Lambda {lambda_name} executed successfully")
            return result
            
        except Exception as e:
            logger.exception(f"Unhandled exception in Lambda handler: {e}")
            
            # Return error response
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    return handler
