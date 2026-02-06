"""
SQS Consumer Base - Base class for all SQS consumers
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
import logging
import json

from ..database.mongo_manager import MongoManager
from ..database.database_proxy import DatabaseProxy
from ..database.external_mongo_manager import ExternalMongoManager
from ..database.external_database_proxy import ExternalDatabaseProxy


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
        - "batch" mode: Use add_message_failed() to mark failed messages.
          The handler will automatically create reportBatchItemFailures so AWS SQS
          retries only those specific messages. Your _do_process_batch() is automatically
          wrapped with error handling.
        
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
                # Use add_message_failed() to mark failed messages - no need for try-except!
                # The base class wraps this method with error handling automatically
                for record in records:
                    message_id = record.get('messageId')
                    try:
                        # Your batch processing logic here
                        # Process all records together (bulk operations, transactions, etc.)
                        await self.process_message(record)
                    except Exception as e:
                        # Mark as failed - automatically handled by base class
                        self.add_message_failed(message_id, str(e))
                # No need to return results - base class handles it automatically
                # But you can return results if you want more control
    """
    
    def __init__(self):
        """Initialize the consumer with a logger"""
        self.logger = logging.getLogger(self.__class__.__name__)
        self._db = None
        self._external_db = None
        self._failed_messages = []  # Track failed messages for batch mode
    
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
        Access to MongoDB databases (main cluster)
        
        Usage:
            result = await self.db.users_db.users.find_one({'_id': user_id})
        """
        if self._db is None:
            self._db = DatabaseProxy(MongoManager)
        return self._db
    
    @property
    def external_db(self):
        """
        Access to external MongoDB clusters
        
        Returns None if EXTERNAL_MONGODB_CONNECTIONS environment variable is not set.
        
        Usage:
            if self.external_db:
                result = await self.external_db.ClusterDockets.smart_data.addresses.find_one({...})
                await self.external_db.ClusterDockets.core.users.insert_one({...})
        
        Returns:
            ExternalDatabaseProxy instance for accessing external clusters, or None if not configured
        """
        if self._external_db is None:
            # Initialize external connections if not already done
            if not ExternalMongoManager.is_initialized():
                has_connections = ExternalMongoManager.initialize()
                if not has_connections:
                    # No external connections available, return None
                    return None
            else:
                # Check if there are any connections available
                if len(ExternalMongoManager.get_available_clusters()) == 0:
                    return None
            
            self._external_db = ExternalDatabaseProxy()
        return self._external_db
    
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
    
    def add_message_failed(self, message_id: str, error: str = None):
        """
        Mark a message as failed (for batch mode)
        
        Use this method in your process_batch() implementation to mark messages
        that failed during batch processing. The handler will automatically
        create reportBatchItemFailures for these messages.
        
        Args:
            message_id: The messageId of the failed message
            error: Optional error message describing the failure
        
        Usage:
            async def process_batch(self, records):
                for record in records:
                    message_id = record.get('messageId')
                    try:
                        # Your processing logic
                        process_message(record)
                    except Exception as e:
                        # Mark as failed - no need to manually add to results
                        self.add_message_failed(message_id, str(e))
        """
        self._failed_messages.append({
            'messageId': message_id,
            'itemIdentifier': message_id,
            'error': error
        })
        if error:
            self.logger.error(f"Message {message_id} marked as failed: {error}")
        else:
            self.logger.error(f"Message {message_id} marked as failed")
    
    async def _process_batch_internal(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Internal method called by the handler to process a batch of SQS records
        
        This method routes to the appropriate processing based on processing_mode:
        - "single": Processes records one by one using process_record()
        - "batch": Wraps the user's process_batch() implementation with error handling
        
        Args:
            records: List of SQS records
        
        Returns:
            List of results with success/error for each record
        """
        mode = self.processing_mode
        
        if mode == "batch":
            # Reset failed messages list for this batch
            self._failed_messages = []
            # Wrap batch processing with error handling
            return await self._process_batch_wrapper(records)
        else:
            # Single mode: process records one by one using process_record()
            return await self._process_batch_single(records)
    
    async def process_batch(self, records: List[Dict[str, Any]]) -> None:
        """
        Process a batch of SQS records (to be overridden by user in batch mode)
        
        When processing_mode is "batch", override this method to implement
        your batch processing logic. Use add_message_failed() to mark failed messages.
        The base class will wrap your implementation with error handling automatically.
        
        This method should not return any value. Simply process the records and use
        add_message_failed() to mark any messages that fail. All other messages will
        be automatically marked as successful.
        
        Args:
            records: List of SQS records
        
        Example:
            async def process_batch(self, records):
                for record in records:
                    message_id = record.get('messageId')
                    try:
                        # Your processing logic
                        await self.process_message(record)
                    except Exception as e:
                        # Mark as failed - automatically handled
                        self.add_message_failed(message_id, str(e))
        """
        # Base implementation - should be overridden by user when processing_mode is "batch"
        # This method is only called when processing_mode is "batch"
        # If not overridden, all messages will be marked as successful
        # (unless marked as failed via add_message_failed)
        if self.processing_mode == "batch":
            raise NotImplementedError(
                f"You must implement process_batch() when processing_mode is 'batch'"
            )
    
    async def _process_batch_wrapper(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Wrapper for batch mode processing with automatic error handling
        
        This method wraps the user's process_batch() implementation with try-except
        to catch any unhandled exceptions. It also merges failed messages marked
        with add_message_failed() into the results.
        
        Internal method used when processing_mode is "batch"
        """
        # Get all message IDs upfront
        message_ids = [record.get('messageId', f'record-{i}') for i, record in enumerate(records)]
        results = []
        
        try:
            # Call the user's process_batch implementation (no return value expected)
            await self.process_batch(records)
            
            # Build results based on _failed_messages
            # All messages are successful by default, except those marked as failed
            for message_id in message_ids:
                # Check if this message was marked as failed
                failed_msg = next((fm for fm in self._failed_messages if fm['messageId'] == message_id), None)
                if failed_msg:
                    # Message was marked as failed
                    results.append({
                        'messageId': message_id,
                        'success': False,
                        'error': failed_msg.get('error'),
                        'itemIdentifier': failed_msg['itemIdentifier']
                    })
                else:
                    # Message was successful
                    results.append({
                        'messageId': message_id,
                        'success': True
                    })
            
        except Exception as e:
            # If the entire batch processing fails, mark all messages as failed
            self.logger.exception(f"Unhandled exception in process_batch: {e}")
            for message_id in message_ids:
                results.append({
                    'messageId': message_id,
                    'success': False,
                    'error': str(e),
                    'itemIdentifier': message_id
                })
        
        # Log summary
        success_count = sum(1 for r in results if r.get('success', False))
        failed_count = len(results) - success_count
        self.logger.info(
            f"Batch processing complete: {success_count} successful, {failed_count} failed"
        )
        
        return results
    
    
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

