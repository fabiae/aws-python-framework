"""
SQS Handler - Handler genérico reutilizable para consumers de SQS
"""

import asyncio
import logging
from typing import Dict, Any, Callable

from .fetcher import SQSFetcher

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def sqs_handler(consumer_name: str) -> Callable:
    """
    Factory que retorna un handler para un consumer específico
    
    Este patrón permite crear handlers específicos para cada consumer
    mientras mantiene el código DRY.
    
    Uso:
        # En tu archivo handler
        from lambda_framework.sqs.handler import sqs_handler
        
        handler = sqs_handler('user-created')
    
    Args:
        consumer_name: Nombre del consumer (debe existir en consumers/)
    
    Returns:
        Función handler configurada para ese consumer
    """
    
    def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """
        Handler genérico para AWS Lambda SQS
        
        Args:
            event: Evento de SQS con Records
            context: Contexto de Lambda
        
        Returns:
            Resumen del procesamiento
        """
        
        # Log del request
        request_id = context.request_id if context else 'local'
        logger.info(f"SQS Handler - Request ID: {request_id}")
        logger.info(f"Consumer: {consumer_name}")
        
        try:
            # Cargar consumer
            fetcher = SQSFetcher(consumer_name)
            consumer = fetcher.get_consumer()
            
            # Obtener registros
            records = event.get('Records', [])
            logger.info(f"Processing {len(records)} records")
            
            # Procesar batch
            results = asyncio.run(consumer.process_batch(records))
            
            # Contar éxitos y fallos
            success_count = sum(1 for r in results if r['success'])
            error_count = len(results) - success_count
            
            response = {
                'processed': len(results),
                'successful': success_count,
                'failed': error_count
            }
            
            logger.info(f"Processing complete: {response}")
            
            return response
            
        except Exception as e:
            logger.exception(f"Unhandled exception in SQS handler: {e}")
            
            return {
                'processed': 0,
                'successful': 0,
                'failed': len(event.get('Records', [])),
                'error': str(e)
            }
    
    return handler


def create_sqs_handler(consumer_name: str) -> Callable:
    """
    Alias de sqs_handler para mayor claridad
    
    Args:
        consumer_name: Nombre del consumer
    
    Returns:
        Función handler configurada
    """
    return sqs_handler(consumer_name)

