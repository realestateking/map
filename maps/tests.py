from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point, Polygon
from django.core.files.uploadedfile import SimpleUploadedFile

from .models import Region, Property, PropertyDataFile, PropertyAttribute
from .services import process_property_file
from .ml_models import predict_property_height, predict_property_quality


class RegionModelTestCase(TestCase):
    """Test case for the Region model."""
    
    def setUp(self):
        self.region = Region.objects.create(
            name="Test Region",
            description="A test region",
            center_latitude=45.0,
            center_longitude=-73.0,
            default_zoom=10
        )
    
    def test_region_creation(self):
        """Test Region model creation."""
        self.assertEqual(self.region.name, "Test Region")
        self.assertEqual(self.region.center_latitude, 45.0)
        self.assertEqual(self.region.center_longitude, -73.0)
        self.assertEqual(self.region.default_zoom, 10)


class PropertyModelTestCase(TestCase):
    """Test case for the Property model."""
    
    def setUp(self):
        self.region = Region.objects.create(
            name="Test Region",
            description="A test region",
            center_latitude=45.0,
            center_longitude=-73.0,
            default_zoom=10
        )
        
        self.property = Property.objects.create(
            lot_number="LOT-123",
            matricule_number="MAT-456",
            address="123 Test Street",
            city="Test City",
            postal_code="T3ST 1E1",
            location=Point(-73.0, 45.0),
            property_type="Residential",
            land_area=1000.0,
            building_area=500.0,
            year_built=2000,
            region=self.region
        )
    
    def test_property_creation(self):
        """Test Property model creation."""
        self.assertEqual(self.property.lot_number, "LOT-123")
        self.assertEqual(self.property.address, "123 Test Street")
        self.assertEqual(self.property.location.x, -73.0)
        self.assertEqual(self.property.location.y, 45.0)


class PropertyAttributeTestCase(TestCase):
    """Test case for the PropertyAttribute model."""
    
    def setUp(self):
        self.region = Region.objects.create(
            name="Test Region",
            center_latitude=45.0,
            center_longitude=-73.0
        )
        
        self.property = Property.objects.create(
            lot_number="LOT-123",
            region=self.region
        )
        
        self.attribute = PropertyAttribute.objects.create(
            property=self.property,
            name="test_attribute",
            value="test_value"
        )
    
    def test_property_attribute_creation(self):
        """Test PropertyAttribute model creation."""
        self.assertEqual(self.attribute.name, "test_attribute")
        self.assertEqual(self.attribute.value, "test_value")
        self.assertEqual(self.attribute.property, self.property)


class ViewTestCase(TestCase):
    """Test case for views."""
    
    def setUp(self):
        self.client = Client()
        self.region = Region.objects.create(
            name="Test Region",
            center_latitude=45.0,
            center_longitude=-73.0,
            default_zoom=10
        )
        
        self.property = Property.objects.create(
            lot_number="LOT-123",
            address="123 Test Street",
            city="Test City",
            location=Point(-73.0, 45.0),
            property_type="Residential",
            region=self.region
        )
        
        # Create a user for admin views
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword'
        )
    
    def test_index_view(self):
        """Test the index view."""
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'maps/index.html')
        self.assertIn('regions', response.context)
        self.assertIn('search_form', response.context)
    
    def test_property_detail_view(self):
        """Test the property detail view."""
        response = self.client.get(reverse('property_detail', args=[self.property.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'maps/property_detail.html')
        self.assertEqual(response.context['property'], self.property)
    
    def test_search_properties_view(self):
        """Test the search properties view."""
        response = self.client.get(reverse('search_properties'), {'search_type': 'lot', 'lot_number': 'LOT-123'})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'maps/search_results.html')
        self.assertEqual(len(response.context['properties']), 1)
    
    def test_admin_dashboard_view_requires_login(self):
        """Test that admin dashboard requires login."""
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
        
        # Login and try again
        self.client.login(username='testuser', password='testpassword')
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'maps/admin_dashboard.html')


class MLModelTestCase(TestCase):
    """Test case for ML models."""
    
    def setUp(self):
        self.region = Region.objects.create(
            name="Test Region",
            center_latitude=45.0,
            center_longitude=-73.0
        )
        
        self.property = Property.objects.create(
            lot_number="LOT-123",
            property_type="Residential",
            building_area=500.0,
            land_area=1000.0,
            year_built=2000,
            region=self.region
        )
    
    def test_predict_property_height(self):
        """Test predicting property height."""
        height = predict_property_height(self.property)
        self.assertIsNotNone(height)
        self.assertTrue(isinstance(height, float))
    
    def test_predict_property_quality(self):
        """Test predicting property quality."""
        quality = predict_property_quality(self.property)
        self.assertIsNotNone(quality)
        self.assertTrue(isinstance(quality, float))
        self.assertTrue(0 <= quality <= 100)
