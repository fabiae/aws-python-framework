"""
Dispatcher - Orchestrates the execution flow of APIs
"""

from typing import Dict, Any
import logging
import json
import os

from .fetcher import Fetcher
from .base import API
from .exceptions import UnauthorizedError, ForbiddenError, AuthenticationError
from .auth_middleware import AuthMiddleware
from .auth_validators import get_auth_validator
from ..context.session import get_session
from ..context.state_validator import StateValidator, InvalidStateError

logger = logging.getLogger(__name__)


# Cómo se llama el header que dice qué estado se está mirando. Es un default y
# no un literal repartido: el nombre es parte del protocolo entre los servicios
# y el panel, así que cambiarlo es un cambio coordinado — pero tenerlo en un
# solo lugar hace que ese día sea una variable de entorno y no una búsqueda.
STATE_HEADER_DEFAULT = 'constitution-state'


def state_header() -> str:
    return os.getenv('STATE_HEADER', STATE_HEADER_DEFAULT)



class Dispatcher:
    """
    Orchestrates the execution of the API
    
    Dispatcher that handles the complete lifecycle:
    1. Prepares the controller (dynamically loads)
    2. Injects request properties
    3. Executes validate()
    4. Executes process()
    5. Returns the response
    """
    
    def __init__(self, event: Dict[str, Any]):
        """
        Initializes the dispatcher with an API Gateway event
        
        Args:
            event: AWS API Gateway event
        """
        # Extract information from the event
        # Support both API Gateway v1.0 (REST API) and v2.0 (HTTP API)
        self.endpoint = event.get('rawPath', event.get('path', '')).strip('/')
        
        # Extract HTTP method from v2.0 or v1.0 format
        http_context = event.get('requestContext', {}).get('http', {})
        self.method = http_context.get('method', event.get('httpMethod', 'GET')).lower()
        
        self.headers = event.get('headers') or {}
        self.query_params = event.get('queryStringParameters') or {}
        
        # Extract body
        raw_body = event.get('body', '{}')
        if isinstance(raw_body, str):
            try:
                self.body = json.loads(raw_body) if raw_body else {}
            except json.JSONDecodeError:
                self.body = {}
        else:
            self.body = raw_body
        
        # For GET, data comes in query params
        # For POST/PUT/PATCH, data comes in body
        if self.method == 'get':
            self.data = self.query_params
        else:
            self.data = self.body
    
    async def dispatch(self) -> Dict[str, Any]:
        """
        Executes the complete lifecycle of the API
        
        Returns:
            Dict with code, body and headers of the response
        """
        try:
            # 1. Prepare - Load controller and inject properties
            api = self._prepare()
            
            # 2. Authorization based on mode
            authorization = os.getenv('AUTHORIZATION', '').lower()
            requires_user = authorization in ('user', 'full', 'permission')
            requires_permission = authorization == 'permission'

            # Pedir el state es independiente de pedir un permiso, así que va por
            # su propia variable. Los valores viejos `state` y `full` la implican,
            # para que un servicio sin migrar siga comportándose igual.
            requires_state = (
                authorization in ('state', 'full')
                or os.getenv('REQUIRES_STATE', '').lower() in ('1', 'true', 'yes')
            )

            # 2a. Authenticate (if mode requires user)
            if requires_user:
                await self._authenticate(api)

            # 2a-bis. Check what the caller is allowed to do
            if requires_permission:
                denial = await self._authorize(api)
                if denial:
                    return denial

            # 2b. Validate state header (if mode requires state)
            if requires_state:
                state = self.headers.get(state_header())
                if not state:
                    return {
                        'code': 400,
                        'body': {
                            'error': 'Bad Request',
                            'message': f"Header '{state_header()}' is required"
                        },
                        'headers': {}
                    }
                try:
                    await StateValidator.validate(state)
                except InvalidStateError as e:
                    return {
                        'code': 403,
                        'body': {
                            'error': 'Forbidden',
                            'message': str(e)
                        },
                        'headers': {}
                    }
                session = get_session()
                session.state = state

            # 2c. Inject user into session (if authenticated)
            if api._current_user:
                session = get_session()
                session.user = api._current_user

            # 3. Schema validation (automatic, if schema property is defined)
            if api.schema is not None:
                try:
                    validated = api.schema(**api.data)
                    api.data = validated.model_dump()
                except Exception as e:
                    raise ValueError(str(e))

            # 4. Validate
            await api.validate()

            # 5. Process
            await api.process()
            
            # 5. If no code was set, use 200 by default
            if api.response['code'] is None:
                api.set_code(200)
            
            return api.response
            
        except FileNotFoundError as e:
            # API not found
            logger.error(f"API not found: {e}")
            return {
                'code': 404,
                'body': {
                    'error': 'Not Found',
                    'message': str(e)
                },
                'headers': {}
            }
        
        except ValueError as e:
            # Validation error
            logger.error(f"Validation error: {e}")
            return {
                'code': 400,
                'body': {
                    'error': 'Bad Request',
                    'message': str(e)
                },
                'headers': {}
            }
        
        except Exception as e:
            # Check if it's an authentication error
            
            if isinstance(e, UnauthorizedError):
                # 401 Unauthorized
                logger.warning(f"Unauthorized: {e}")
                return {
                    'code': 401,
                    'body': {
                        'error': 'Unauthorized',
                        'message': str(e)
                    },
                    'headers': {}
                }
            
            elif isinstance(e, ForbiddenError):
                # 403 Forbidden
                logger.warning(f"Forbidden: {e}")
                return {
                    'code': 403,
                    'body': {
                        'error': 'Forbidden',
                        'message': str(e)
                    },
                    'headers': {}
                }
            
            elif isinstance(e, AuthenticationError):
                # Generic auth error - 401
                logger.warning(f"Authentication error: {e}")
                return {
                    'code': 401,
                    'body': {
                        'error': 'Unauthorized',
                        'message': str(e)
                    },
                    'headers': {}
                }
            
            # Internal error
            logger.exception(f"Internal error: {e}")
            return {
                'code': 500,
                'body': {
                    'error': 'Internal Server Error',
                    'message': str(e)
                },
                'headers': {}
            }
    
    def _prepare(self) -> API:
        """
        Load the controller and inject properties
        
        Returns:
            Instance of the controller with properties injected
        
        Raises:
            FileNotFoundError: If the controller is not found
            ValueError: If the controller is not valid
        """
        
        # Create fetcher and get controller
        fetcher = Fetcher(self.endpoint, self.method)
        api = fetcher.get_controller()
        
        # Inject request properties
        api.endpoint = self.endpoint
        api.http_method = self.method
        api.data = self.data
        api.headers = self.headers
        api.path_parameters = fetcher.path_parameters
        api.query_parameters = self.query_params
        
        return api
    
    async def _authorize(self, api: API):
        """Refuse the request when the caller lacks the permission it needs.

        Returns the response to send back, or None to carry on.
        """
        from ..permissions import allows, required_for

        granted = await api.granted_permissions()
        if granted is None:
            logger.error(
                "AUTHORIZATION=permission but %s does not implement "
                "granted_permissions(); refusing the request",
                type(api).__name__,
            )
            return {
                'code': 403,
                'body': {
                    'error': 'Forbidden',
                    'message': 'Permission checking is not configured for this endpoint',
                },
                'headers': {},
            }

        required = required_for(api.service_code, self.method, self.endpoint)
        if allows(granted, required):
            return None

        logger.warning("Denied: %s lacks %r", self.headers.get('x-caller', 'caller'), required)
        return {
            'code': 403,
            'body': {
                'error': 'Forbidden',
                'message': f"Te falta el permiso '{required}'",
            },
            'headers': {},
        }

    async def _authenticate(self, api: API):
        """
        Execute authentication middleware
        
        The validator is chosen by AUTH_STRATEGY: stateless JWT, or the
        database lookup used so far.
        
        Args:
            api: API instance to inject authentication data into
        
        Raises:
            UnauthorizedError: If authentication fails
        """
        # Strategy comes from configuration, per service
        validator = get_auth_validator()
        
        # Create middleware and authenticate
        middleware = AuthMiddleware(validator)
        await middleware.authenticate(self.headers, api)

