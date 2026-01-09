"""
Response Utilities - Helpers to build standardized responses
"""

from typing import Dict, Any, Optional


class ApiResponse:
    """
    Helper to build standardized responses
    
    Provides static methods to create common responses
    quickly and consistently.
    """
    
    @staticmethod
    def success(data: Any, status_code: int = 200, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Create a success response
        
        Args:
            data: Data to return
            status_code: HTTP status code (default 200)
            headers: Additional headers
        
        Returns:
            Dict with code, body and headers
        """
        return {
            'code': status_code,
            'body': data,
            'headers': headers or {}
        }
    
    @staticmethod
    def error(message: str, status_code: int = 500, details: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Create an error response
        
        Args:
            message: Error message
            status_code: HTTP status code (default 500)
            details: Additional error details
        
        Returns:
            Dict with code, body and headers
        """
        body = {
            'error': True,
            'message': message
        }
        
        if details:
            body['details'] = details
        
        return {
            'code': status_code,
            'body': body,
            'headers': {}
        }
    
    @staticmethod
    def not_found(message: str = "Resource not found") -> Dict[str, Any]:
        """
        Create a 404 response
        
        Args:
            message: Custom message
        
        Returns:
            Dict with code 404
        """
        return ApiResponse.error(message, 404)
    
    @staticmethod
    def bad_request(message: str = "Bad request", details: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Create a 400 response
        
        Args:
            message: Error message
            details: Validation details
        
        Returns:
            Dict with code 400
        """
        return ApiResponse.error(message, 400, details)
    
    @staticmethod
    def unauthorized(message: str = "Unauthorized") -> Dict[str, Any]:
        """
        Create a 401 response
        
        Args:
            message: Error message
        
        Returns:
            Dict with code 401
        """
        return ApiResponse.error(message, 401)
    
    @staticmethod
    def forbidden(message: str = "Forbidden") -> Dict[str, Any]:
        """
        Create a 403 response
        
        Args:
            message: Error message
        
        Returns:
            Dict with code 403
        """
        return ApiResponse.error(message, 403)
    
    @staticmethod
    def created(data: Any, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Create a 201 response (Created)

        Args:
            data: Data of the created resource
            headers: Additional headers (e.g: Location)
        
        Returns:
            Dict with code 201
        """
        return ApiResponse.success(data, 201, headers)
    
    @staticmethod
    def no_content(headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Create a 204 response (No Content)
        
        Args:
            headers: Additional headers
        
        Returns:
            Dict with code 204
        """
        return {
            'code': 204,
            'body': None,
            'headers': headers or {}
        }

