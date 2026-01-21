"""
MongoDB Serializer - Utility to convert MongoDB types to JSON-serializable types
"""

from typing import Any
from datetime import datetime, date
from decimal import Decimal

try:
    from bson import ObjectId, Decimal128, Binary
    from uuid import UUID
    BSON_AVAILABLE = True
except ImportError:
    BSON_AVAILABLE = False
    ObjectId = None
    Decimal128 = None
    Binary = None
    UUID = None


def serialize_mongo_types(obj: Any) -> Any:
    """
    Recursively convert MongoDB types to JSON-serializable Python types
    
    This function walks through the entire object structure (dicts, lists, tuples, sets)
    and converts any MongoDB-specific types to standard Python types that can be
    serialized to JSON.
    
    Conversions:
    - ObjectId -> string
    - datetime -> ISO 8601 string
    - date -> ISO 8601 string
    - Decimal128 -> float
    - Decimal -> float
    - Binary -> base64 string
    - UUID -> string
    - bytes -> base64 string
    - set -> list
    - tuple -> list
    
    Args:
        obj: Object to serialize (can be dict, list, or any type)
        
    Returns:
        Object with all MongoDB types converted to JSON-serializable types
        
    Example:
        >>> from bson import ObjectId
        >>> data = {'_id': ObjectId('507f1f77bcf86cd799439011'), 'name': 'John'}
        >>> result = serialize_mongo_types(data)
        >>> result
        {'_id': '507f1f77bcf86cd799439011', 'name': 'John'}
    """
    # Handle None
    if obj is None:
        return None
    
    # Handle MongoDB types
    if BSON_AVAILABLE:
        if isinstance(obj, ObjectId):
            return str(obj)
        
        if isinstance(obj, Decimal128):
            return float(obj.to_decimal())
        
        if isinstance(obj, Binary):
            import base64
            return base64.b64encode(bytes(obj)).decode('utf-8')
        
        if isinstance(obj, UUID):
            return str(obj)
    
    # Handle Python datetime types
    if isinstance(obj, datetime):
        return obj.isoformat()
    
    if isinstance(obj, date):
        return obj.isoformat()
    
    # Handle Python Decimal
    if isinstance(obj, Decimal):
        return float(obj)
    
    # Handle Python bytes
    if isinstance(obj, bytes):
        import base64
        return base64.b64encode(obj).decode('utf-8')
    
    # Handle collections recursively
    if isinstance(obj, dict):
        return {key: serialize_mongo_types(value) for key, value in obj.items()}
    
    if isinstance(obj, list):
        return [serialize_mongo_types(item) for item in obj]
    
    if isinstance(obj, tuple):
        return [serialize_mongo_types(item) for item in obj]
    
    if isinstance(obj, set):
        return [serialize_mongo_types(item) for item in obj]
    
    # Return as-is for other types (str, int, float, bool, etc.)
    return obj
