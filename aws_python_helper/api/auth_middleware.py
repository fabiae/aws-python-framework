"""
Auth Middleware - Handles authentication for API requests
"""

from typing import Dict, Any
import logging

from .auth_validators import AuthValidator
from .exceptions import UnauthorizedError

logger = logging.getLogger(__name__)


class AuthMiddleware:
    """
    Middleware to handle authentication for API requests
    
    This middleware:
    1. Extracts token from Authorization header
    2. Validates token using configured validator
    3. Injects user information into API instance
    4. Raises UnauthorizedError if authentication fails
    """
    
    def __init__(self, validator: AuthValidator):
        """
        Initialize middleware with an auth validator
        
        Args:
            validator: AuthValidator instance to use for token validation
        """
        self.validator = validator
    
    def _extract_token(self, headers: Dict[str, str]) -> str:
        """
        Extract token from Authorization header
        
        Supports two formats:
        - Authorization: Bearer <token>
        - authorization: Bearer <token> (case insensitive)
        
        Args:
            headers: Request headers dictionary
        
        Returns:
            The extracted token string
        
        Raises:
            UnauthorizedError: If Authorization header is missing or invalid
        """
        # Try to get Authorization header (case-insensitive)
        auth_header = None
        for key, value in headers.items():
            if key.lower() == 'authorization':
                auth_header = value
                break
        
        if not auth_header:
            raise UnauthorizedError("Authorization header is required")
        
        # Check Bearer format
        if not auth_header.startswith('Bearer '):
            raise UnauthorizedError("Authorization header must use Bearer scheme")
        
        # Extract token
        token = auth_header.replace('Bearer ', '').strip()
        
        if not token:
            raise UnauthorizedError("Token cannot be empty")
        
        return token
    
    async def authenticate(self, headers: Dict[str, str], api: Any):
        """
        Authenticate the request and inject user data into API instance
        
        This method:
        1. Extracts token from headers
        2. Validates token using the configured validator
        3. Injects authentication data into the API instance
        
        Args:
            headers: Request headers dictionary
            api: API instance to inject authentication data into
        
        Raises:
            UnauthorizedError: If authentication fails
        """
        
        try:
            # 1. Extract token from headers
            token = self._extract_token(headers)
            
            # 2. Validate token
            auth_data = await self.validator.validate_token(token)
            
            # 3. Inject authentication data into API instance
            api._current_user = auth_data.get('user')
            api._auth_data = auth_data
            api._is_authenticated = True
        except UnauthorizedError:
            # Re-raise UnauthorizedError as is
            raise
        
        except Exception as e:
            # Catch any other error and convert to UnauthorizedError
            logger.error(f"Authentication error: {e}", exc_info=True)
            raise UnauthorizedError(f"Authentication failed: {str(e)}")
