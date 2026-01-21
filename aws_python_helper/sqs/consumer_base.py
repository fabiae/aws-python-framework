"""
SQS Consumer Base - Base class for all SQS consumers
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
import logging
import json


class SQSConsumer(ABC):
    """
    Base class for all SQS consumers
    
    Provides structure to process SQS messages in batch or individually.
    """
    
    def __init__(self):
        """Initialize the consumer with a logger"""
        self.logger = logging.getLogger(self.__class__.__name__)
        self._db = None
    
    @property
    def db(self):
        """
        Access to MongoDB databases
        
        Usage:
            result = await self.db.users_db.users.find_one({'_id': user_id})
        """
        if self._db is None:
            from ..database.mongo_manager import MongoManager
            from ..database.database_proxy import DatabaseProxy
            self._db = DatabaseProxy(MongoManager)
        return self._db
    
    @abstractmethod
    async def process_record(self, record: Dict[str, Any]):
        """
        Process an individual SQS record
        
        Args:
            record: SQS record with 'body', 'messageId', etc.
        
        Raises:
            Exception: Any error in the processing
        """
        raise NotImplementedError("You must implement process_record()")
    
    def parse_body(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse the body of the SQS message
        
        Args:
            record: SQS record
        
        Returns:
            Parsed body as dict
        """
        body = record.get('body', '{}')
        
        if isinstance(body, str):
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                self.logger.warning(f"Could not parse body as JSON: {body}")
                return {'raw': body}
        
        return body
    
    async def process_batch(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process a batch of SQS records
        
        Args:
            records: List of SQS records
        
        Returns:
            List of results with success/error for each record
        """
        results = []
        
        for i, record in enumerate(records):
            message_id = record.get('messageId', f'record-{i}')
            
            try:
                self.logger.info(f"Processing message: {message_id}")
                await self.process_record(record)
                results.append({
                    'messageId': message_id,
                    'success': True
                })
                self.logger.info(f"Successfully processed message: {message_id}")
                
            except Exception as e:
                self.logger.error(
                    f"Error processing message {message_id}: {e}",
                    exc_info=True
                )
                results.append({
                    'messageId': message_id,
                    'success': False,
                    'error': str(e)
                })
        
        # Log summary
        success_count = sum(1 for r in results if r['success'])
        self.logger.info(
            f"Batch processing complete: {success_count}/{len(records)} successful"
        )
        
        return results

