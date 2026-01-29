"""
API Handler - Generic reusable handler for all APIs
"""

import json
import asyncio
import logging
import sys
from typing import Dict, Any

from .dispatcher import Dispatcher
from ..utils.json_encoder import MongoJSONEncoder
from ..database.mongo_manager import MongoManager

def setup_logging():
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Solo configurar si no tiene handlers
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        root_logger.addHandler(handler)
    else:
        # Si ya tiene handlers, solo actualizar el nivel
        for handler in root_logger.handlers:
            handler.setLevel(logging.INFO)

# Llamar al inicio del módulo
setup_logging()

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
    
    # Initialize MongoDB connection (only once, reused in subsequent invocations)
    try:
        if not MongoManager.is_initialized():
            MongoManager.initialize()
    except Exception as e:
        logger.warning(f"MongoDB initialization failed: {e}")
    
    try:
        # Create dispatcher and execute
        dispatcher = Dispatcher(event)
        
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
        
        response = loop.run_until_complete(dispatcher.dispatch())
        
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
            'body': json.dumps(response['body'], cls=MongoJSONEncoder, ensure_ascii=False)
        }
        
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
            }, cls=MongoJSONEncoder)
        }

