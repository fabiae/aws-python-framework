"""
Fetcher - Carga dinámica de controladores API basado en endpoint y método HTTP
"""

import os
import importlib.util
from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class Fetcher:
    """
    Carga dinámica de controladores API
    
    Fetcher del framework, determina qué archivo cargar basándose
    en el endpoint y método HTTP usando convención sobre configuración.
    
    Ejemplos:
        GET /users        -> api/users/list.py
        GET /users/123    -> api/users/get.py
        POST /users       -> api/users/post.py
        PUT /users/123    -> api/users/put.py
        DELETE /users/123 -> api/users/delete.py
    """
    
    API_FOLDER = "api"
    _cache = {}
    
    def __init__(self, endpoint: str, method: str):
        """
        Inicializa el fetcher
        
        Args:
            endpoint: El endpoint de la API (ej: 'users' o 'users/123/posts')
            method: El método HTTP (get, post, put, delete, etc.)
        """
        self.endpoint = endpoint.strip('/')
        self.method = method.lower()
    
    @property
    def file_path(self) -> str:
        """
        Calcula la ruta del archivo basado en endpoint y método
        
        Lógica:
        - Split endpoint por '/'
        - Si método es GET y hay cantidad impar de partes -> 'list'
        - Si método es GET y hay cantidad par de partes -> 'get'
        - Otros métodos usan su nombre directo
        - Solo las partes en índices pares (0,2,4...) son directorios
        
        Returns:
            Ruta absoluta al archivo del controlador
        """
        url_parts = self.endpoint.split('/') if self.endpoint else []
        
        # Determinar el nombre del método
        if self.method == 'get' and len(url_parts) % 2 == 1:
            method_name = 'list'
        else:
            method_name = self.method
        
        # Solo partes pares son directorios (0, 2, 4...)
        # Las impares son IDs de recursos
        dir_parts = [url_parts[i] for i in range(0, len(url_parts), 2)]
        file_dir = '/'.join(dir_parts) if dir_parts else ''
        
        # Construir ruta completa
        base_path = Path(os.getcwd()) / self.API_FOLDER
        file_path = base_path / file_dir / f"{method_name}.py"
        
        logger.debug(f"Resolved path: {file_path} for endpoint={self.endpoint}, method={self.method}")
        
        return str(file_path)
    
    @property
    def path_parameters(self) -> List[str]:
        """
        Extrae path parameters del endpoint
        
        Los path parameters son las partes en índices impares (1,3,5...)
        
        Ejemplos:
            'users/123' -> ['123']
            'users/123/posts/456' -> ['123', '456']
            'users' -> []
        
        Returns:
            Lista de path parameters
        """
        url_parts = self.endpoint.split('/') if self.endpoint else []
        return [url_parts[i] for i in range(1, len(url_parts), 2)]
    
    def get_controller(self):
        """
        Carga y retorna una instancia del controlador
        
        Usa caché para evitar cargar el mismo módulo múltiples veces.
        Busca una clase que herede de API en el módulo.
        
        Returns:
            Instancia del controlador API
        
        Raises:
            FileNotFoundError: Si no existe el archivo
            ValueError: Si no encuentra una clase API válida en el archivo
        """
        file_path = self.file_path
        
        # Verificar caché
        if file_path in self._cache:
            logger.debug(f"Using cached controller: {file_path}")
            return self._cache[file_path]()
        
        # Verificar que el archivo existe
        if not os.path.exists(file_path):
            raise FileNotFoundError(
                f"API Controller not found: {file_path}\n"
                f"Expected file for endpoint '{self.endpoint}' with method '{self.method}'"
            )
        
        # Cargar módulo dinámicamente
        spec = importlib.util.spec_from_file_location("api_module", file_path)
        if not spec or not spec.loader:
            raise ImportError(f"Could not load module spec from: {file_path}")
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Buscar clase que herede de API
        controller_class = None
        for item_name in dir(module):
            item = getattr(module, item_name)
            if (isinstance(item, type) and 
                hasattr(item, 'process') and 
                item.__name__ not in ['API', 'ABC']):
                controller_class = item
                break
        
        if not controller_class:
            raise ValueError(
                f"No API class found in {file_path}\n"
                f"Make sure your file exports a class that inherits from API"
            )
        
        # Cachear la clase (no la instancia)
        self._cache[file_path] = controller_class
        logger.info(f"Loaded controller: {controller_class.__name__} from {file_path}")
        
        # Retornar nueva instancia
        return controller_class()

