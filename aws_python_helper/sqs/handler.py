"""
SQS Handler - Generic reusable handler for SQS consumers
"""

import asyncio
import logging
import sys
from typing import Dict, Any, Callable

from .fetcher import SQSFetcher
from ..utils.serializer import serialize_mongo_types
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


def sqs_handler(consumer_name: str) -> Callable:
    """
    Factory that returns a handler for a specific consumer
    
    This pattern allows creating specific handlers for each consumer
    while keeping the code DRY.
    
    Args:
        consumer_name: Name of the consumer (must exist in consumer/)
    
    Returns:
        Configured handler function for that consumer
    """
    
    def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """
        Generic handler for AWS Lambda SQS
        
        Args:
            event: SQS event with Records
            context: Lambda context
        
        Returns:
            Summary of the processing
        """
        
        # Initialize MongoDB connection (only once, reused in subsequent invocations)
        try:
            if not MongoManager.is_initialized():
                MongoManager.initialize()
        except Exception as e:
            logger.warning(f"MongoDB initialization skipped: {e}")
        
        try:
            # Load consumer
            fetcher = SQSFetcher(consumer_name)
            consumer = fetcher.get_consumer()
            
            # Get records
            records = event.get('Records', [])
            
            # Process batch
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
            
            results = loop.run_until_complete(consumer.process_batch(records))
            
            # Count successes and failures
            success_count = sum(1 for r in results if r['success'])
            error_count = len(results) - success_count
            
            # Get failed message IDs for reportBatchItemFailures
            # This allows AWS SQS to retry only failed messages, not the entire batch
            failed_message_ids = [
                r.get('itemIdentifier') or r.get('messageId')
                for r in results
                if not r.get('success', True)
            ]
            
            response = {
                'processed': len(results),
                'successful': success_count,
                'failed': error_count,
                'results': results  # Include detailed results
            }
            
            # If there are failures, add reportBatchItemFailures for partial batch failure reporting
            # This tells AWS SQS to only retry the failed messages
            if failed_message_ids:
                response['batchItemFailures'] = [
                    {'itemIdentifier': msg_id} for msg_id in failed_message_ids
                ]
                logger.warning(
                    f"Processing complete with {error_count} failures. "
                    f"Failed messages will be retried: {failed_message_ids}"
                )
            
            # Serialize MongoDB types to JSON-serializable types
            # AWS Lambda will serialize the return value to JSON, so we need to ensure
            # all MongoDB types (ObjectId, datetime, etc.) are converted first
            response = serialize_mongo_types(response)
            
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

