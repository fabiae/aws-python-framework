"""
SQS Consumer Base - Base class for all SQS consumers
"""

import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import logging
import json

from ..context.session import Session, get_session, set_session
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
    def session(self) -> Session:
        """
        Request-scoped session with state, user, and extensible properties.

        Populated automatically from the SQS message attributes.
        """
        return get_session()

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
    
    def get_queue_url(self) -> str:
        """
        Get the URL of the SQS queue
        
        Returns:
            The URL of the SQS queue
        """

        base_url = f"https://sqs.{os.getenv('AWS_REGION')}.amazonaws.com/{os.getenv('AWS_ACCOUNT_ID')}"
        queue_name = f"{os.getenv('SERVICE_NAME')}{os.getenv('QUEUE_NAME')}-{os.getenv('ENV')}"
        return f"{base_url}/{queue_name}"
    
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
    
    def extract_content_message(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse the body of the SQS message
        
        When SNS sends messages to SQS, the body has this structure:
        {
            "Type": "Notification",
            "Message": "{...the actual message serialized as JSON string...}",
            "MessageAttributes": {...}
        }
        
        This method automatically detects SNS messages and extracts the actual content
        from the "Message" field. If it's not an SNS message, it parses the body directly.
        
        Args:
            record: SQS record with 'body' field
        
        Returns:
            Parsed body as dict. For SNS messages, returns the parsed content from the "Message" field.
            For regular SQS messages, returns the parsed body directly.
        """
        body = record.get('body', '{}')
        
        # Parse the body string to JSON if needed
        if isinstance(body, str):
            try:
                body_json = json.loads(body)
            except json.JSONDecodeError:
                self.logger.warning(f"Could not parse body as JSON: {body}")
                return {'raw': body}
        else:
            body_json = body
        
        # Check if this is an SNS notification message
        if isinstance(body_json, dict) and body_json.get('Type') == 'Notification':
            # Extract the actual message from the "Message" field
            message_str = body_json.get('Message', '{}')
            
            if isinstance(message_str, str):
                try:
                    # Parse the JSON string in the Message field
                    message_content = json.loads(message_str)
                    self.logger.debug(f"Extracted SNS message content: {message_content}")
                    return message_content
                except json.JSONDecodeError:
                    self.logger.warning(f"Could not parse SNS Message field as JSON: {message_str}")
                    return {'raw': message_str, 'sns_notification': True}
            else:
                # Message field is already a dict
                return message_str
        
        # Not an SNS message, return the body as-is
        return body_json
    
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
    
    def _extract_session(self, record: Dict[str, Any]) -> Optional[Session]:
        """
        Extract Session from an SQS record without setting it in the context.

        Looks first in SNS MessageAttributes for 'session' (injected automatically
        by SNSPublisher), then falls back to the parsed message body content for
        legacy 'constitution_state' field.

        Args:
            record: SQS record

        Returns:
            Session instance if found, None otherwise
        """
        # Primary: SNS MessageAttributes (auto-injected by SNSPublisher)
        raw_body = record.get('body', '{}')
        if isinstance(raw_body, str):
            try:
                raw_body_json = json.loads(raw_body)
            except json.JSONDecodeError:
                raw_body_json = {}
        else:
            raw_body_json = raw_body or {}

        if isinstance(raw_body_json, dict) and 'MessageAttributes' in raw_body_json:
            # Try full session attribute first
            session_attr = raw_body_json['MessageAttributes'].get('session', {})
            session_str = session_attr.get('Value')
            if session_str:
                try:
                    return Session.from_dict(json.loads(session_str))
                except (json.JSONDecodeError, TypeError):
                    self.logger.warning(f"Could not parse session attribute: {session_str}")

        # Fallback: parsed body content (for direct SQS messages without SNS wrapping)
        body = self.extract_content_message(record)
        state = body.get("constitution_state") or body.get("content", {}).get("constitution_state")
        if state:
            return Session(state=state)
        return None

    def _extract_and_set_session(self, record: Dict[str, Any]) -> Optional[Session]:
        """
        Extract Session from an SQS record and set it in the context.

        Args:
            record: SQS record

        Returns:
            Session instance if found, None otherwise
        """
        session = self._extract_session(record)
        if session:
            set_session(session)
        return session

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
        Wrapper for batch mode processing with automatic error handling.

        Groups records by session state so that each call to process_batch()
        has the correct session set in context. This ensures that repositories
        resolve to the right database even when a batch contains records from
        different states (e.g. connecticut + new_jersey in the same SQS batch).

        Internal method used when processing_mode is "batch".
        """
        all_results = []

        # Group records by session state
        state_groups: Dict[Optional[str], List[Dict[str, Any]]] = {}
        session_by_state: Dict[Optional[str], Session] = {}
        for record in records:
            session = self._extract_session(record)
            state = session.state if session else None
            state_groups.setdefault(state, []).append(record)
            if state and state not in session_by_state and session:
                session_by_state[state] = session

        for state, group_records in state_groups.items():
            if state and state in session_by_state:
                set_session(session_by_state[state])

            self._failed_messages = []  # reset per state group

            try:
                await self.process_batch(group_records)
            except Exception as e:
                self.logger.exception(f"Unhandled exception in process_batch (state={state}): {e}")
                for record in group_records:
                    msg_id = record.get('messageId', '')
                    all_results.append({
                        'messageId': msg_id,
                        'success': False,
                        'error': str(e),
                        'itemIdentifier': msg_id,
                    })
                continue

            failed_ids = {fm['messageId'] for fm in self._failed_messages}
            for record in group_records:
                msg_id = record.get('messageId', '')
                if msg_id in failed_ids:
                    failed_msg = next(fm for fm in self._failed_messages if fm['messageId'] == msg_id)
                    all_results.append({
                        'messageId': msg_id,
                        'success': False,
                        'error': failed_msg.get('error'),
                        'itemIdentifier': failed_msg['itemIdentifier'],
                    })
                else:
                    all_results.append({'messageId': msg_id, 'success': True})

        # Log summary
        success_count = sum(1 for r in all_results if r.get('success', False))
        failed_count = len(all_results) - success_count
        self.logger.info(
            f"Batch processing complete: {success_count} successful, {failed_count} failed"
        )

        return all_results
    
    
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
                # Auto-extract and set session for this record
                self._extract_and_set_session(record)

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

