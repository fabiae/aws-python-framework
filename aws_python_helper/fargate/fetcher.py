"""
Fargate Task Fetcher - Dynamically load Fargate tasks based on name
"""

import os
import importlib.util
from pathlib import Path
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class FargateTaskFetcher:
    """
    Dynamically load Fargate tasks
    
    Searches for tasks in folders within 'src/task/' with a task.py file inside.
    
    Convention:
        task-name -> src/task/task-name/task.py -> TaskNameTask
    
    Examples:
        'search-tax-by-town' -> src/task/search-tax-by-town/task.py -> SearchTaxByTownTask
        'process-data' -> src/task/process-data/task.py -> ProcessDataTask
    """
    
    TASKS_FOLDER = "src/task"
    _cache = {}
    
    def __init__(self, task_name: str):
        """
        Initializes the fetcher
        
        Args:
            task_name: Name of the task in kebab-case (e.g.: 'search-tax-by-town')
        """
        self.task_name = task_name
    
    @property
    def file_path(self) -> str:
        """
        Calculates the path of the task file
        
        Converts 'search-tax-by-town' to 'search-tax-by-town/task.py'
        
        Returns:
            Absolute path to the task file
        """
        # Keep kebab-case for folder name
        folder_name = self.task_name
        
        base_path = Path(os.getcwd()) / self.TASKS_FOLDER / folder_name
        file_path = base_path / 'task.py'
        
        logger.debug(f"Resolved task path: {file_path}")
        
        return str(file_path)
    
    def get_task(self, envs: Dict[str, str] = None):
        """
        Loads and returns an instance of the task
        
        Args:
            envs: Environment variables to pass to the task
        
        Returns:
            Instance of the task
        
        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the task class is not valid
        """
        file_path = self.file_path
        
        # Verify that the file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(
                f"Task not found: {file_path}\n"
                f"Expected file for task '{self.task_name}' at {self.TASKS_FOLDER}/{self.task_name}/task.py"
            )
        
        # Load module dynamically
        spec = importlib.util.spec_from_file_location("task_module", file_path)
        if not spec or not spec.loader:
            raise ImportError(f"Could not load module spec from: {file_path}")
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Search for a class that inherits from FargateTask
        # Expected class name: 'search-tax-by-town' -> 'SearchTaxByTownTask'
        class_name = ''.join(
            word.capitalize() for word in self.task_name.split('-')
        ) + 'Task'
        
        task_class = None
        for item_name in dir(module):
            item = getattr(module, item_name)
            if (isinstance(item, type) and 
                hasattr(item, 'execute') and 
                item.__name__ not in ['FargateTask', 'ABC']):
                task_class = item
                break
        
        if not task_class:
            raise ValueError(
                f"No FargateTask class found in {file_path}\n"
                f"Make sure your file exports a class that inherits from FargateTask\n"
                f"Expected class name: {class_name}"
            )
        
        logger.info(f"Loaded task: {task_class.__name__} from {file_path}")
        
        # Return new instance with envs
        return task_class(envs=envs)
