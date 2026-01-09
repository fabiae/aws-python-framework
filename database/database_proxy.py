"""
Database Proxy - Proxy para acceso dinámico a múltiples bases de datos
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class DatabaseProxy:
    """
    Proxy para acceso dinámico a bases de datos y colecciones MongoDB
    
    Este proxy permite acceder a múltiples bases de datos y colecciones
    de forma dinámica y pythónica, sin necesidad de definir models.
    
    Framework de acceso directo a las bases de datos y colecciones para mayor flexibilidad.
    
    Uso:
        # Acceder a diferentes bases de datos
        users = await self.db.users_db.users.find().to_list(100)
        
        # Otra base de datos
        logs = await self.db.analytics_db.logs.insert_one({...})
        
        # Múltiples colecciones en la misma DB
        titles = await self.db.constitution_db.titles.find_one({...})
        articles = await self.db.constitution_db.articles.find({...})
    
    Ventajas:
        - Acceso a múltiples bases de datos sin configuración
        - No necesitas definir Models
        - Syntax pythónico y claro
        - Toda la potencia de Motor/PyMongo
    """
    
    def __init__(self, mongo_manager):
        """
        Inicializa el proxy
        
        Args:
            mongo_manager: Clase MongoManager (no instancia)
        """
        self._manager = mongo_manager
        self._db_cache = {}
    
    def __getattr__(self, db_name: str) -> Any:
        """
        Acceso dinámico a bases de datos
        
        Se llama cuando accedes a self.db.nombre_base_datos
        
        Args:
            db_name: Nombre de la base de datos
        
        Returns:
            Referencia a la base de datos de Motor
        """
        # Evitar recursión con atributos internos
        if db_name.startswith('_'):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{db_name}'")
        
        if db_name not in self._db_cache:
            logger.debug(f"DatabaseProxy: accessing database '{db_name}'")
            self._db_cache[db_name] = self._manager.get_database(db_name)
        
        return self._db_cache[db_name]
    
    def __repr__(self) -> str:
        """Representación string del proxy"""
        cached_dbs = list(self._db_cache.keys())
        return f"<DatabaseProxy cached_dbs={cached_dbs}>"

