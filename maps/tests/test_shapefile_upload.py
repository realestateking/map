import os
import tempfile
from io import BytesIO
from zipfile import ZipFile

from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.urls import reverse

from maps.models import MapLayer, Region


class ShapefileUploadTest(TestCase):
    """Test case for shapefile upload functionality."""
    
    def setUp(self):
        """Set up test data."""
        # Create a test user
        self.user = User.objects.create_superuser(
            username="testadmin",
            email="testadmin@example.com",
            password="testpassword"
        )
        
        # Create a test region
        self.region = Region.objects.create(
            name="Test Region",
            center_latitude=45.0,
            center_longitude=-75.0,
            default_zoom=8
        )
        
        # Create a test client
        self.client = Client()
        self.client.login(username="testadmin", password="testpassword")
        
        # Prepare a test shapefile
        self.temp_shapefile = self.create_test_shapefile()
    
    def create_test_shapefile(self):
        """Create a test shapefile ZIP for testing."""
        # Create a temporary ZIP file with shapefile components
        zip_buffer = BytesIO()
        
        with ZipFile(zip_buffer, 'w') as zipf:
            # Add minimal shapefile components
            zipf.writestr('test.shp', b'POINT\nx,y\n1,1')
            zipf.writestr('test.dbf', b'INDEX\nid\n1')
            zipf.writestr('test.shx', b'PROJECTION\nWGS84')
        
        # Reset buffer position
        zip_buffer.seek(0)
        
        # Create a Django file wrapper
        return SimpleUploadedFile(
            name="test_shapefile.zip",
            content=zip_buffer.read(),
            content_type="application/zip"
        )
    
    def test_shapefile_upload(self):
        """Test that a shapefile can be uploaded and processed correctly."""
        # Count initial layers
        initial_count = MapLayer.objects.count()
        
        # Prepare POST data for creating a new layer
        post_data = {
            'name': 'Test Shapefile Layer',
            'layer_type': 'shapefile',
            'z_index': '0',
            'is_active': 'on',
            'region': str(self.region.id)
        }
        
        # Add the file to the request
        post_data['file'] = self.temp_shapefile
        
        # Make the request
        response = self.client.post(
            reverse('add_map_layer'),
            post_data,
            follow=True
        )
        
        # Check that the layer was created
        self.assertEqual(MapLayer.objects.count(), initial_count + 1)
        
        # Get the created layer
        layer = MapLayer.objects.latest('id')
        
        # Check that the layer was correctly processed
        self.assertEqual(layer.name, 'Test Shapefile Layer')
        self.assertEqual(layer.layer_type, 'shapefile')
        self.assertIsNotNone(layer.shapefile_dir)
        
        # Check that the directory exists
        self.assertTrue(os.path.exists(layer.shapefile_dir))
        
        # Check for the shapefile components
        self.assertTrue(os.path.exists(os.path.join(layer.shapefile_dir, 'test.shp')))
        self.assertTrue(os.path.exists(os.path.join(layer.shapefile_dir, 'test.dbf')))
        self.assertTrue(os.path.exists(os.path.join(layer.shapefile_dir, 'test.shx')))