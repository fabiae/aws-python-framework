"""
Fetcher - Dynamically load API controllers based on endpoint and HTTP method
"""

import os
import importlib.util
from pathlib import Path
from typing import List

def load_controller_class(file_path: str):
    """The API class a controller file defines.

    Shared so the permission catalog asks the class the same questions the
    dispatcher does — a second way of finding it would answer differently the
    day one of them changes.
    """
    spec = importlib.util.spec_from_file_location("api_module", file_path)
    if not spec or not spec.loader:
        raise ImportError(f"Could not load module spec from: {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for item_name in dir(module):
        item = getattr(module, item_name)
        if (isinstance(item, type) and
                hasattr(item, 'process') and
                item.__name__ not in ['API', 'ABC'] and
                item.__module__ == module.__name__):
            return item

    raise ValueError(
        f"No API class found in {file_path}\n"
        f"Make sure your file exports a class that inherits from API"
    )


class Fetcher:
    """
    Dynamically load API controllers
    
    Fetcher of the framework, determines which file to load based on
    the endpoint and HTTP method using convention over configuration.
    
    Searches for APIs in the 'src/api/' folder.
    
    Examples:
        GET /users              -> src/api/users/list.py
        GET /users/123          -> src/api/users/get.py
        POST /users              -> src/api/users/post.py
        PUT /users/123           -> src/api/users/put.py
        DELETE /users/123        -> src/api/users/delete.py
        POST /auth/login         -> src/api/auth/login/post.py
        POST /auth/logout        -> src/api/auth/logout/post.py
        PUT /users/123/posts/456 -> src/api/users/posts/put.py (456 is ID)
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
        - For GET method:
          - If odd number of parts -> 'list' (e.g., 'users' -> users/list.py)
          - If even number of parts -> 'get' (e.g., 'users/123' -> users/get.py)
          - Only even-indexed parts are directories (0, 2, 4...), odd parts are IDs
        - For POST/PUT/DELETE methods:
          - All parts are directories (e.g., 'auth/login' -> auth/login/post.py)
          - Exception: If last part looks like an ID (numeric or UUID), it's treated as ID
        
        Returns:
            Absolute path to the controller file
        """
        url_parts = self.endpoint.split('/') if self.endpoint else []
        
        # Determine the name of the method
        if self.method == 'get' and len(url_parts) % 2 == 1:
            method_name = 'list'
        elif self.method == 'get' and len(url_parts) % 2 == 0:
            method_name = 'get'
        else:
            method_name = self.method
        
        # Determine directory structure based on method
        if self.method == 'get':
            # GET: Only even-indexed parts are directories, odd parts are IDs
            dir_parts = [url_parts[i] for i in range(0, len(url_parts), 2)]
        else:
            # POST/PUT/DELETE: All parts are directories
            # Exception: If last part looks like an ID (numeric or UUID), exclude it
            if url_parts and self._looks_like_id(url_parts[-1]):
                dir_parts = url_parts[:-1]
            else:
                dir_parts = url_parts
        
        file_dir = '/'.join(dir_parts) if dir_parts else ''
        
        # Build the complete path
        base_path = Path(os.getcwd()) / self.API_FOLDER
        file_path = base_path / file_dir / f"{method_name}.py"
        
        return str(file_path)
    
    def _looks_like_id(self, part: str) -> bool:
        """
        Check if a URL part looks like an ID (numeric, ObjectId or UUID format)
        
        Args:
            part: URL part to check
        
        Returns:
            True if it looks like an ID, False otherwise
        """
        if not part:
            return False
        
        # Check if it's numeric
        if part.isdigit():
            return True

        # ObjectId de MongoDB: 24 caracteres hexadecimales. Sin esto, un
        # PATCH /users/<oid> busca un directorio con el id como nombre.
        if len(part) == 24:
            try:
                int(part, 16)
                return True
            except ValueError:
                pass
        
        # Check if it's a UUID format (8-4-4-4-12 hex digits)
        if len(part) == 36 and part.count('-') == 4:
            try:
                # Try to validate as UUID
                parts = part.split('-')
                if all(len(p) in [8, 4, 4, 4, 12] for p in parts):
                    int(part.replace('-', ''), 16)
                    return True
            except ValueError:
                pass
        
        return False
    
    @property
    def path_parameters(self) -> List[str]:
        """
        Extracts path parameters from the endpoint
        
        For GET method: The path parameters are the parts in odd indices (1,3,5...)
        For other methods: Path parameters are parts that look like IDs (numeric or UUID)
        
        Examples:
            GET 'users/123' -> ['123']
            GET 'users/123/posts/456' -> ['123', '456']
            GET 'users' -> []
            POST 'auth/login' -> []
            PUT 'users/123' -> ['123']
            POST 'auth/login/abc123' -> ['abc123'] (if looks like ID)
        
        Returns:
            List of path parameters
        """
        url_parts = self.endpoint.split('/') if self.endpoint else []
        
        if self.method == 'get':
            # GET: Odd-indexed parts are IDs
            return [url_parts[i] for i in range(1, len(url_parts), 2)]
        else:
            # POST/PUT/DELETE: Extract parts that look like IDs
            params = []
            for part in url_parts:
                if self._looks_like_id(part):
                    params.append(part)
            return params
    
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
            return self._cache[file_path]()
        
        # Verify that the file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(
                f"API Controller not found: {file_path}\n"
                f"Expected file for endpoint '{self.endpoint}' with method '{self.method}'"
            )
        
        controller_class = load_controller_class(file_path)
        
        # Cache the class (not the instance)
        self._cache[file_path] = controller_class
        
        # Return new instance
        return controller_class()

