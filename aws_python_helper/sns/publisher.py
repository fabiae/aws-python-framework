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
    ) -> Union[str, List[str]]:
        """
        Publishes one or more messages to the topic
        
        Args:
            message: Message or list of messages (dicts serializable to JSON) with at least a 'content' key containing
                the message body to send.
                Optionally, it can include:
                    - 'attributes': a dict with SNS message attributes
                    - 'subject': an optional subject string
                Example:
                    message = {
                        "content": {...},              # The message body that will be published
                        "attributes": {...},          # (Optional) SNS message attributes
                        "subject": "Optional subject" # (Optional) Subject for the message
                    }
                If you just want to send a body, use at least: {"content": ...}
                The 'content' key is required.
                If the message is a list, each item must have a 'content' key.
                The 'attributes' and 'subject' keys are optional.
        
        Returns:
            Message ID or list of message IDs
        
        Raises:
            ValueError: If the message is not serializable
            Exception: If the publication fails
        """
        # Determine if it is batch or simple
        if isinstance(message, list):
            return await self._publish_batch(message)
        else:
            return await self._publish_single(message)
    
    async def _publish_single(
        self,
        message: Dict[str, Any]
    ) -> str:
        """
        Publishes a single message
        
        Args:
            message: Message to publish with at least a 'content' key containing the message body to send.
                Optionally, it can include:
                    - 'attributes': a dict with SNS message attributes
                    - 'subject': an optional subject string
                Example:
                    message = {
                        "content": {...},              # The message body that will be published
                        "attributes": {...},          # (Optional) SNS message attributes
                        "subject": "Optional subject" # (Optional) Subject for the message
                    }
                If you just want to send a body, use at least: {"content": ...}
                The 'content' key is required.
                The 'attributes' and 'subject' keys are optional.
        
        Returns:
            Message ID
        """
        try:
            
            # Prepare parameters
            params = {
                'TopicArn': self.topic_arn,
                **self._format_message(message)
            }

            # Publish
            response = self.sns_client.publish(**params)
            
            message_id = response['MessageId']
            self.logger.info(f"Published message {message_id} to {self.topic_arn}")
            
            return message_id
            
        except Exception as e:
            self.logger.error(f"Error publishing message to {self.topic_arn}: {e}")
            raise
    
    async def _publish_batch(
        self,
        messages: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Publishes multiple messages (one by one, SNS does not have native batch)
        
        Args:
            messages: List of messages to publish
                Each message must have at least a 'content' key containing the message body to send.
                Optionally, it can include:
                    - 'attributes': a dict with SNS message attributes
                    - 'subject': an optional subject string
                Example:
                    messages = [
                        {
                            "content": {...},              # The message body that will be published
                            "attributes": {...},          # (Optional) SNS message attributes
                            "subject": "Optional subject" # (Optional) Subject for the message
                        }
                    ]
                If you just want to send a body, use at least: {"content": ...}
                The 'content' key is required.
                The 'attributes' and 'subject' keys are optional.
                If the message is a list, each item must have a 'content' key.
        
        Returns:
            List of message IDs
        """
        message_to_publish = []
        message_ids_success = []
        message_ids_failed = []

        params = {
            'TopicArn': self.topic_arn
        }
        
        for i, message in enumerate(messages):
            try:
                message_to_publish.append(self._format_message(message, i))
            except Exception as e:
                self.logger.error(f"Error publishing message {i} in batch: {e}")
                # Continue with the other messages
                continue

        params['PublishBatchRequestEntries'] = message_to_publish

        result = self.sns_client.publish_batch(**params)

        for message in result['Successful']:
            message_ids_success.append(message['MessageId'])

        for message in result['Failed']:
            message_ids_failed.append(None)
        
        return message_ids_success, message_ids_failed
    
    def _serialize_message(self, content: Dict[str, Any]) -> str:
        """
        Serializes the message to JSON
        
        Args:
            content: Content to serialize
        
        Returns:
            String JSON
        
        Raises:
            ValueError: If the content is not serializable
        """
        try:
            from ..utils.json_encoder import MongoJSONEncoder
            return json.dumps(content, cls=MongoJSONEncoder, ensure_ascii=False)
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
    
    def _format_message(self, message: Dict[str, Any], index: int) -> Dict[str, Any]:
        """
        Formats the message for SNS
        
        Args:
            message: Message to format
        
        Returns:
            Formatted message
        """
        content = message.get("content")
        if not content:
            raise ValueError("Message content is required")
        
        content = self._serialize_message(content)
        attributes = message.get("attributes")
        subject = message.get("subject")

        params = {
            'Id': index,
            'Message': content
        }
        
        # Add subject if exists
        if subject:
            params['Subject'] = subject
        
        # Add message attributes if exist
        if attributes:
            params['MessageAttributes'] = self._format_attributes(attributes)

        return params
