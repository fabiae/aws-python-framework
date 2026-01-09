"""
Response Utilities - Helpers para construir respuestas
"""

from typing import Dict, Any, Optional


class ApiResponse:
    """
    Helper para construir respuestas estandarizadas
    
    Proporciona métodos estáticos para crear respuestas comunes
    de forma rápida y consistente.
    """
    
    @staticmethod
    def success(data: Any, status_code: int = 200, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Crea una respuesta de éxito
        
        Args:
            data: Datos a retornar
            status_code: Código HTTP (default 200)
            headers: Headers adicionales
        
        Returns:
            Dict con code, body y headers
        """
        return {
            'code': status_code,
            'body': data,
            'headers': headers or {}
        }
    
    @staticmethod
    def error(message: str, status_code: int = 500, details: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Crea una respuesta de error
        
        Args:
            message: Mensaje de error
            status_code: Código HTTP (default 500)
            details: Detalles adicionales del error
        
        Returns:
            Dict con code, body y headers
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
        Crea una respuesta 404
        
        Args:
            message: Mensaje personalizado
        
        Returns:
            Dict con code 404
        """
        return ApiResponse.error(message, 404)
    
    @staticmethod
    def bad_request(message: str = "Bad request", details: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Crea una respuesta 400
        
        Args:
            message: Mensaje de error
            details: Detalles de validación
        
        Returns:
            Dict con code 400
        """
        return ApiResponse.error(message, 400, details)
    
    @staticmethod
    def unauthorized(message: str = "Unauthorized") -> Dict[str, Any]:
        """
        Crea una respuesta 401
        
        Args:
            message: Mensaje de error
        
        Returns:
            Dict con code 401
        """
        return ApiResponse.error(message, 401)
    
    @staticmethod
    def forbidden(message: str = "Forbidden") -> Dict[str, Any]:
        """
        Crea una respuesta 403
        
        Args:
            message: Mensaje de error
        
        Returns:
            Dict con code 403
        """
        return ApiResponse.error(message, 403)
    
    @staticmethod
    def created(data: Any, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Crea una respuesta 201 (Created)
        
        Args:
            data: Datos del recurso creado
            headers: Headers adicionales (ej: Location)
        
        Returns:
            Dict con code 201
        """
        return ApiResponse.success(data, 201, headers)
    
    @staticmethod
    def no_content(headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Crea una respuesta 204 (No Content)
        
        Args:
            headers: Headers adicionales
        
        Returns:
            Dict con code 204
        """
        return {
            'code': 204,
            'body': None,
            'headers': headers or {}
        }

