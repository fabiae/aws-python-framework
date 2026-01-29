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
from .auth_validators import TokenValidator

logger = logging.getLogger(__name__)


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
            
            # 2. Authenticate (if required)
            require_auth = os.getenv('REQUIRE_AUTH', 'false').lower() == 'true'
            if require_auth:
                await self._authenticate(api)
            
            # 3. Validate
            await api.validate()
            
            # 4. Process
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
    
    async def _authenticate(self, api: API):
        """
        Execute authentication middleware
        
        Uses TokenValidator to validate tokens against AUTH_BYPASS_TOKEN
        or MongoDB database.
        
        Args:
            api: API instance to inject authentication data into
        
        Raises:
            UnauthorizedError: If authentication fails
        """
        # Use unified token validator
        validator = TokenValidator()
        
        # Create middleware and authenticate
        middleware = AuthMiddleware(validator)
        await middleware.authenticate(self.headers, api)

