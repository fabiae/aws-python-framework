"""
SQS Consumer Base - Clase base para todos los consumers de SQS
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
import logging
import json


class SQSConsumer(ABC):
    """
    Clase base para consumers de SQS
    
    Similar al IterativeSQSConsumer de Janis, proporciona estructura
    para procesar mensajes de SQS de forma batch o individual.
    
    Ejemplo de uso:
        class UserCreatedConsumer(SQSConsumer):
            async def process_record(self, record):
                user_id = record['body']['userId']
                await self.send_welcome_email(user_id)
    """
    
    def __init__(self):
        """Inicializa el consumer con un logger"""
        self.logger = logging.getLogger(self.__class__.__name__)
        self._db = None
    
    @property
    def db(self):
        """
        Acceso a bases de datos MongoDB
        
        Uso:
            result = await self.db.users_db.users.find_one({'_id': user_id})
        """
        if self._db is None:
            from lambda_framework.database.mongo_manager import MongoManager
            from lambda_framework.database.database_proxy import DatabaseProxy
            self._db = DatabaseProxy(MongoManager)
        return self._db
    
    @abstractmethod
    async def process_record(self, record: Dict[str, Any]):
        """
        Procesa un registro individual de SQS
        
        Args:
            record: Registro de SQS con 'body', 'messageId', etc.
        
        Raises:
            Exception: Cualquier error en el procesamiento
        """
        raise NotImplementedError("Debes implementar process_record()")
    
    def parse_body(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parsea el body del mensaje SQS
        
        Args:
            record: Registro de SQS
        
        Returns:
            Body parseado como dict
        """
        body = record.get('body', '{}')
        
        if isinstance(body, str):
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                self.logger.warning(f"Could not parse body as JSON: {body}")
                return {'raw': body}
        
        return body
    
    async def process_batch(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Procesa un batch de registros de SQS
        
        Args:
            records: Lista de registros de SQS
        
        Returns:
            Lista de resultados con éxito/error de cada registro
        """
        results = []
        
        for i, record in enumerate(records):
            message_id = record.get('messageId', f'record-{i}')
            
            try:
                self.logger.info(f"Processing message: {message_id}")
                await self.process_record(record)
                results.append({
                    'messageId': message_id,
                    'success': True
                })
                self.logger.info(f"Successfully processed message: {message_id}")
                
            except Exception as e:
                self.logger.error(
                    f"Error processing message {message_id}: {e}",
                    exc_info=True
                )
                results.append({
                    'messageId': message_id,
                    'success': False,
                    'error': str(e)
                })
        
        # Log resumen
        success_count = sum(1 for r in results if r['success'])
        self.logger.info(
            f"Batch processing complete: {success_count}/{len(records)} successful"
        )
        
        return results

