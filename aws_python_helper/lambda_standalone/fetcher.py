"""
Lambda Fetcher - Dynamically loads Lambda classes based on naming convention
"""

import os
import importlib.util
from pathlib import Path
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)


class LambdaFetcher:
    """
    Dynamically loads lambda classes based on naming convention
    
    The fetcher searches for lambdas in folders within 'src/lambda/' with
    a main.py file inside.
    
    Convention:
        lambda-name -> src/lambda/lambda-name/main.py -> LambdaNameLambda
    
    Examples:
        'generate-route' -> src/lambda/generate-route/main.py -> GenerateRouteLambda
        'sync-carrier' -> src/lambda/sync-carrier/main.py -> SyncCarrierLambda
        'process-payment' -> src/lambda/process-payment/main.py -> ProcessPaymentLambda
    """
    
    LAMBDA_FOLDER = "lambda"
    _cache = {}
    
    def __init__(self, lambda_name: str):
        """
        Initialize the fetcher with a lambda name
        
        Args:
            lambda_name: Name of the lambda in kebab-case (e.g., 'generate-route')
        """
        self.lambda_name = lambda_name
    
    @property
    def file_path(self) -> str:
        """
        Calculate the path of the lambda file
        
        Converts 'generate-route' to 'generate-route/main.py'
        
        Returns:
            Absolute path to the lambda file
        """
        # Keep kebab-case for folder name (consistent with tasks)
        folder_name = self.lambda_name
        
        base_path = Path(os.getcwd()) / self.LAMBDA_FOLDER / folder_name
        file_path = base_path / 'main.py'
        
        logger.debug(f"Resolved lambda path: {file_path}")
        
        return str(file_path)
    
    def get_lambda(self, event: Dict[str, Any], context: Any):
        """
        Load and instantiate the lambda class
        
        Args:
            event: Lambda event with data
            context: Lambda context
        
        Returns:
            Instance of the Lambda class
        
        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the Lambda class is not valid
        """
        file_path = self.file_path
        
        # Verify cache
        if file_path in self._cache:
            logger.debug(f"Using cached lambda: {file_path}")
            return self._cache[file_path](event, context)
        
        # Verify that the file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(
                f"Lambda not found: {file_path}\n"
                f"Expected file for lambda '{self.lambda_name}' at {self.LAMBDA_FOLDER}/{self.lambda_name}/main.py"
            )
        
        # Load module dynamically
        spec = importlib.util.spec_from_file_location("lambda_module", file_path)
        if not spec or not spec.loader:
            raise ImportError(f"Could not load module spec from: {file_path}")
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Search for class that inherits from Lambda
        # Expected class name: 'generate-route' -> 'GenerateRouteLambda'
        class_name = ''.join(
            word.capitalize() for word in self.lambda_name.split('-')
        ) + 'Lambda'
        
        lambda_class = None
        for item_name in dir(module):
            item = getattr(module, item_name)
            if (isinstance(item, type) and 
                hasattr(item, 'process') and 
                item.__name__ not in ['Lambda', 'ABC']):
                lambda_class = item
                break
        
        if not lambda_class:
            raise ValueError(
                f"No Lambda class found in {file_path}\n"
                f"Make sure your file exports a class that inherits from Lambda\n"
                f"Expected class name: {class_name}"
            )
        
        # Cache the class
        self._cache[file_path] = lambda_class
        logger.info(f"Loaded lambda: {lambda_class.__name__} from {file_path}")
        
        # Return new instance
        return lambda_class(event, context)


