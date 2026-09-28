"""
API Base Class - Base class for all REST APIs
"""

from abc import ABC, abstractmethod
import logging
from typing import Dict, Any, Optional, List, Tuple
from ..database.mongo_manager import MongoManager
from ..database.database_proxy import DatabaseProxy
from ..database.external_mongo_manager import ExternalMongoManager
from ..database.external_database_proxy import ExternalDatabaseProxy
from ..context.session import get_session


def _positive(value: Any) -> Optional[int]:
    """Un entero positivo de la query, o None si no lo es.

    Llega como texto desde la URL, y puede llegar cualquier cosa.
    """
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


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
        self._external_db = None
        
        # Authentication properties
        self._current_user: Optional[Dict[str, Any]] = None
        self._auth_data: Optional[Dict[str, Any]] = None
        self._is_authenticated: bool = False
        self.logger = logging.getLogger(self.__class__.__name__)   
    
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
        Access to MongoDB databases (main cluster)
        """
        if self._db is None:
            self._db = DatabaseProxy(MongoManager)
        return self._db
    
    @property
    def external_db(self):
        """
        Access to external MongoDB clusters
        
        Returns None if EXTERNAL_MONGODB_CONNECTIONS environment variable is not set.
        
        Usage:
            if self.external_db:
                result = await self.external_db.ClusterDockets.smart_data.addresses.find_one({...})
                await self.external_db.ClusterDockets.core.users.insert_one({...})
        
        Returns:
            ExternalDatabaseProxy instance for accessing external clusters, or None if not configured
        """
        if self._external_db is None:
            # Initialize external connections if not already done
            if not ExternalMongoManager.is_initialized():
                has_connections = ExternalMongoManager.initialize()
                if not has_connections:
                    # No external connections available, return None
                    return None
            else:
                # Check if there are any connections available
                if len(ExternalMongoManager.get_available_clusters()) == 0:
                    return None
            
            self._external_db = ExternalDatabaseProxy()
        return self._external_db
    
    @property
    def session(self):
        """
        Request-scoped session with state, user, and extensible properties.

        Populated automatically by the dispatcher from the request headers
        and authentication middleware.

        Usage:
            state = self.session.state          # constitution-state
            user = self.session.user            # authenticated user dict
        """
        return get_session()

    @property
    def current_user(self) -> Optional[Dict[str, Any]]:
        """
        Current authenticated user or None if not authenticated

        This property is populated by the authentication middleware
        when AUTHORIZATION is 'user' or 'full'.

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
    
    # Lo que una página puede pedir. El máximo no es una opinión: es lo que una
    # respuesta de lambda aguanta sin que el navegador se atragante.
    DEFAULT_PAGE_SIZE = 50
    MAX_PAGE_SIZE = 200

    def page_bounds(self) -> Tuple[int, int]:
        """Qué pedazo pidieron, acotado a algo que se pueda servir.

        Sale de `page` y `size` de la query, que llegan como texto. Un valor que
        no es un número, o que no tiene sentido, cae al default en vez de fallar:
        un listado que devuelve 400 porque alguien escribió `page=abc` en la URL
        es un listado roto por nada.
        """
        page = max(1, _positive(self.data.get('page')) or 1)
        size = _positive(self.data.get('size')) or self.DEFAULT_PAGE_SIZE
        size = min(self.MAX_PAGE_SIZE, max(1, size))
        return (page - 1) * size, size

    def paged(
        self, items: List[Any], total: int, key: str = 'items'
    ) -> Dict[str, Any]:
        """The body of a paged listing.

        The total travels with the page because without it a panel cannot draw a
        paginator, and whoever is looking cannot tell ten of twelve from ten of a
        million.

        `key` names the list so an endpoint can keep answering `users` or
        `regions` instead of a generic `items`; what a listing is called is part
        of how it reads.
        """
        _, size = self.page_bounds()
        page = max(1, _positive(self.data.get('page')) or 1)
        return {
            key: items,
            'page': page,
            'size': size,
            'total': total,
            'pages': (total + size - 1) // size if size else 0,
        }

    async def granted_permissions(self):
        """Which permissions the caller holds, or None when this API does not know.

        By default they come from the token: core signs them in, so a service
        authorizes on its own without asking anybody. That is the whole point —
        a service that had to call core on every request would put core back in
        the read path of the entire platform.

        Override it where the list comes from somewhere else. Core does: it holds
        the roles, so it reads them rather than trusting a claim it just signed.

        Returning None with AUTHORIZATION=permission is refused, not waved
        through. An endpoint that cannot say what its caller may do has to be a
        closed door: the alternative is that forgetting to wire this up leaves it
        open to anyone holding a token, which is the failure this whole mechanism
        exists to prevent.

        A token with no `permissions` claim yields an empty list, not None: it is
        a caller who may do nothing, which is different from an endpoint that
        cannot tell.
        """
        auth = self.auth_data or {}

        # La marca de dev y el token maestro responden por todo: son la forma de
        # entrar cuando una configuración de permisos quedó mal.
        if auth.get('is_bypass') or (auth.get('user') or {}).get('is_dev') is True:
            from ..permissions import ALL
            return [ALL]

        claims = auth.get('token_data')
        if not isinstance(claims, dict):
            return None

        granted = claims.get('permissions')
        return list(granted) if isinstance(granted, list) else []

    @property
    def service_code(self) -> str:
        """Names this service inside a permission, as in `core:GET /users`.

        Resolved by the same function the catalog uses, so the name a permission
        is stored under and the name it is demanded by cannot drift.
        """
        from ..permissions import service_code

        return service_code()

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
    
    @property
    def public(self) -> bool:
        """
        Whether this endpoint answers without a token.

        Declared here, next to the code, so the permission catalog can leave it
        out: a permission for something nobody needs permission for is noise in
        every role screen, and an administrator ticking it would be granting
        nothing.

        This does not make an endpoint public — terraform does, by leaving
        `authorization` unset on its lambda. This says so, so the rest of the
        framework can act on it.

            class AuthLoginAPI(API):
                @property
                def public(self):
                    return True
        """
        return False

    @property
    def schema(self):
        """
        Optional Pydantic model class for automatic request validation.

        Override this property to return a BaseModel subclass.
        The dispatcher will validate self.data against it before calling validate(),
        replace self.data with the coerced model output, and return 400 on failure.

        Example:
            @property
            def schema(self):
                return MyRequestSchema
        """
        return None

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

