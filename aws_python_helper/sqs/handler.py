"""
SQS Handler - Generic reusable handler for SQS consumers
"""

import asyncio
import logging
from typing import Dict, Any, Callable

from .fetcher import SQSFetcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
        
        # Log the request
        request_id = context.request_id if context else 'local'
        logger.info(f"SQS Handler - Request ID: {request_id}")
        logger.info(f"Consumer: {consumer_name}")
        
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
            # Load consumer
            fetcher = SQSFetcher(consumer_name)
            consumer = fetcher.get_consumer()
            
            # Get records
            records = event.get('Records', [])
            logger.info(f"Processing {len(records)} records")
            
            # Process batch
            results = asyncio.run(consumer.process_batch(records))
            
            # Count successes and failures
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

