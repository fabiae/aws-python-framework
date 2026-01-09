"""
MongoDB Manager - Gestor de conexiones a múltiples bases de datos MongoDB
"""

from motor.motor_asyncio import AsyncIOMotorClient
from typing import Dict, Optional
import os
import logging

logger = logging.getLogger(__name__)


class MongoManager:
    """
    Gestor singleton de conexiones MongoDB
    
    Maneja la conexión a MongoDB y proporciona acceso a múltiples
    bases de datos desde una única conexión.
    
    Framework de acceso directo a las bases de datos y colecciones para mayor flexibilidad.
    
    Uso:
        # Inicializar una vez (en el handler)
        MongoManager.initialize('mongodb://localhost:27017')
        
        # Acceder a bases de datos
        db = MongoManager.get_database('users_db')
        users = await db.users.find().to_list(100)
    """
    
    _client: Optional[AsyncIOMotorClient] = None
    _databases: Dict[str, any] = {}
    _connection_string: Optional[str] = None
    
    @classmethod
    def initialize(cls, connection_string: str = None):
        """
        Inicializa la conexión a MongoDB
        
        Solo se conecta una vez. Llamadas subsecuentes no hacen nada.
        
        Args:
            connection_string: URI de conexión de MongoDB.
                              Si no se provee, usa la variable MONGODB_URI
        """
        if cls._client is not None:
            logger.debug("MongoManager already initialized")
            return
        
        conn_str = connection_string or os.getenv('MONGODB_URI')
        
        if not conn_str:
            raise ValueError(
                "MongoDB connection string not provided. "
                "Pass it to initialize() or set MONGODB_URI environment variable"
            )
        
        logger.info(f"Initializing MongoDB connection")
        cls._connection_string = conn_str
        cls._client = AsyncIOMotorClient(conn_str)
        logger.info("MongoDB connection initialized successfully")
    
    @classmethod
    def get_database(cls, db_name: str):
        """
        Obtiene referencia a una base de datos
        
        Las referencias se cachean para reutilización.
        
        Args:
            db_name: Nombre de la base de datos
        
        Returns:
            Objeto de base de datos de Motor
        
        Raises:
            RuntimeError: Si MongoManager no ha sido inicializado
        """
        if cls._client is None:
            raise RuntimeError(
                "MongoManager not initialized. "
                "Call MongoManager.initialize() first"
            )
        
        if db_name not in cls._databases:
            logger.debug(f"Creating database reference: {db_name}")
            cls._databases[db_name] = cls._client[db_name]
        
        return cls._databases[db_name]
    
    @classmethod
    def get_client(cls) -> Optional[AsyncIOMotorClient]:
        """
        Obtiene el cliente de MongoDB
        
        Returns:
            Cliente de Motor o None si no está inicializado
        """
        return cls._client
    
    @classmethod
    async def close(cls):
        """
        Cierra la conexión a MongoDB
        
        Útil para testing o cleanup.
        """
        if cls._client:
            logger.info("Closing MongoDB connection")
            cls._client.close()
            cls._client = None
            cls._databases = {}
            cls._connection_string = None
    
    @classmethod
    def is_initialized(cls) -> bool:
        """
        Verifica si el manager está inicializado
        
        Returns:
            True si está inicializado, False en caso contrario
        """
        return cls._client is not None
    
    @classmethod
    async def ping(cls) -> bool:
        """
        Verifica la conexión a MongoDB
        
        Returns:
            True si la conexión está activa, False en caso contrario
        """
        if not cls._client:
            return False
        
        try:
            await cls._client.admin.command('ping')
            return True
        except Exception as e:
            logger.error(f"MongoDB ping failed: {e}")
            return False

