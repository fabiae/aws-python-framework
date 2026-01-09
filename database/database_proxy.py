"""
Database Proxy - Proxy to dynamically access multiple databases
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class DatabaseProxy:
    """
    Proxy to dynamically access multiple databases and collections in MongoDB
    
    This proxy allows accessing multiple databases and collections
    dynamically and pythonically, without the need to define models.
    """
    
    def __init__(self, mongo_manager):
        """
        Initialize the proxy
        
        Args:
            mongo_manager: MongoManager class (not an instance)
        """
        self._manager = mongo_manager
        self._db_cache = {}
    
    def __getattr__(self, db_name: str) -> Any:
        """
        Dynamic access to databases
        
        It is called when you access self.db.database_name
        
        Args:
            db_name: Name of the database
        
        Returns:
            Reference to the database of Motor
        """
        # Avoid recursion with internal attributes
        if db_name.startswith('_'):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{db_name}'")
        
        if db_name not in self._db_cache:
            logger.debug(f"DatabaseProxy: accessing database '{db_name}'")
            self._db_cache[db_name] = self._manager.get_database(db_name)
        
        return self._db_cache[db_name]
    
    def __repr__(self) -> str:
        """String representation of the proxy"""
        cached_dbs = list(self._db_cache.keys())
        return f"<DatabaseProxy cached_dbs={cached_dbs}>"

