"""
SQS Fetcher - Dynamically load consumers based on name
"""

import os
import importlib.util
from pathlib import Path

class SQSFetcher:
    """
    Dynamically load SQS consumers
    
    Searches for consumers as direct files in 'src/consumer/' folder.
    
    Convention:
        consumer-name -> src/consumer/consumer_name.py -> ConsumerNameConsumer
    
    Examples:
        'user-created' -> src/consumer/user_created.py -> UserCreatedConsumer
        'title-indexed' -> src/consumer/title_indexed.py -> TitleIndexedConsumer
    """
    
    CONSUMERS_FOLDER = "consumer"
    _cache = {}
    
    def __init__(self, consumer_name: str):
        """
        Initialize the fetcher
        
        Args:
            consumer_name: Name of the consumer in kebab-case (e.g.: 'user-created')
        """
        self.consumer_name = consumer_name
    
    @property
    def file_path(self) -> str:
        """
        Calculate the path of the consumer file
        
        Converts 'user-created' to 'user_created.py'
        
        Returns:
            Absolute path to the consumer file
        """
        # Convert dashes to underscores for Python file name
        file_name = self.consumer_name.replace('-', '_') + '_consumer.py'
        
        base_path = Path(os.getcwd()) / self.CONSUMERS_FOLDER
        file_path = base_path / file_name
        
        return str(file_path)
    
    def get_consumer(self):
        """
        Load and return an instance of the consumer
        
        Returns:
            Instance of the consumer
        
        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the consumer class is not valid
        """
        file_path = self.file_path
        
        # Verify cache
        if file_path in self._cache:
            return self._cache[file_path]()
        
        # Verify that the file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(
                f"Consumer not found: {file_path}\n"
                f"Expected file for consumer '{self.consumer_name}' at {file_path}"
            )
        
        # Load module dynamically
        spec = importlib.util.spec_from_file_location("consumer_module", file_path)
        if not spec or not spec.loader:
            raise ImportError(f"Could not load module spec from: {file_path}")
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Search for class that inherits from SQSConsumer
        # Expected class name: 'user-created' -> 'UserCreatedConsumer'
        class_name = ''.join(
            word.capitalize() for word in self.consumer_name.split('-')
        ) + 'Consumer'
        
        consumer_class = None
        for item_name in dir(module):
            item = getattr(module, item_name)
            if (isinstance(item, type) and
                hasattr(item, 'process_record') and
                item.__name__ not in ['SQSConsumer', 'ABC'] and
                item.__module__ == module.__name__):
                consumer_class = item
                break
        
        if not consumer_class:
            raise ValueError(
                f"No SQSConsumer class found in {file_path}\n"
                f"Make sure your file exports a class that inherits from SQSConsumer\n"
                f"Expected class name: {class_name}"
            )
        
        # Cache the class
        self._cache[file_path] = consumer_class
        
        # Return new instance
        return consumer_class()
