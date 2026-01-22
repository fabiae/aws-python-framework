"""
API Base Class - Base class for all REST APIs
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List


class API(ABC):
    """
    Base class for all REST APIs
    
    Base class that provides the basic structure
    to handle requests and responses from API Gateway.
    """
    
    def __init__(self):
        # Request properties
        self._endpoint: str = ""
        self._http_method: str = ""
        self._data: Dict[str, Any] = {}
        self._headers: Dict[str, str] = {}
        self._path_parameters: List[str] = []
        self._query_parameters: Dict[str, Any] = {}
        
        # Response properties
        self._response_code: Optional[int] = None
        self._response_body: Any = None
        self._response_headers: Dict[str, str] = {}
        
        # Database proxy
        self._db = None
        
        # Authentication properties
        self._current_user: Optional[Dict[str, Any]] = None
        self._auth_data: Optional[Dict[str, Any]] = None
        self._is_authenticated: bool = False
    
    @property
    def endpoint(self) -> str:
        """Endpoint of the request"""
        return self._endpoint
    
    @endpoint.setter
    def endpoint(self, value: str):
        self._endpoint = value
    
    @property
    def http_method(self) -> str:
        """HTTP method (get, post, put, delete, etc.)"""
        return self._http_method
    
    @http_method.setter
    def http_method(self, value: str):
        self._http_method = value
    
    @property
    def data(self) -> Dict[str, Any]:
        """Data of the request (body for POST/PUT, query params for GET)"""
        return self._data
    
    @data.setter
    def data(self, value: Dict[str, Any]):
        self._data = value or {}
    
    @property
    def headers(self) -> Dict[str, str]:
        """Headers of the request"""
        return self._headers
    
    @headers.setter
    def headers(self, value: Dict[str, str]):
        self._headers = value or {}
    
    @property
    def path_parameters(self) -> List[str]:
        """Path parameters extracted from the URL"""
        return self._path_parameters
    
    @path_parameters.setter
    def path_parameters(self, value: List[str]):
        self._path_parameters = value or []
    
    @property
    def query_parameters(self) -> Dict[str, Any]:
        """Query parameters of the URL"""
        return self._query_parameters
    
    @query_parameters.setter
    def query_parameters(self, value: Dict[str, Any]):
        self._query_parameters = value or {}
    
    @property
    def db(self):
        """
        Access to MongoDB databases
        """
        if self._db is None:
            from ..database.mongo_manager import MongoManager
            from ..database.database_proxy import DatabaseProxy
            self._db = DatabaseProxy(MongoManager)
        return self._db
    
    @property
    def current_user(self) -> Optional[Dict[str, Any]]:
        """
        Current authenticated user or None if not authenticated
        
        This property is populated by the authentication middleware
        when REQUIRE_AUTH=true.
        
        Returns:
            Dict with user data (email, role, name, etc.) or None
        
        Example:
            if self.is_authenticated:
                user_email = self.current_user['email']
                user_role = self.current_user.get('role', 'user')
        """
        return self._current_user
    
    @property
    def is_authenticated(self) -> bool:
        """
        True if the request has been authenticated
        
        This is set to True by the authentication middleware
        when a valid token is provided.
        
        Returns:
            True if authenticated, False otherwise
        
        Example:
            if not self.is_authenticated:
                raise ValueError("This operation requires authentication")
        """
        return self._is_authenticated
    
    @property
    def auth_data(self) -> Optional[Dict[str, Any]]:
        """
        Complete authentication data from the middleware
        
        This includes user data, token data, and other metadata
        provided by the authentication validator.
        
        Returns:
            Dict with authentication data or None
        """
        return self._auth_data
    
    def set_code(self, code: int):
        """
        Set the HTTP response code
        
        Args:
            code: HTTP code (200, 404, 500, etc.)
        
        Returns:
            self to chain calls
        """
        self._response_code = code
        return self
    
    def set_body(self, body: Any):
        """
        Set the body of the response
        
        Args:
            body: Any serializable object to JSON
        
        Returns:
            self to chain calls
        """
        self._response_body = body
        return self
    
    def set_header(self, key: str, value: str):
        """
        Add a header to the response
        
        Args:
            key: Name of the header
            value: Value of the header
        
        Returns:
            self to chain calls
        """
        self._response_headers[key] = value
        return self
    
    def set_headers(self, headers: Dict[str, str]):
        """
        Set multiple headers
        
        Args:
            headers: Dictionary of headers
        
        Returns:
            self to chain calls
        """
        self._response_headers.update(headers)
        return self
    
    @property
    def response(self) -> Dict[str, Any]:
        """
        Return the complete response object
        
        Returns:
            Dict with code, body and headers
        """
        return {
            'code': self._response_code,
            'body': self._response_body,
            'headers': self._response_headers
        }
    
    async def validate(self):
        """
        Hook for data validation
        
        Override this method to implement custom validations.
        If the validation fails, raise an exception.
        """
        pass
    
    @abstractmethod
    async def process(self):
        """
        Main method that must be implemented by each class
        
        This is the method where you implement the logic of your API.
        You must use set_body() and optionally set_code() and set_header().
        """
        raise NotImplementedError("You must implement the process() method")

