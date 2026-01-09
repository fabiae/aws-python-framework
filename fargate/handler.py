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


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
        
        # Load task
        fetcher = FargateTaskFetcher(task_name)
        task = fetcher.get_task(envs=envs)
        
        # Execute task
        result = asyncio.run(task.run())
        
        if result:
            logger.info(f"Task {task_name} completed successfully")
            return 0
        else:
            logger.error(f"Task {task_name} failed")
            return 1
            
    except Exception as e:
        logger.exception(f"Unhandled exception in Fargate handler: {e}")
        return 1


if __name__ == '__main__':
    """
    Entry point when executed directly
    
    Uso:
        TASK_NAME=search-tax-by-town python -m fargate.handler
    """
    exit_code = fargate_handler()
    sys.exit(exit_code)

