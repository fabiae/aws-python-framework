"""
Lambda Fetcher - Dynamically loads Lambda classes based on naming convention
"""

import importlib
from typing import Any, Dict


class LambdaFetcher:
    """
    Dynamically loads lambda classes based on naming convention
    
    The fetcher converts lambda names from kebab-case to the appropriate
    module path (snake_case) and class name (PascalCase).
    
    Convention:
        lambda-name -> src.lambdas.lambda_name -> LambdaNameLambda
    
    Examples:
        'generate-route' -> src.lambdas.generate_route -> GenerateRouteLambda
        'sync-carrier' -> src.lambdas.sync_carrier -> SyncCarrierLambda
        'process-payment' -> src.lambdas.process_payment -> ProcessPaymentLambda
    """
    
    def __init__(self, lambda_name: str):
        """
        Initialize the fetcher with a lambda name
        
        Args:
            lambda_name: Name of the lambda in kebab-case (e.g., 'generate-route')
        """
        self.lambda_name = lambda_name
    
    def get_lambda(self, event: Dict[str, Any], context: Any):
        """
        Load and instantiate the lambda class
        
        Args:
            event: Lambda event with data
            context: Lambda context
        
        Returns:
            Instance of the Lambda class
        
        Raises:
            ImportError: If the module or class cannot be found
        """
        # Convert kebab-case to snake_case for module import
        # Example: 'generate-route' -> 'generate_route'
        module_name = self.lambda_name.replace('-', '_')
        
        # Convert kebab-case to PascalCase for class name
        # Example: 'generate-route' -> 'GenerateRouteLambda'
        class_name = ''.join(
            word.capitalize() for word in self.lambda_name.split('-')
        ) + 'Lambda'
        
        try:
            # Import the module
            # Example: import src.lambdas.generate_route
            module = importlib.import_module(f'src.lambdas.{module_name}')
            
            # Get the class from the module
            # Example: GenerateRouteLambda = getattr(module, 'GenerateRouteLambda')
            lambda_class = getattr(module, class_name)
            
            # Instantiate and return
            # Example: return GenerateRouteLambda(event, context)
            return lambda_class(event, context)
            
        except ImportError as e:
            raise ImportError(
                f"Could not import lambda module '{self.lambda_name}'. "
                f"Expected module: src.lambdas.{module_name}. "
                f"Make sure the file exists and is in the correct location. "
                f"Error: {e}"
            )
        except AttributeError as e:
            raise ImportError(
                f"Could not find lambda class '{class_name}' in module 'src.lambdas.{module_name}'. "
                f"Make sure the class is defined and named correctly. "
                f"Error: {e}"
            )
