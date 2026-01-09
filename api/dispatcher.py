"""
Dispatcher - Orquesta el flujo de ejecución de las APIs
"""

from typing import Dict, Any
import logging
import json

from .fetcher import Fetcher
from .base import API

logger = logging.getLogger(__name__)


class Dispatcher:
    """
    Orquesta la ejecución del API
    
    Dispatcher que maneja el ciclo de vida completo:
    1. Prepara el controlador (carga dinámicamente)
    2. Inyecta propiedades del request
    3. Ejecuta validate()
    4. Ejecuta process()
    5. Retorna la respuesta
    """
    
    def __init__(self, event: Dict[str, Any]):
        """
        Inicializa el dispatcher con un evento de API Gateway
        
        Args:
            event: Evento de AWS API Gateway
        """
        # Extraer información del evento
        self.endpoint = event.get('path', '').strip('/')
        self.method = event.get('httpMethod', 'GET').lower()
        self.headers = event.get('headers') or {}
        self.query_params = event.get('queryStringParameters') or {}
        
        # Extraer body
        raw_body = event.get('body', '{}')
        if isinstance(raw_body, str):
            try:
                self.body = json.loads(raw_body) if raw_body else {}
            except json.JSONDecodeError:
                self.body = {}
        else:
            self.body = raw_body
        
        # Para GET, los datos vienen en query params
        # Para POST/PUT/PATCH, vienen en body
        if self.method == 'get':
            self.data = self.query_params
        else:
            self.data = self.body
        
        logger.info(f"Dispatcher initialized: {self.method.upper()} /{self.endpoint}")
    
    async def dispatch(self) -> Dict[str, Any]:
        """
        Ejecuta el ciclo de vida completo del API
        
        Returns:
            Dict con code, body y headers de la respuesta
        """
        try:
            # 1. Preparar - Cargar controlador e inyectar propiedades
            api = self._prepare()
            
            # 2. Validar
            logger.debug("Executing validate()")
            await api.validate()
            
            # 3. Procesar
            logger.debug("Executing process()")
            await api.process()
            
            # 4. Si no se estableció código, usar 200 por defecto
            if api.response['code'] is None:
                api.set_code(200)
            
            logger.info(f"Request completed successfully with code {api.response['code']}")
            return api.response
            
        except FileNotFoundError as e:
            # API no encontrada
            logger.error(f"API not found: {e}")
            return {
                'code': 404,
                'body': {
                    'error': 'Not Found',
                    'message': str(e)
                },
                'headers': {}
            }
        
        except ValueError as e:
            # Error de validación
            logger.error(f"Validation error: {e}")
            return {
                'code': 400,
                'body': {
                    'error': 'Bad Request',
                    'message': str(e)
                },
                'headers': {}
            }
        
        except Exception as e:
            # Error interno
            logger.exception(f"Internal error: {e}")
            return {
                'code': 500,
                'body': {
                    'error': 'Internal Server Error',
                    'message': str(e)
                },
                'headers': {}
            }
    
    def _prepare(self) -> API:
        """
        Carga el controlador e inyecta propiedades
        
        Returns:
            Instancia del controlador con propiedades inyectadas
        
        Raises:
            FileNotFoundError: Si no encuentra el controlador
            ValueError: Si el controlador no es válido
        """
        logger.debug(f"Preparing controller for {self.endpoint}")
        
        # Crear fetcher y obtener controlador
        fetcher = Fetcher(self.endpoint, self.method)
        api = fetcher.get_controller()
        
        # Inyectar propiedades del request
        api.endpoint = self.endpoint
        api.http_method = self.method
        api.data = self.data
        api.headers = self.headers
        api.path_parameters = fetcher.path_parameters
        api.query_parameters = self.query_params
        
        logger.debug(f"Controller prepared: {api.__class__.__name__}")
        logger.debug(f"Path parameters: {api.path_parameters}")
        
        return api

