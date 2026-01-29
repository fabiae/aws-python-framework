"""
Fargate Executor - Executes Fargate tasks from Lambda

Provides an interface to invoke Fargate tasks from Lambda
using the boto3 ECS SDK.
"""

import os
import logging
import boto3
from typing import Dict, Any, List, Optional


logger = logging.getLogger(__name__)


class FargateExecutor:
    """
    Fargate task executor
    
    Allows invoking Fargate tasks from Lambda programmatically.
    Reads configuration from environment variables or accepts it as parameters.
    """
    
    def __init__(
        self,
        cluster: str = None,
        subnets: List[str] = None,
        assign_public_ip: str = None,
        region: str = None
    ):
        """
        Initializes the executor
        
        Args:
            cluster: Name of the ECS cluster (default: from ECS_CLUSTER env var)
            subnets: List of subnets (default: from ECS_SUBNETS env var)
            assign_public_ip: 'ENABLED' or 'DISABLED' (default: from env var)
            region: AWS region (default: from AWS_REGION or us-east-2)
        """
        # Configuration
        self.cluster = cluster or os.getenv('ECS_CLUSTER', 'DevDockets')
        
        # Subnets: accept list or string separated by commas
        if subnets:
            self.subnets = subnets
        else:
            subnets_str = os.getenv('ECS_SUBNETS', '')
            self.subnets = [s.strip() for s in subnets_str.split(',') if s.strip()]
        
        # If no subnets are configured, use the default ones
        if not self.subnets:
            self.subnets = [
                'subnet-0014a556ff4b9ad25',
                'subnet-0f3a12222df52ddc0',
                'subnet-0d271a90b055826cd',
                'subnet-05bdb3178e6dadef0'
            ]
        
        self.assign_public_ip = assign_public_ip or os.getenv('ECS_ASSIGN_PUBLIC_IP', 'ENABLED')
        self.region = region or os.getenv('AWS_REGION', 'us-east-2')
        
        # ECS client
        self._ecs_client = None
        
    
    @property
    def ecs_client(self):
        """
        ECS client (lazy loading)
        
        Returns:
            boto3 ECS client
        """
        if self._ecs_client is None:
            self._ecs_client = boto3.client('ecs', region_name=self.region)
        return self._ecs_client
    
    def run_task(
        self,
        task_name: str,
        envs: Dict[str, Any],
        container_name: str = None,
        task_definition_revision: int = None,
        count: int = 1,
        launch_type: str = 'FARGATE'
    ) -> str:
        """
        Executes a Fargate task
        
        Args:
            task_name: Name of the task (e.g: 'search-tax-by-town')
            envs: Environment variables to pass to the task
            container_name: Name of the container (default: task_name)
            task_definition_revision: Specific revision (default: latest)
            count: Number of instances to execute (default: 1)
            launch_type: Launch type (default: 'FARGATE')
        
        Returns:
            ARN of the first executed task
        
        Raises:
            Exception: If the execution fails
        """
        try:
            # Prepare task definition
            if task_definition_revision:
                task_definition = f"{task_name}:{task_definition_revision}"
            else:
                task_definition = task_name
            
            # Container name (default: same as task)
            if not container_name:
                container_name = task_name
            
            # Format environment variables for ECS
            environment = [
                {'name': key.upper(), 'value': str(value)}
                for key, value in envs.items()
            ]
            
            # Add TASK_NAME for the handler to know which task to execute
            environment.append({'name': 'TASK_NAME', 'value': task_name})
            
            # Execute task
            response = self.ecs_client.run_task(
                cluster=self.cluster,
                launchType=launch_type,
                taskDefinition=task_definition,
                count=count,
                networkConfiguration={
                    'awsvpcConfiguration': {
                        'subnets': self.subnets,
                        'assignPublicIp': self.assign_public_ip
                    }
                },
                overrides={
                    'containerOverrides': [
                        {
                            'name': container_name,
                            'environment': environment
                        }
                    ]
                }
            )
            
            # Get task ARN
            tasks = response.get('tasks', [])
            if not tasks:
                raise Exception("No tasks were started")
            
            task_arn = tasks[0]['taskArn']
            
            # Check for failures
            failures = response.get('failures', [])
            if failures:
                logger.warning(f"Some tasks failed to start: {failures}")
            
            return task_arn
            
        except Exception as e:
            logger.error(f"Error running Fargate task {task_name}: {e}")
            raise
    
    def run_task_batch(
        self,
        task_name: str,
        envs_list: List[Dict[str, Any]],
        **kwargs
    ) -> List[str]:
        """
        Executes multiple instances of a task with different envs
        
        Args:
            task_name: Name of the task
            envs_list: List of dictionaries of environment variables
            **kwargs: Additional parameters for run_task()
        
        Returns:
            List of task ARNs
        """
        task_arns = []
        
        for i, envs in enumerate(envs_list):
            try:
                task_arn = self.run_task(task_name, envs, **kwargs)
                task_arns.append(task_arn)
            except Exception as e:
                logger.error(f"Error running batch task {i}: {e}")
                task_arns.append(None)
        
        return task_arns
    
    def get_task_status(self, task_arn: str) -> Dict[str, Any]:
        """
        Gets the status of a task

        Args:
            task_arn: ARN of the task
        
        Returns:
            Information about the task
        """
        try:
            response = self.ecs_client.describe_tasks(
                cluster=self.cluster,
                tasks=[task_arn]
            )
            
            tasks = response.get('tasks', [])
            if not tasks:
                return {'status': 'NOT_FOUND'}
            
            task = tasks[0]
            return {
                'status': task.get('lastStatus'),
                'desired_status': task.get('desiredStatus'),
                'started_at': task.get('startedAt'),
                'stopped_at': task.get('stoppedAt'),
                'stop_reason': task.get('stoppedReason'),
                'task_arn': task_arn
            }
            
        except Exception as e:
            return {'status': 'ERROR', 'error': str(e)}

