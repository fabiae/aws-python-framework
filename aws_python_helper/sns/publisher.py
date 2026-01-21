"""
SNS Publisher - Class to publish messages to SNS

Provides a simple interface to publish messages to SNS topics
without complex validations, only basic JSON serialization.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Union
import boto3
from abc import ABC


class SNSPublisher(ABC):
    """
    Base class to publish messages to SNS
    
    Features:
        - Simple and batch publishing
        - No complex structure validation
        - Support for message attributes
        - Automatic logging
    """
    
    def __init__(self, topic_arn: str, region: str = 'us-east-2'):
        """
        Initializes the publisher
        
        Args:
            topic_arn: ARN of the SNS topic
            region: AWS region (default: us-east-2)
        
        Raises:
            ValueError: If topic_arn is empty or None
        """
        if not topic_arn:
            raise ValueError(f"topic_arn is required for {self.__class__.__name__}")
        
        self.topic_arn = topic_arn
        self.region = region
        self.logger = logging.getLogger(self.__class__.__name__)
        self._sns_client = None
    
    @property
    def sns_client(self):
        """
        SNS client (lazy loading)
        
        Returns:
            boto3 SNS client
        """
        if self._sns_client is None:
            self._sns_client = boto3.client('sns', region_name=self.region)
        return self._sns_client
    
    async def publish(
        self,
        message: Union[Dict[str, Any], List[Dict[str, Any]]],
        attributes: Optional[Dict[str, str]] = None,
        subject: Optional[str] = None
    ) -> Union[str, List[str]]:
        """
        Publishes one or more messages to the topic
        
        Args:
            message: Message or list of messages (dicts serializable to JSON)
            attributes: Optional message attributes (only strings)
            subject: Subject of the message (optional, useful for emails)
        
        Returns:
            Message ID or list of message IDs
        
        Raises:
            ValueError: If the message is not serializable
            Exception: If the publication fails
        """
        # Determine if it is batch or simple
        if isinstance(message, list):
            return await self._publish_batch(message, attributes, subject)
        else:
            return await self._publish_single(message, attributes, subject)
    
    async def _publish_single(
        self,
        message: Dict[str, Any],
        attributes: Optional[Dict[str, str]] = None,
        subject: Optional[str] = None
    ) -> str:
        """
        Publishes a single message
        
        Args:
            message: Message to publish
            attributes: Message attributes
            subject: Subject of the message
        
        Returns:
            Message ID
        """
        try:
            # Serialize message
            message_body = self._serialize_message(message)
            
            # Prepare parameters
            params = {
                'TopicArn': self.topic_arn,
                'Message': message_body
            }
            
            # Add subject if exists
            if subject:
                params['Subject'] = subject
            
            # Add message attributes if exist
            if attributes:
                params['MessageAttributes'] = self._format_attributes(attributes)
            
            # Publish
            self.logger.debug(f"Publishing message to {self.topic_arn}")
            response = self.sns_client.publish(**params)
            
            message_id = response['MessageId']
            self.logger.info(f"Published message {message_id} to {self.topic_arn}")
            
            return message_id
            
        except Exception as e:
            self.logger.error(f"Error publishing message to {self.topic_arn}: {e}")
            raise
    
    async def _publish_batch(
        self,
        messages: List[Dict[str, Any]],
        attributes: Optional[Dict[str, str]] = None,
        subject: Optional[str] = None
    ) -> List[str]:
        """
        Publishes multiple messages (one by one, SNS does not have native batch)
        
        Args:
            messages: List of messages to publish
            attributes: Message attributes (applied to all)
            subject: Subject (applied to all)
        
        Returns:
            List of message IDs
        """
        message_ids = []
        
        for i, message in enumerate(messages):
            try:
                message_id = await self._publish_single(message, attributes, subject)
                message_ids.append(message_id)
            except Exception as e:
                self.logger.error(f"Error publishing message {i} in batch: {e}")
                # Continue with the other messages
                message_ids.append(None)
        
        success_count = sum(1 for mid in message_ids if mid is not None)
        self.logger.info(
            f"Batch publish complete: {success_count}/{len(messages)} successful"
        )
        
        return message_ids
    
    def _serialize_message(self, message: Dict[str, Any]) -> str:
        """
        Serializes the message to JSON
        
        Args:
            message: Message to serialize
        
        Returns:
            String JSON
        
        Raises:
            ValueError: If the message is not serializable
        """
        try:
            from ..utils.json_encoder import MongoJSONEncoder
            return json.dumps(message, cls=MongoJSONEncoder, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Message is not JSON serializable: {e}")
    
    def _format_attributes(self, attributes: Dict[str, str]) -> Dict[str, Dict]:
        """
        Formats the message attributes for SNS
        
        SNS requires format: {'attr_name': {'DataType': 'String', 'StringValue': 'value'}}
        
        Args:
            attributes: Dictionary of attributes
        
        Returns:
            Dictionary in SNS format
        """
        formatted = {}
        
        for key, value in attributes.items():
            # Convert booleans to strings
            if isinstance(value, bool):
                value = str(value)
            
            formatted[key] = {
                'DataType': 'String',
                'StringValue': str(value)
            }
        
        return formatted
