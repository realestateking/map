"""
GeoServer REST API Client for Property Mapper

This module provides a client for interacting with the GeoServer REST API
to upload and manage layers in GeoServer.
"""
import os
import json
import requests
from urllib.parse import urljoin
import zipfile
import tempfile
import shutil
import logging

logger = logging.getLogger(__name__)

class GeoServerClient:
    """Client for interacting with GeoServer's REST API"""
    
    def __init__(self, base_url, username, password, workspace=None):
        """
        Initialize the GeoServer client.
        
        Args:
            base_url: Base URL of the GeoServer instance
            username: GeoServer admin username
            password: GeoServer admin password
            workspace: Default workspace to use (created if doesn't exist)
        """
        self.base_url = base_url.rstrip('/')
        self.rest_url = f"{self.base_url}/rest"
        self.username = username
        self.password = password
        self.auth = (username, password)
        
        # Create default workspace if provided
        if workspace:
            self.workspace = workspace
            self.ensure_workspace_exists(workspace)
    
    def ensure_workspace_exists(self, workspace):
        """Ensure a workspace exists, creating it if it doesn't."""
        url = f"{self.rest_url}/workspaces/{workspace}.json"
        
        try:
            # Check if workspace exists
            response = requests.get(url, auth=self.auth)
            
            if response.status_code == 404:
                # Create workspace if it doesn't exist
                create_url = f"{self.rest_url}/workspaces"
                headers = {"Content-Type": "application/json"}
                data = {"workspace": {"name": workspace}}
                
                create_response = requests.post(
                    create_url, 
                    json=data,
                    headers=headers,
                    auth=self.auth
                )
                
                if create_response.status_code in (201, 200):
                    logger.info(f"Created workspace: {workspace}")
                else:
                    logger.error(f"Failed to create workspace: {workspace}, Status: {create_response.status_code}, Response: {create_response.text}")
                    raise Exception(f"Failed to create workspace: {workspace}")
        except Exception as e:
            logger.error(f"Error ensuring workspace exists: {e}")
            raise
    
    def publish_shapefile(self, shapefile_path, store_name=None, layer_name=None, workspace=None):
        """
        Publish a shapefile to GeoServer.
        
        Args:
            shapefile_path: Path to the .shp file or directory containing shapefile components
            store_name: Name of the datastore to create (defaults to basename of shapefile)
            layer_name: Name of the layer to create (defaults to basename of shapefile)
            workspace: Workspace to use (defaults to self.workspace)
            
        Returns:
            dict: Response data or None if failed
        """
        if workspace is None:
            if not hasattr(self, 'workspace'):
                raise ValueError("Workspace must be provided or set during initialization")
            workspace = self.workspace
        
        # Ensure the workspace exists
        self.ensure_workspace_exists(workspace)
        
        # Handle shapefile paths
        if os.path.isdir(shapefile_path):
            # Find .shp file in directory
            shp_files = [f for f in os.listdir(shapefile_path) if f.lower().endswith('.shp')]
            if not shp_files:
                raise ValueError(f"No .shp file found in {shapefile_path}")
            basename = os.path.splitext(shp_files[0])[0]
            shapefile_dir = shapefile_path
        else:
            basename = os.path.splitext(os.path.basename(shapefile_path))[0]
            shapefile_dir = os.path.dirname(shapefile_path)
        
        # Use provided names or defaults
        if not store_name:
            store_name = basename
        if not layer_name:
            layer_name = basename
        
        # Create a ZIP file containing all shapefile components
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip:
            temp_zip_path = temp_zip.name
        
        try:
            # Create ZIP file with all shapefile components
            with zipfile.ZipFile(temp_zip_path, 'w') as zipf:
                for file in os.listdir(shapefile_dir):
                    if file.startswith(basename) and file.lower().endswith(('.shp', '.shx', '.dbf', '.prj', '.sbn', '.sbx', '.xml')):
                        zipf.write(os.path.join(shapefile_dir, file), arcname=file)
            
            # Upload the zipped shapefile
            url = f"{self.rest_url}/workspaces/{workspace}/datastores/{store_name}/file.shp"
            headers = {'Content-Type': 'application/zip'}
            
            with open(temp_zip_path, 'rb') as f:
                response = requests.put(url, data=f, headers=headers, auth=self.auth)
            
            if response.status_code in (201, 200):
                logger.info(f"Published shapefile to GeoServer as {workspace}:{layer_name}")
                return {"success": True, "workspace": workspace, "store": store_name, "layer": layer_name}
            else:
                logger.error(f"Failed to publish shapefile. Status: {response.status_code}, Response: {response.text}")
                return {"success": False, "error": response.text}
        
        except Exception as e:
            logger.error(f"Error publishing shapefile: {e}")
            return {"success": False, "error": str(e)}
        
        finally:
            # Clean up temporary file
            if os.path.exists(temp_zip_path):
                os.unlink(temp_zip_path)
    
    def publish_geojson(self, geojson_data, store_name, layer_name=None, workspace=None):
        """
        Publish GeoJSON data to GeoServer.
        
        Args:
            geojson_data: GeoJSON data as string or dict
            store_name: Name of the datastore to create
            layer_name: Name of the layer to create (defaults to store_name)
            workspace: Workspace to use (defaults to self.workspace)
            
        Returns:
            dict: Response data or None if failed
        """
        if workspace is None:
            if not hasattr(self, 'workspace'):
                raise ValueError("Workspace must be provided or set during initialization")
            workspace = self.workspace
        
        # Ensure the workspace exists
        self.ensure_workspace_exists(workspace)
        
        # Use provided layer name or default to store name
        if not layer_name:
            layer_name = store_name
        
        # Convert dict to JSON string if needed
        if isinstance(geojson_data, dict):
            geojson_data = json.dumps(geojson_data)
        
        # Create a temporary GeoJSON file
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(geojson_data.encode('utf-8'))
        
        try:
            # Upload the GeoJSON file
            url = f"{self.rest_url}/workspaces/{workspace}/datastores/{store_name}/file.geojson"
            headers = {'Content-Type': 'application/json'}
            
            with open(temp_file_path, 'rb') as f:
                response = requests.put(url, data=f, headers=headers, auth=self.auth)
            
            if response.status_code in (201, 200):
                logger.info(f"Published GeoJSON to GeoServer as {workspace}:{layer_name}")
                return {"success": True, "workspace": workspace, "store": store_name, "layer": layer_name}
            else:
                logger.error(f"Failed to publish GeoJSON. Status: {response.status_code}, Response: {response.text}")
                return {"success": False, "error": response.text}
        
        except Exception as e:
            logger.error(f"Error publishing GeoJSON: {e}")
            return {"success": False, "error": str(e)}
        
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
    
    def delete_layer(self, layer_name, workspace=None, recursive=True):
        """
        Delete a layer from GeoServer.
        
        Args:
            layer_name: Name of the layer to delete
            workspace: Workspace containing the layer (defaults to self.workspace)
            recursive: Whether to recursively delete resources (datastores, etc.)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if workspace is None:
            if not hasattr(self, 'workspace'):
                raise ValueError("Workspace must be provided or set during initialization")
            workspace = self.workspace
        
        url = f"{self.rest_url}/workspaces/{workspace}/layers/{layer_name}"
        if recursive:
            url += "?recurse=true"
        
        try:
            response = requests.delete(url, auth=self.auth)
            
            if response.status_code in (200, 204):
                logger.info(f"Deleted layer {workspace}:{layer_name}")
                return True
            else:
                logger.error(f"Failed to delete layer {workspace}:{layer_name}. Status: {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"Error deleting layer: {e}")
            return False
    
    def get_layer_info(self, layer_name, workspace=None):
        """
        Get information about a layer.
        
        Args:
            layer_name: Name of the layer
            workspace: Workspace containing the layer (defaults to self.workspace)
            
        Returns:
            dict: Layer information or None if not found
        """
        if workspace is None:
            if not hasattr(self, 'workspace'):
                raise ValueError("Workspace must be provided or set during initialization")
            workspace = self.workspace
        
        url = f"{self.rest_url}/workspaces/{workspace}/layers/{layer_name}.json"
        
        try:
            response = requests.get(url, auth=self.auth)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Layer {workspace}:{layer_name} not found. Status: {response.status_code}")
                return None
        
        except Exception as e:
            logger.error(f"Error getting layer info: {e}")
            return None
    
    def set_layer_style(self, layer_name, style_name, workspace=None):
        """
        Set the default style for a layer.
        
        Args:
            layer_name: Name of the layer
            style_name: Name of the style to apply
            workspace: Workspace containing the layer (defaults to self.workspace)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if workspace is None:
            if not hasattr(self, 'workspace'):
                raise ValueError("Workspace must be provided or set during initialization")
            workspace = self.workspace
        
        url = f"{self.rest_url}/workspaces/{workspace}/layers/{layer_name}.json"
        
        data = {
            "layer": {
                "defaultStyle": {
                    "name": style_name
                }
            }
        }
        
        headers = {"Content-Type": "application/json"}
        
        try:
            response = requests.put(url, json=data, headers=headers, auth=self.auth)
            
            if response.status_code in (200, 201):
                logger.info(f"Set style {style_name} for layer {workspace}:{layer_name}")
                return True
            else:
                logger.error(f"Failed to set style for layer. Status: {response.status_code}, Response: {response.text}")
                return False
        
        except Exception as e:
            logger.error(f"Error setting layer style: {e}")
            return False
    
    def list_layers(self, workspace=None):
        """
        List all layers in a workspace.
        
        Args:
            workspace: Workspace to list layers from (defaults to self.workspace)
            
        Returns:
            list: List of layer names or empty list if failed
        """
        if workspace is None:
            if not hasattr(self, 'workspace'):
                raise ValueError("Workspace must be provided or set during initialization")
            workspace = self.workspace
        
        url = f"{self.rest_url}/workspaces/{workspace}/layers.json"
        
        try:
            response = requests.get(url, auth=self.auth)
            
            if response.status_code == 200:
                data = response.json()
                if 'layers' in data and 'layer' in data['layers']:
                    return [layer['name'] for layer in data['layers']['layer']]
                return []
            else:
                logger.warning(f"Failed to list layers. Status: {response.status_code}")
                return []
        
        except Exception as e:
            logger.error(f"Error listing layers: {e}")
            return []
    
    def check_connection(self):
        """
        Check if the GeoServer instance is reachable and authentication works.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        url = f"{self.rest_url}/about/version.json"
        
        try:
            response = requests.get(url, auth=self.auth)
            
            if response.status_code == 200:
                version_info = response.json()
                logger.info(f"Connected to GeoServer version: {version_info.get('about', {}).get('resource', [{}])[0].get('Version', 'Unknown')}")
                return True
            else:
                logger.warning(f"Failed to connect to GeoServer. Status: {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"Error connecting to GeoServer: {e}")
            return False