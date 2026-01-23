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
        db_name = os.getenv('AUTH_DB_NAME')
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
        
        logger.info(f"Token validated successfully for user {user_data.get('email')}")
        
        return {
            'user_id': str(token_doc['user_id']),
            'user': user_data,
            'token_data': token_doc,
            'is_bypass': False
        }
