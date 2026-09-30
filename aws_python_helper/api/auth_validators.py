"""
Auth Validators - Validators for different authentication strategies
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import os
import logging
from datetime import datetime
# Quién firma los tokens que este servicio verifica. Es un default histórico y
# no un nombre que el framework imponga: el `iss` de un token ya emitido no se
# puede cambiar sin invalidarlo, así que se configura con JWT_ISSUER y esto
# queda como el valor que venía de antes.
ISSUER_DEFAULT = 'constitution-core'

from . import jwt_keys
from .exceptions import UnauthorizedError
from ..database.mongo_manager import MongoManager

logger = logging.getLogger(__name__)


def _machine_caller(token: str) -> Optional[Dict[str, Any]]:
    """Quién es, cuando quien llama no es una persona.

    Dos tokens distintos, porque son dos cosas distintas y confundirlas deja una
    puerta abierta más ancha de lo que nadie quiso:

    - `INTER_SERVICE_TOKEN` dice **"soy un microservicio de los nuestros"**. Es
      lo que un servicio manda cuando le habla a otro. No es un usuario y no
      tiene permisos de nadie: un endpoint que lo acepta lo dice explícitamente.
    - `AUTH_BYPASS_TOKEN` es la **llave maestra**, la forma de entrar cuando una
      configuración de permisos quedó mal. Abre todo, y por eso no debería ser la
      que un servicio usa todos los días.

    Devuelve None si el token no es ninguno de los dos, y entonces se valida como
    lo que es: el token de una persona.
    """
    service_token = os.getenv('INTER_SERVICE_TOKEN')
    if service_token and token == service_token:
        logger.info("Inter-service token used")
        return {
            'user_id': 'service',
            'user': {
                '_id': 'service',
                'email': 'service@system',
                'name': 'Service',
                'role': 'service',
            },
            'is_service': True,
            'is_bypass': False,
            'token_data': None,
        }

    bypass_token = os.getenv('AUTH_BYPASS_TOKEN')
    if bypass_token and token == bypass_token:
        logger.info("Bypass token used - skipping validation")
        return {
            'user_id': 'bypass',
            'user': {
                '_id': 'bypass',
                'email': 'bypass@system',
                'name': 'Bypass User',
                'role': 'admin',
            },
            'is_bypass': True,
            'token_data': None,
        }

    return None


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
        
        # 1. Quien llama puede no ser una persona: un servicio o la llave maestra.
        caller = _machine_caller(token)
        if caller:
            return caller

        
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
    Validates RS256 JWTs issued by the identity service.

    Stateless: the signature and the claims are enough, so no database is
    touched. That is what lets any microservice authenticate a request without
    calling the issuer.

    The key comes from core, which publishes it: see `jwt_keys`. A service that
    pins JWT_PUBLIC_KEY uses that instead and never calls out.

    Environment:
        CORE_API_URL: where core answers. How the key is found.
        JWT_PUBLIC_KEY: pins the key instead of reading it from core.
        JWT_ISSUER: expected `iss`. Must match what the issuer signs.
        JWT_AUDIENCE: expected `aud`. Only verified when set.
        AUTH_BYPASS_TOKEN: still honoured, same as TokenValidator.
    """

    async def validate_token(self, token: str) -> Dict[str, Any]:
        caller = _machine_caller(token)
        if caller:
            return caller

        try:
            import jwt
        except ImportError as exc:
            raise RuntimeError(
                "PyJWT is required for AUTH_STRATEGY=jwt. Install aws-python-helper[jwt]."
            ) from exc

        # El kid del header dice con qué clave se firmó. Es dato sin verificar y
        # sólo se usa para elegir la clave: la firma se comprueba igual, así que
        # un kid mentido no abre nada, simplemente no encuentra clave.
        try:
            kid = jwt.get_unverified_header(token).get('kid')
        except jwt.InvalidTokenError:
            raise UnauthorizedError("Invalid token")

        try:
            key = await jwt_keys.resolve(kid)
        except ValueError as exc:
            logger.error("Cannot verify tokens: %s", exc)
            raise

        audience = os.getenv('JWT_AUDIENCE')
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=['RS256'],
                issuer=os.getenv('JWT_ISSUER', ISSUER_DEFAULT),
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
