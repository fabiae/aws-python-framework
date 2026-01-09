"""
Lambda Handler - Handler genérico reutilizable para todas las APIs
"""

import json
import asyncio
import logging
from typing import Dict, Any

from .dispatcher import Dispatcher

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handler genérico para AWS Lambda API Gateway
    
    Este handler es reutilizable para TODAS las rutas de tu API.
    El routing dinámico se maneja mediante el Dispatcher y Fetcher.
    
    Uso en Terraform/Serverless:
        handler: handlers.api_handler.handler
    
    Args:
        event: Evento de API Gateway con path, httpMethod, body, etc.
        context: Contexto de Lambda (request_id, etc.)
    
    Returns:
        Response de API Gateway con statusCode, body y headers
    """
    
    # Log del request
    request_id = context.request_id if context else 'local'
    logger.info(f"Request ID: {request_id}")
    logger.debug(f"Event: {json.dumps(event)}")
    
    try:
        # Crear dispatcher y ejecutar
        dispatcher = Dispatcher(event)
        response = asyncio.run(dispatcher.dispatch())
        
        # Formatear respuesta para API Gateway
        api_gateway_response = {
            'statusCode': response['code'],
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',  # Ajustar según necesites
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
        
        # Respuesta de error genérica
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

