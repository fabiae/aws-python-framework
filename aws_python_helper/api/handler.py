"""
API Handler - Generic reusable handler for all APIs
"""

import json
import asyncio
import logging
from typing import Dict, Any

from .dispatcher import Dispatcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def api_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Generic handler for AWS Lambda API Gateway
    
    This handler is reusable for ALL routes of your API.
    The dynamic routing is handled by the Dispatcher and Fetcher.
    
    Args:
        event: API Gateway event with path, httpMethod, body, etc.
        context: Lambda context (request_id, etc.)
    
    Returns:
        Response of API Gateway with statusCode, body and headers
    """

    print(f"Event: {json.dumps(event)}")
    print(f"Context: {context}")
    
    # Log the request
    request_id = context.aws_request_id if context else 'local'
    logger.info(f"Request ID: {request_id}")
    logger.debug(f"Event: {json.dumps(event)}")
    
    # Initialize MongoDB connection (only once, reused in subsequent invocations)
    try:
        from ..database.mongo_manager import MongoManager
        import os
        mongo_uri = os.getenv('MONGO_DB_URI') or os.getenv('MONGODB_URI')
        if mongo_uri and not MongoManager.is_initialized():
            logger.info("Initializing MongoDB connection")
            MongoManager.initialize(mongo_uri)
    except Exception as e:
        logger.warning(f"MongoDB initialization skipped: {e}")
    
    try:
        # Create dispatcher and execute
        dispatcher = Dispatcher(event)
        response = asyncio.run(dispatcher.dispatch())
        
        # Format response for API Gateway
        api_gateway_response = {
            'statusCode': response['code'],
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',  # Adjust as needed
                'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
                **response.get('headers', {})
            },
            'body': json.dumps(response['body'], ensure_ascii=False)
        }
        
        logger.info(f"Response: {response['code']}")
        return api_gateway_response
        
    except Exception as e:
        logger.exception(f"Unhandled exception in handler: {e}")
        
        # Generic error response
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal Server Error',
                'message': 'An unexpected error occurred'
            })
        }

