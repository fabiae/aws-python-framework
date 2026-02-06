"""
External Database Proxy - Proxy to dynamically access multiple external MongoDB clusters
"""

from typing import Any
from .external_mongo_manager import ExternalMongoManager
from .database_proxy import DatabaseProxy


class ExternalDatabaseProxy:
    """
    Proxy to dynamically access multiple external MongoDB clusters and their databases
    
    This proxy allows accessing external clusters dynamically:
    - external_db.ClusterDockets.smart_data.addresses
    - external_db.ClusterDockets.core.users
    
    Each cluster name returns a DatabaseProxy for that cluster.
    """
    
    def __init__(self):
        """Initialize the proxy"""
        self._cluster_proxies = {}
    
    def __getattr__(self, cluster_name: str) -> Any:
        """
        Dynamic access to external clusters
        
        It is called when you access self.external_db.ClusterDockets
        
        Args:
            cluster_name: Name of the external cluster
        
        Returns:
            DatabaseProxy instance for that cluster
        
        Example:
            # Access database in external cluster
            result = await self.external_db.ClusterDockets.smart_data.addresses.find_one({...})
        """
        # Avoid recursion with internal attributes
        if cluster_name.startswith('_'):
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{cluster_name}'"
            )
        
        # Lazy load proxy for this cluster
        if cluster_name not in self._cluster_proxies:
            # Create a custom manager class for this specific cluster
            # Capture cluster_name in closure
            captured_cluster_name = cluster_name
            
            class ClusterMongoManager:
                @staticmethod
                def get_database(db_name: str):
                    return ExternalMongoManager.get_database(captured_cluster_name, db_name)
            
            self._cluster_proxies[cluster_name] = DatabaseProxy(ClusterMongoManager)
        
        return self._cluster_proxies[cluster_name]
    
    def __repr__(self) -> str:
        """String representation of the proxy"""
        available_clusters = ExternalMongoManager.get_available_clusters()
        cached_clusters = list(self._cluster_proxies.keys())
        return f"<ExternalDatabaseProxy available={available_clusters} cached={cached_clusters}>"
