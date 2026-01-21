"""
MongoDB JSON Encoder - Custom JSON encoder to handle MongoDB types
"""

import json
from datetime import datetime, date
from decimal import Decimal
from typing import Any

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


class MongoJSONEncoder(json.JSONEncoder):
    """
    Custom JSON Encoder that handles MongoDB types
    
    Automatically converts:
    - ObjectId -> string
    - datetime -> ISO 8601 string
    - date -> ISO 8601 string
    - Decimal128 -> float
    - Decimal -> float
    - Binary -> base64 string
    - UUID -> string
    - bytes -> base64 string
    - set -> list
    
    Usage:
        json.dumps(data, cls=MongoJSONEncoder)
    """
    
    def default(self, obj: Any) -> Any:
        """
        Convert MongoDB types to JSON-serializable types
        
        Args:
            obj: Object to convert
            
        Returns:
            JSON-serializable representation of the object
        """
        if BSON_AVAILABLE:
            # MongoDB ObjectId
            if isinstance(obj, ObjectId):
                return str(obj)
            
            # MongoDB Decimal128
            if isinstance(obj, Decimal128):
                return float(obj.to_decimal())
            
            # MongoDB Binary
            if isinstance(obj, Binary):
                import base64
                return base64.b64encode(bytes(obj)).decode('utf-8')
            
            # UUID
            if isinstance(obj, UUID):
                return str(obj)
        
        # Python datetime
        if isinstance(obj, datetime):
            return obj.isoformat()
        
        # Python date
        if isinstance(obj, date):
            return obj.isoformat()
        
        # Python Decimal
        if isinstance(obj, Decimal):
            return float(obj)
        
        # Python bytes
        if isinstance(obj, bytes):
            import base64
            return base64.b64encode(obj).decode('utf-8')
        
        # Python set
        if isinstance(obj, set):
            return list(obj)
        
        # Default behavior for other types
        return super().default(obj)


def mongo_json_dumps(obj: Any, **kwargs) -> str:
    """
    Helper function to serialize objects with MongoDB types to JSON
    
    Args:
        obj: Object to serialize
        **kwargs: Additional arguments for json.dumps
        
    Returns:
        JSON string
        
    Example:
        result = mongo_json_dumps({'_id': ObjectId('...'), 'name': 'John'})
    """
    return json.dumps(obj, cls=MongoJSONEncoder, **kwargs)
