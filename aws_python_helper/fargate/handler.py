"""
Fargate Handler - Entry point generic for Fargate tasks

Provides a reusable handler that loads tasks dynamically
and executes them, similar to the SQS handler pattern.
"""

import os
import sys
import asyncio
import logging
from typing import Any

from .fetcher import FargateTaskFetcher
from ..database.mongo_manager import MongoManager


def setup_logging():
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Solo configurar si no tiene handlers
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        root_logger.addHandler(handler)
    else:
        # Si ya tiene handlers, solo actualizar el nivel
        for handler in root_logger.handlers:
            handler.setLevel(logging.INFO)

# Llamar al inicio del módulo
setup_logging()


def fargate_handler(task_name: str = None):
    """
    Generic handler for Fargate tasks
    
    Reads environment variables and executes the specified task.
    
    Args:
        task_name: Name of the task (if not provided, reads from TASK_NAME env var)
    
    Returns:
        Exit code (0 = success, 1 = failure)
    """
    try:
        # Get name of the task
        if not task_name:
            task_name = os.getenv('TASK_NAME')
            if not task_name:
                logger.error("TASK_NAME environment variable not set")
                return 1
        
        logger.info(f"Starting Fargate task: {task_name}")
        
        # Collect all environment variables
        envs = dict(os.environ)
        logger.info(f"Environment variables loaded: {len(envs)} vars")
        
        # Initialize MongoDB connection
        try:
            if not MongoManager.is_initialized():
                MongoManager.initialize()
        except Exception as e:
            logger.warning(f"MongoDB initialization failed: {e}")
        
        # Load task
        fetcher = FargateTaskFetcher(task_name)
        task = fetcher.get_task(envs=envs)
        
        # Execute task
        # Use get_event_loop() instead of asyncio.run() to avoid closing the loop
        # This is important for container reuse with Motor/MongoDB
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(task.run())
        
        if result:
            logger.info(f"Task {task_name} completed successfully")
            return 0
        else:
            logger.error(f"Task {task_name} failed")
            return 1
            
    except Exception as e:
        logger.exception(f"Unhandled exception in Fargate handler: {e}")
        return 1

