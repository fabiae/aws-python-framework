"""
Fetcher - Dynamically load API controllers based on endpoint and HTTP method
"""

import os
import importlib.util
from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class Fetcher:
    """
    Dynamically load API controllers
    
    Fetcher of the framework, determines which file to load based on
    the endpoint and HTTP method using convention over configuration.
    
    Examples:
        GET /users        -> api/users/list.py
        GET /users/123    -> api/users/get.py
        POST /users       -> api/users/post.py
        PUT /users/123    -> api/users/put.py
        DELETE /users/123 -> api/users/delete.py
    """
    
    API_FOLDER = "api"
    _cache = {}
    
    def __init__(self, endpoint: str, method: str):
        """
        Initializes the fetcher
        
        Args:
            endpoint: The endpoint of the API (e.g.: 'users' or 'users/123/posts')
            method: The HTTP method (get, post, put, delete, etc.)
        """
        self.endpoint = endpoint.strip('/')
        self.method = method.lower()
    
    @property
    def file_path(self) -> str:
        """
        Calculates the path of the file based on endpoint and method
        
        Logic:
        - Split endpoint by '/'
        - If method is GET and there is an odd number of parts -> 'list'
        - If method is GET and there is an even number of parts -> 'get'
        - Other methods use their direct name
        - Only the parts in even indices (0,2,4...) are directories
        
        Returns:
            Absolute path to the controller file
        """
        url_parts = self.endpoint.split('/') if self.endpoint else []
        
        # Determine the name of the method
        if self.method == 'get' and len(url_parts) % 2 == 1:
            method_name = 'list'
        else:
            method_name = self.method
        
        # Only even parts are directories (0, 2, 4...)
        # Odd parts are resource IDs
        dir_parts = [url_parts[i] for i in range(0, len(url_parts), 2)]
        file_dir = '/'.join(dir_parts) if dir_parts else ''
        
        # Build the complete path
        base_path = Path(os.getcwd()) / self.API_FOLDER
        file_path = base_path / file_dir / f"{method_name}.py"
        
        logger.debug(f"Resolved path: {file_path} for endpoint={self.endpoint}, method={self.method}")
        
        return str(file_path)
    
    @property
    def path_parameters(self) -> List[str]:
        """
        Extracts path parameters from the endpoint
        
        The path parameters are the parts in odd indices (1,3,5...)
        
        Examples:
            'users/123' -> ['123']
            'users/123/posts/456' -> ['123', '456']
            'users' -> []
        
        Returns:
            List of path parameters
        """
        url_parts = self.endpoint.split('/') if self.endpoint else []
        return [url_parts[i] for i in range(1, len(url_parts), 2)]
    
    def get_controller(self):
        """
        Loads and returns an instance of the controller
        
        Uses cache to avoid loading the same module multiple times.
        Searches for a class that inherits from API in the module.
        
        Returns:
            Instance of the API controller
        
        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the API class is not valid in the file
        """
        file_path = self.file_path
        
        # Verify cache
        if file_path in self._cache:
            logger.debug(f"Using cached controller: {file_path}")
            return self._cache[file_path]()
        
        # Verify that the file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(
                f"API Controller not found: {file_path}\n"
                f"Expected file for endpoint '{self.endpoint}' with method '{self.method}'"
            )
        
        # Load module dynamically
        spec = importlib.util.spec_from_file_location("api_module", file_path)
        if not spec or not spec.loader:
            raise ImportError(f"Could not load module spec from: {file_path}")
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Search for a class that inherits from API
        controller_class = None
        for item_name in dir(module):
            item = getattr(module, item_name)
            if (isinstance(item, type) and 
                hasattr(item, 'process') and 
                item.__name__ not in ['API', 'ABC']):
                controller_class = item
                break
        
        if not controller_class:
            raise ValueError(
                f"No API class found in {file_path}\n"
                f"Make sure your file exports a class that inherits from API"
            )
        
        # Cache the class (not the instance)
        self._cache[file_path] = controller_class
        logger.info(f"Loaded controller: {controller_class.__name__} from {file_path}")
        
        # Return new instance
        return controller_class()

