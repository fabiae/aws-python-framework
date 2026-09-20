"""
Auth Validators - Validators for different authentication strategies
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import os
import logging
from datetime import datetime
from .exceptions import UnauthorizedError
from ..database.mongo_manager import MongoManager

logger = logging.getLogger(__name__)


class AuthValidator(ABC):
    """
    Abstract base class for authentication validators
    
    Each validator implements a different strategy to validate tokens.
    """
    
    @abstractmethod
    async def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate a token and return user information
        
        Args:
            token: The authentication token to validate
        
        Returns:
            Dict with user information: {'user_id': ..., 'user': {...}, ...}
        
        Raises:
            UnauthorizedError: If token is invalid
        """
        raise NotImplementedError("Subclasses must implement validate_token()")


class TokenValidator(AuthValidator):
    """
    Validates authentication tokens
    
    Simple unified validator that:
    1. First checks if token matches AUTH_BYPASS_TOKEN (if set)
    2. If not bypass, searches token in MongoDB 'tokens' collection
    3. Validates token is not expired and is active
    4. Loads complete user data from 'users' collection
    5. Updates last_used_at timestamp for auditing
    """
    
    async def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate token against MongoDB or bypass token
        
        Args:
            token: The authentication token to validate
        
        Returns:
            Dict with user_id, user object, and token_data
        
        Raises:
            UnauthorizedError: If token is invalid or expired
        """
        
        # 1. Check bypass token first (for development/testing)
        bypass_token = os.getenv('AUTH_BYPASS_TOKEN')
        if bypass_token and token == bypass_token:
            logger.info("Bypass token used - skipping DB validation")
            return {
                'user_id': 'bypass',
                'user': {
                    'email': 'bypass@system',
                    'role': 'admin',
                    'name': 'Bypass User',
                    '_id': 'bypass'
                },
                'is_bypass': True,
                'token_data': None
            }
        
        # 2. Get database name from environment
        db_name = os.getenv('AUTH_DB_NAME') or 'core'
        if not db_name:
            raise ValueError(
                "AUTH_DB_NAME environment variable not set. "
                "This is required for MongoDB authentication."
            )
        
        # 3. Get database reference
        if not MongoManager.is_initialized():
            raise RuntimeError("MongoManager not initialized")
        
        db = MongoManager.get_database(db_name)
        
        # 4. Search for token in database
        token_doc = await db.tokens.find_one({
            'token': token,
            'is_active': True
        })
        
        if not token_doc:
            logger.warning(f"Token not found or inactive")
            raise UnauthorizedError("Invalid or revoked token")
        
        # 5. Check if token is expired
        if 'expires_at' in token_doc:
            if token_doc['expires_at'] < datetime.utcnow():
                logger.warning(f"Token expired at {token_doc['expires_at']}")
                raise UnauthorizedError("Token has expired")
        
        # 6. Load user from database
        user = await db.users.find_one({'_id': token_doc['user_id']})
        
        if not user:
            logger.error(f"User {token_doc['user_id']} not found for valid token")
            raise UnauthorizedError("User not found")
        
        # 7. Check if user is active
        if 'is_active' in user and not user['is_active']:
            logger.warning(f"User {user['_id']} is inactive")
            raise UnauthorizedError("User account is inactive")
        
        # 8. Update last_used_at for auditing
        try:
            await db.tokens.update_one(
                {'_id': token_doc['_id']},
                {'$set': {'last_used_at': datetime.utcnow()}}
            )
        except Exception as e:
            # Non-critical, just log
            logger.warning(f"Failed to update last_used_at: {e}")
        
        # 9. Return user data (remove password from response)
        user_data = dict(user)
        user_data.pop('password', None)  # Never return password
        
        return {
            'user_id': str(token_doc['user_id']),
            'user': user_data,
            'token_data': token_doc,
            'is_bypass': False
        }


class JWTValidator(AuthValidator):
    """
    Validates RS256 JWTs issued by constitution-core.

    Stateless: the signature and the claims are enough, so no database is
    touched. That is what lets any microservice authenticate a request without
    calling the issuer.

    Environment:
        JWT_PUBLIC_KEY: RSA public key in PEM, raw or base64-encoded.
        JWT_ISSUER: expected `iss`. Defaults to 'constitution-core'.
        JWT_AUDIENCE: expected `aud`. Only verified when set.
        AUTH_BYPASS_TOKEN: still honoured, same as TokenValidator.
    """

    _public_key_cache: Optional[str] = None

    @classmethod
    def _public_key(cls) -> str:
        """The configured public key, decoded once per container."""
        if cls._public_key_cache:
            return cls._public_key_cache

        raw = os.getenv('JWT_PUBLIC_KEY')
        if not raw:
            raise ValueError(
                "JWT_PUBLIC_KEY environment variable not set. "
                "Required when AUTH_STRATEGY=jwt."
            )

        key = raw.strip()
        if not key.startswith('-----BEGIN'):
            # PEMs are multi-line, so they travel base64-encoded in env vars.
            import base64
            key = base64.b64decode(key).decode('utf-8')

        cls._public_key_cache = key
        return key

    async def validate_token(self, token: str) -> Dict[str, Any]:
        bypass_token = os.getenv('AUTH_BYPASS_TOKEN')
        if bypass_token and token == bypass_token:
            logger.info("Bypass token used - skipping JWT validation")
            return {
                'user_id': 'bypass',
                'user': {
                    'email': 'bypass@system',
                    'role': 'admin',
                    'name': 'Bypass User',
                    '_id': 'bypass'
                },
                'is_bypass': True,
                'token_data': None
            }

        try:
            import jwt
        except ImportError as exc:
            raise RuntimeError(
                "PyJWT is required for AUTH_STRATEGY=jwt. Install aws-python-helper[jwt]."
            ) from exc

        audience = os.getenv('JWT_AUDIENCE')
        try:
            claims = jwt.decode(
                token,
                self._public_key(),
                algorithms=['RS256'],
                issuer=os.getenv('JWT_ISSUER', 'constitution-core'),
                audience=audience,
                options={'verify_aud': bool(audience)},
            )
        except jwt.ExpiredSignatureError:
            logger.warning("JWT expired")
            raise UnauthorizedError("Token has expired")
        except jwt.InvalidTokenError as exc:
            logger.warning("JWT rejected: %s", exc)
            raise UnauthorizedError("Invalid token")

        if not claims.get('sub'):
            raise UnauthorizedError("Invalid token")

        # Same shape TokenValidator returns, so nothing downstream changes.
        return {
            'user_id': str(claims['sub']),
            'user': {
                '_id': claims['sub'],
                'email': claims.get('email'),
                'name': claims.get('name', ''),
                'role': claims.get('role', 'user'),
                **(claims.get('extra') or {}),
            },
            'token_data': claims,
            'is_bypass': False,
        }


def get_auth_validator() -> AuthValidator:
    """The validator this service is configured to use.

    AUTH_STRATEGY=jwt switches to stateless validation. Anything else keeps the
    database lookup, so a service only migrates when its environment says so.
    """
    strategy = (os.getenv('AUTH_STRATEGY') or 'db').strip().lower()
    if strategy == 'jwt':
        return JWTValidator()
    return TokenValidator()
