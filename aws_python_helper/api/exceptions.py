"""
Authentication Exceptions - Custom exceptions for authentication errors
"""


class AuthenticationError(Exception):
    """
    Base exception for authentication-related errors
    
    This is the parent class for all authentication exceptions.
    Can be used to catch any authentication error.
    """
    pass


class UnauthorizedError(AuthenticationError):
    """
    Raised when token is missing or invalid
    
    This should return HTTP 401 Unauthorized response.
    
    Examples:
        - Missing Authorization header
        - Invalid token format
        - Token not found in database
        - Token expired
        - Token revoked
    """
    pass


class ForbiddenError(AuthenticationError):
    """
    Raised when user doesn't have required permissions
    
    This should return HTTP 403 Forbidden response.
    
    Examples:
        - User authenticated but doesn't have access to resource
        - User role doesn't allow the operation
        - User account is inactive
    """
    pass
