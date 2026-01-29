"""
SQS Consumer Base - Base class for all SQS consumers
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
import logging
import json

from ..database.mongo_manager import MongoManager
from ..database.database_proxy import DatabaseProxy


class SQSConsumer(ABC):
    """
    Base class for all SQS consumers
    
    Provides structure to process SQS messages in batch or individually.
    
    Processing modes:
        - "single": Process messages one by one using process_record()
        - "batch": Process all messages together using process_batch()
    
    Error Handling & Retries:
        Both modes support controlled retry via AWS SQS reportBatchItemFailures:
        - "single" mode: If process_record() raises an exception, that message
          is automatically reported for retry. Other messages continue processing.
        - "batch" mode: Return results with 'success': False and 'itemIdentifier'
          for failed messages. The handler will automatically create reportBatchItemFailures
          so AWS SQS retries only those specific messages.
        
        This ensures that if 1 message fails out of 5, only that 1 message is retried,
        not the entire batch.
    
    Usage:
        # Single mode (default):
        class MyConsumer(SQSConsumer):
            @property
            def processing_mode(self):
                return "single"  # or omit, "single" is default
            
            async def process_record(self, record):
                # Process individual record
                # If you raise an exception here, AWS SQS will retry only this message
                # Other messages in the batch will continue processing normally
                body = self.parse_body(record)
                # Your processing logic here
                # If something fails, just raise an exception:
                # if error_condition:
                #     raise ValueError("This message failed, will be retried")
                pass
        
        # Batch mode:
        class MyBatchConsumer(SQSConsumer):
            @property
            def processing_mode(self):
                return "batch"
            
            async def process_batch(self, records):
                # Process all records together
                # Must return a list of results with format:
                # [{'messageId': '...', 'success': True/False, 'error': '...', 'itemIdentifier': '...'}, ...]
                # 
                # IMPORTANT: For failed messages, include 'itemIdentifier' so AWS SQS
                # can retry only those specific messages. The handler will automatically
                # create reportBatchItemFailures for you.
                results = []
                for record in records:
                    message_id = record.get('messageId', 'unknown')
                    try:
                        # Your batch processing logic here
                        # Process all records together (bulk operations, transactions, etc.)
                        results.append({
                            'messageId': message_id,
                            'success': True
                        })
                    except Exception as e:
                        # Failed message - include itemIdentifier for controlled retry
                        results.append({
                            'messageId': message_id,
                            'success': False,
                            'error': str(e),
                            'itemIdentifier': message_id  # Required for reportBatchItemFailures
                        })
                return results
    """
    
    def __init__(self):
        """Initialize the consumer with a logger"""
        self.logger = logging.getLogger(self.__class__.__name__)
        self._db = None
    
    @property
    def processing_mode(self) -> str:
        """
        Processing mode: "single" or "batch"
        
        - "single": Process messages individually using process_record()
        - "batch": Process all messages together using process_batch()
        
        Returns:
            "single" or "batch" (default: "single")
        """
        return "single"
    
    @property
    def db(self):
        """
        Access to MongoDB databases
        
        Usage:
            result = await self.db.users_db.users.find_one({'_id': user_id})
        """
        if self._db is None:
            self._db = DatabaseProxy(MongoManager)
        return self._db
    
    async def process_record(self, record: Dict[str, Any]):
        """
        Process an individual SQS record
        
        This method is required when processing_mode is "single".
        When processing_mode is "batch", this method is optional.
        
        If this method raises an exception, AWS SQS will automatically retry
        only that specific message. Other messages in the batch will continue
        processing normally.
        
        Args:
            record: SQS record with 'body', 'messageId', etc.
        
        Raises:
            Exception: Any error in the processing. The exception will be caught
                      and the message will be reported for retry by AWS SQS.
        """
        # Only raise NotImplementedError if in single mode
        if self.processing_mode == "single":
            raise NotImplementedError(
                f"You must implement process_record() when processing_mode is 'single'"
            )
        # In batch mode, this method is optional
    
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
        
        This method behavior depends on processing_mode:
        - "single": Processes records one by one using process_record() (default implementation)
        - "batch": Must be overridden to process all records together
        
        Args:
            records: List of SQS records
        
        Returns:
            List of results with success/error for each record.
            Format for each result:
            {
                'messageId': str,           # Required: message ID
                'success': bool,             # Required: True if successful, False if failed
                'error': str,                # Optional: error message if failed
                'itemIdentifier': str        # Required if failed: messageId for reportBatchItemFailures
            }
        
        Note:
            When processing_mode is "batch", you must override this method completely.
            When processing_mode is "single", implement process_record() instead.
            
            For failed messages in batch mode, include 'itemIdentifier' in the result
            to enable controlled retry via reportBatchItemFailures. The handler will
            automatically create the reportBatchItemFailures response for you.
        """
        mode = self.processing_mode
        
        if mode == "batch":
            # In batch mode, this method must be overridden
            # If we reach here, it means the method wasn't overridden
            raise NotImplementedError(
                f"When processing_mode is 'batch', you must override process_batch() method. "
                f"The base implementation only supports 'single' mode."
            )
        else:
            # Single mode: process records one by one using process_record()
            return await self._process_batch_single(records)
    
    async def _process_batch_single(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process records one by one (single mode)
        
        If a message fails (raises an exception), it will be reported as failed
        and AWS SQS will retry only that message. Other messages continue processing.
        
        Internal method used when processing_mode is "single"
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
                # Log the error but continue with other messages
                self.logger.error(
                    f"Error processing message {message_id}: {e}",
                    exc_info=True
                )
                results.append({
                    'messageId': message_id,
                    'success': False,
                    'error': str(e),
                    'itemIdentifier': message_id  # For reportBatchItemFailures (AWS SQS messageId)
                })
        
        # Log summary
        success_count = sum(1 for r in results if r['success'])
        failed_count = len(results) - success_count
        self.logger.info(
            f"Batch processing complete: {success_count} successful, {failed_count} failed"
        )
        
        return results

