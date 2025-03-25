"""
GeoServer Service for Property Mapper

This module provides a service layer for interacting with GeoServer from the Django application.
It handles configuration, connection management, and publication workflows.
"""
import os
import json
import logging
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from .geoserver_client import GeoServerClient

logger = logging.getLogger(__name__)

# Default GeoServer configuration
DEFAULT_GEOSERVER_URL = "http://localhost:8080/geoserver"
DEFAULT_GEOSERVER_WORKSPACE = "property_mapper"
DEFAULT_GEOSERVER_USERNAME = "admin"
DEFAULT_GEOSERVER_PASSWORD = "geoserver"

# Get configuration from settings or environment variables
GEOSERVER_URL = getattr(settings, "GEOSERVER_URL", os.environ.get("GEOSERVER_URL", DEFAULT_GEOSERVER_URL))
GEOSERVER_WORKSPACE = getattr(settings, "GEOSERVER_WORKSPACE", os.environ.get("GEOSERVER_WORKSPACE", DEFAULT_GEOSERVER_WORKSPACE))
GEOSERVER_USERNAME = getattr(settings, "GEOSERVER_USERNAME", os.environ.get("GEOSERVER_USERNAME", DEFAULT_GEOSERVER_USERNAME))
GEOSERVER_PASSWORD = getattr(settings, "GEOSERVER_PASSWORD", os.environ.get("GEOSERVER_PASSWORD", DEFAULT_GEOSERVER_PASSWORD))

# Flag to enable mock mode for development without GeoServer
GEOSERVER_MOCK_MODE = getattr(settings, "GEOSERVER_MOCK_MODE", os.environ.get("GEOSERVER_MOCK_MODE", "False").lower() == "true")

class GeoServerService:
    """Service for interacting with GeoServer"""
    
    def __init__(self, url=None, username=None, password=None, workspace=None, mock_mode=None):
        """
        Initialize the GeoServer service.
        
        Args:
            url: GeoServer URL (defaults to settings value)
            username: GeoServer admin username (defaults to settings value)
            password: GeoServer admin password (defaults to settings value)
            workspace: Default workspace to use (defaults to settings value)
            mock_mode: Whether to operate in mock mode without actual GeoServer
        """
        self.url = url or GEOSERVER_URL
        self.username = username or GEOSERVER_USERNAME
        self.password = password or GEOSERVER_PASSWORD
        self.workspace = workspace or GEOSERVER_WORKSPACE
        self.mock_mode = mock_mode if mock_mode is not None else GEOSERVER_MOCK_MODE
        
        # Lazy-loaded client
        self._client = None
        
        # Map layer cache
        self._layer_info_cache = {}
    
    @property
    def client(self):
        """Get the GeoServer client, initializing it if needed."""
        if self._client is None and not self.mock_mode:
            self._client = GeoServerClient(
                base_url=self.url,
                username=self.username,
                password=self.password,
                workspace=self.workspace
            )
        return self._client
    
    def check_connection(self):
        """
        Check if GeoServer is reachable and authentication works.
        
        Returns:
            bool: True if connection successful or in mock mode
        """
        if self.mock_mode:
            logger.info("GeoServer in mock mode, connection check skipped")
            return True
        
        try:
            return self.client.check_connection()
        except Exception as e:
            logger.error(f"Error checking GeoServer connection: {e}")
            return False
    
    def publish_map_layer(self, map_layer):
        """
        Publish a MapLayer to GeoServer.
        
        Args:
            map_layer: MapLayer instance to publish
            
        Returns:
            dict: Publication result or mock result
        """
        if self.mock_mode:
            logger.info(f"[MOCK] Publishing map layer to GeoServer: {map_layer.name}")
            return {
                "success": True,
                "mock": True,
                "layer_url": f"{self.url}/wms",
                "layer_name": f"{self.workspace}:{map_layer.name}"
            }
        
        try:
            if map_layer.layer_type == 'shapefile':
                # Publish shapefile
                if map_layer.shapefile_dir:
                    result = self.client.publish_shapefile(
                        shapefile_path=map_layer.shapefile_dir,
                        store_name=f"store_{map_layer.id}",
                        layer_name=map_layer.name
                    )
                else:
                    return {"success": False, "error": "No shapefile directory available"}
            
            elif map_layer.layer_type == 'geojson':
                # Get GeoJSON data
                geojson_data = map_layer.get_geojson_data()
                if not geojson_data:
                    return {"success": False, "error": "Failed to get GeoJSON data"}
                
                result = self.client.publish_geojson(
                    geojson_data=geojson_data,
                    store_name=f"store_{map_layer.id}",
                    layer_name=map_layer.name
                )
            
            else:
                return {"success": False, "error": f"Unsupported layer type for GeoServer: {map_layer.layer_type}"}
            
            if result and result.get("success"):
                # If we have a style for the layer, apply it
                if map_layer.style:
                    # Create a style in GeoServer (future feature)
                    pass
                
                # Add WMS URL to result
                result["layer_url"] = f"{self.url}/wms"
                result["layer_name"] = f"{self.workspace}:{map_layer.name}"
            
            return result
        
        except Exception as e:
            logger.error(f"Error publishing map layer to GeoServer: {e}")
            return {"success": False, "error": str(e)}
    
    def delete_map_layer(self, map_layer):
        """
        Delete a MapLayer from GeoServer.
        
        Args:
            map_layer: MapLayer instance to delete
            
        Returns:
            bool: True if deleted successfully or in mock mode
        """
        if self.mock_mode:
            logger.info(f"[MOCK] Deleting map layer from GeoServer: {map_layer.name}")
            return True
        
        try:
            return self.client.delete_layer(layer_name=map_layer.name)
        except Exception as e:
            logger.error(f"Error deleting map layer from GeoServer: {e}")
            return False
    
    def get_map_layer_info(self, map_layer):
        """
        Get information about a MapLayer from GeoServer.
        
        Args:
            map_layer: MapLayer instance
            
        Returns:
            dict: Layer information or None if not found
        """
        if self.mock_mode:
            logger.info(f"[MOCK] Getting map layer info from GeoServer: {map_layer.name}")
            return {
                "name": map_layer.name,
                "title": map_layer.name,
                "abstract": map_layer.description or "",
                "defaultStyle": {"name": "point"},
                "resource": {"projection": "EPSG:4326"},
                "mock": True
            }
        
        # Check cache first
        if map_layer.id in self._layer_info_cache:
            return self._layer_info_cache[map_layer.id]
        
        try:
            info = self.client.get_layer_info(layer_name=map_layer.name)
            if info:
                # Cache the result
                self._layer_info_cache[map_layer.id] = info
            return info
        except Exception as e:
            logger.error(f"Error getting map layer info from GeoServer: {e}")
            return None
    
    def get_wms_url(self, map_layer):
        """
        Get the WMS URL for a MapLayer.
        
        Args:
            map_layer: MapLayer instance
            
        Returns:
            str: WMS URL or None if not published
        """
        if self.mock_mode:
            return f"{self.url}/wms"
        
        # Check if layer exists in GeoServer
        info = self.get_map_layer_info(map_layer)
        if info:
            return f"{self.url}/wms"
        return None
    
    def get_wms_layer_name(self, map_layer):
        """
        Get the WMS layer name for a MapLayer.
        
        Args:
            map_layer: MapLayer instance
            
        Returns:
            str: WMS layer name or None if not published
        """
        if self.mock_mode:
            return f"{self.workspace}:{map_layer.name}"
        
        # Check if layer exists in GeoServer
        info = self.get_map_layer_info(map_layer)
        if info:
            return f"{self.workspace}:{map_layer.name}"
        return None
    
    def clear_cache(self):
        """Clear the layer info cache."""
        self._layer_info_cache = {}

# Create a singleton instance for use throughout the application
geoserver_service = GeoServerService()