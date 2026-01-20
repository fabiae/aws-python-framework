"""
AWS Lambda Standalone Module
"""

from .base import Lambda
from .handler import lambda_handler

__all__ = ['Lambda', 'lambda_handler']
