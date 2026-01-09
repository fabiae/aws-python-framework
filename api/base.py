"""
API Base Class - Clase base para todas las APIs REST
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List


class API(ABC):
    """
    Clase base para todas las APIs
    
    Clase base que proporciona la estructura básica
    para manejar requests y responses de API Gateway.
    
    Ejemplo de uso:
        class UserListAPI(API):
            async def process(self):
                users = await self.db.users_db.users.find().to_list(100)
                self.set_body(users)
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
    
    # ==================== Request Getters/Setters ====================
    
    @property
    def endpoint(self) -> str:
        """El endpoint de la request (ej: 'users' o 'users/123')"""
        return self._endpoint
    
    @endpoint.setter
    def endpoint(self, value: str):
        self._endpoint = value
    
    @property
    def http_method(self) -> str:
        """El método HTTP (get, post, put, delete, etc.)"""
        return self._http_method
    
    @http_method.setter
    def http_method(self, value: str):
        self._http_method = value
    
    @property
    def data(self) -> Dict[str, Any]:
        """Los datos de la request (body para POST/PUT, query params para GET)"""
        return self._data
    
    @data.setter
    def data(self, value: Dict[str, Any]):
        self._data = value or {}
    
    @property
    def headers(self) -> Dict[str, str]:
        """Headers de la request"""
        return self._headers
    
    @headers.setter
    def headers(self, value: Dict[str, str]):
        self._headers = value or {}
    
    @property
    def path_parameters(self) -> List[str]:
        """Path parameters extraídos del URL (ej: ['123'] para /users/123)"""
        return self._path_parameters
    
    @path_parameters.setter
    def path_parameters(self, value: List[str]):
        self._path_parameters = value or []
    
    @property
    def query_parameters(self) -> Dict[str, Any]:
        """Query parameters de la URL"""
        return self._query_parameters
    
    @query_parameters.setter
    def query_parameters(self, value: Dict[str, Any]):
        self._query_parameters = value or {}
    
    # ==================== Database Access ====================
    
    @property
    def db(self):
        """
        Acceso a bases de datos MongoDB
        
        Uso:
            # Acceder a diferentes bases de datos y colecciones
            result = await self.db.users_db.users.find_one({'_id': user_id})
            await self.db.analytics_db.logs.insert_one({'action': 'user_login'})
        """
        if self._db is None:
            from lambda_framework.database.mongo_manager import MongoManager
            from lambda_framework.database.database_proxy import DatabaseProxy
            self._db = DatabaseProxy(MongoManager)
        return self._db
    
    # ==================== Response Builders ====================
    
    def set_code(self, code: int):
        """
        Establece el código de respuesta HTTP
        
        Args:
            code: Código HTTP (200, 404, 500, etc.)
        
        Returns:
            self para encadenar llamadas
        """
        self._response_code = code
        return self
    
    def set_body(self, body: Any):
        """
        Establece el body de la respuesta
        
        Args:
            body: Cualquier objeto serializable a JSON
        
        Returns:
            self para encadenar llamadas
        """
        self._response_body = body
        return self
    
    def set_header(self, key: str, value: str):
        """
        Agrega un header a la respuesta
        
        Args:
            key: Nombre del header
            value: Valor del header
        
        Returns:
            self para encadenar llamadas
        """
        self._response_headers[key] = value
        return self
    
    def set_headers(self, headers: Dict[str, str]):
        """
        Establece múltiples headers
        
        Args:
            headers: Diccionario de headers
        
        Returns:
            self para encadenar llamadas
        """
        self._response_headers.update(headers)
        return self
    
    @property
    def response(self) -> Dict[str, Any]:
        """
        Retorna el objeto de respuesta completo
        
        Returns:
            Dict con code, body y headers
        """
        return {
            'code': self._response_code,
            'body': self._response_body,
            'headers': self._response_headers
        }
    
    # ==================== Lifecycle Hooks ====================
    
    async def validate(self):
        """
        Hook para validación de datos
        
        Override este método para implementar validaciones personalizadas.
        Si la validación falla, lanza una excepción.
        
        Ejemplo:
            async def validate(self):
                if 'email' not in self.data:
                    raise ValueError("Email is required")
        """
        pass
    
    @abstractmethod
    async def process(self):
        """
        Método principal que debe implementar cada clase
        
        Este es el método donde implementas la lógica de tu API.
        Debes usar set_body() y opcionalmente set_code() y set_header().
        
        Ejemplo:
            async def process(self):
                users = await self.db.users_db.users.find().to_list(100)
                self.set_body(users)
        """
        raise NotImplementedError("Debes implementar el método process()")

