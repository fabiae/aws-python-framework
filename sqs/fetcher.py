"""
SQS Fetcher - Carga dinámica de consumers basado en nombre
"""

import os
import importlib.util
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class SQSFetcher:
    """
    Carga dinámica de consumers de SQS
    
    Similar al Fetcher de API pero para consumers de SQS.
    Busca consumers en la carpeta 'consumers/' por nombre.
    
    Ejemplo:
        'user-created' -> consumers/user_created.py -> UserCreatedConsumer
    """
    
    CONSUMERS_FOLDER = "consumers"
    _cache = {}
    
    def __init__(self, consumer_name: str):
        """
        Inicializa el fetcher
        
        Args:
            consumer_name: Nombre del consumer (ej: 'user-created')
        """
        self.consumer_name = consumer_name
    
    @property
    def file_path(self) -> str:
        """
        Calcula la ruta del archivo del consumer
        
        Convierte 'user-created' a 'user_created.py'
        
        Returns:
            Ruta absoluta al archivo del consumer
        """
        # Convertir guiones a guiones bajos para nombre de archivo Python
        file_name = self.consumer_name.replace('-', '_') + '.py'
        
        base_path = Path(os.getcwd()) / self.CONSUMERS_FOLDER
        file_path = base_path / file_name
        
        logger.debug(f"Resolved consumer path: {file_path}")
        
        return str(file_path)
    
    def get_consumer(self):
        """
        Carga y retorna una instancia del consumer
        
        Returns:
            Instancia del consumer
        
        Raises:
            FileNotFoundError: Si no existe el archivo
            ValueError: Si no encuentra una clase consumer válida
        """
        file_path = self.file_path
        
        # Verificar caché
        if file_path in self._cache:
            logger.debug(f"Using cached consumer: {file_path}")
            return self._cache[file_path]()
        
        # Verificar que el archivo existe
        if not os.path.exists(file_path):
            raise FileNotFoundError(
                f"Consumer not found: {file_path}\n"
                f"Expected file for consumer '{self.consumer_name}'"
            )
        
        # Cargar módulo dinámicamente
        spec = importlib.util.spec_from_file_location("consumer_module", file_path)
        if not spec or not spec.loader:
            raise ImportError(f"Could not load module spec from: {file_path}")
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Buscar clase que herede de SQSConsumer
        consumer_class = None
        for item_name in dir(module):
            item = getattr(module, item_name)
            if (isinstance(item, type) and 
                hasattr(item, 'process_record') and 
                item.__name__ not in ['SQSConsumer', 'ABC']):
                consumer_class = item
                break
        
        if not consumer_class:
            raise ValueError(
                f"No SQSConsumer class found in {file_path}\n"
                f"Make sure your file exports a class that inherits from SQSConsumer"
            )
        
        # Cachear la clase
        self._cache[file_path] = consumer_class
        logger.info(f"Loaded consumer: {consumer_class.__name__} from {file_path}")
        
        # Retornar nueva instancia
        return consumer_class()

