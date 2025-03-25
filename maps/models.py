from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
import os

# Note: Temporarily using regular fields instead of GeoDjango fields


class Region(models.Model):
    """Model representing a geographical region"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    center_latitude = models.FloatField()
    center_longitude = models.FloatField()
    default_zoom = models.IntegerField(default=12)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class PropertyDataFile(models.Model):
    """Model for uploaded Excel files containing property data"""
    FILE_TYPE_CHOICES = [
        ('excel', 'Excel File'),
        ('kml', 'KML File'),
    ]
    
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='files')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_files')
    file = models.FileField(
        upload_to='property_files/',
        validators=[FileExtensionValidator(allowed_extensions=['xlsx', 'xls', 'kml', 'kmz'])]
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    processing_errors = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.title} ({self.get_file_type_display()})"
    
    def filename(self):
        return os.path.basename(self.file.name)


class Property(models.Model):
    """Model representing a real estate property"""
    # Basic information
    lot_number = models.CharField(max_length=100, db_index=True)
    matricule_number = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    address = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    
    # Geographic data (using regular fields temporarily)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    # Temporary alternative to polygon - could be JSON string representation
    boundary_coordinates = models.TextField(blank=True, null=True)
    
    # Property characteristics
    property_type = models.CharField(max_length=100, blank=True, null=True)
    land_area = models.FloatField(blank=True, null=True)
    building_area = models.FloatField(blank=True, null=True)
    year_built = models.IntegerField(blank=True, null=True)
    
    # Additional data
    owner = models.CharField(max_length=200, blank=True, null=True)
    assessed_value = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    last_sale_date = models.DateField(blank=True, null=True)
    last_sale_price = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    
    # AI-predicted attributes
    predicted_height = models.FloatField(blank=True, null=True)
    predicted_quality_score = models.FloatField(blank=True, null=True)  # 0-100 score
    
    # Metadata
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='properties')
    source_file = models.ForeignKey(PropertyDataFile, on_delete=models.SET_NULL, null=True, related_name='properties')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Properties"
        indexes = [
            models.Index(fields=['lot_number']),
            models.Index(fields=['matricule_number']),
            models.Index(fields=['address']),
        ]
    
    def __str__(self):
        if self.address:
            return f"{self.address} ({self.lot_number})"
        return self.lot_number


class PropertyAttribute(models.Model):
    """Model for storing dynamic/custom attributes for properties"""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='attributes')
    name = models.CharField(max_length=100)
    value = models.TextField()
    
    class Meta:
        unique_together = ('property', 'name')
    
    def __str__(self):
        return f"{self.name}: {self.value[:50]}"


class MapLayer(models.Model):
    """Model for custom map layers (GeoJSON, KML, Shapefile, etc)"""
    LAYER_TYPE_CHOICES = [
        ('geojson', 'GeoJSON'),
        ('kml', 'KML'),
        ('shapefile', 'Shapefile'),
        ('wms', 'WMS Service'),
        ('tile', 'Tile Layer'),
    ]
    
    FILE_STORAGE_CHOICES = [
        ('local', 'Local Storage'),
        ('onedrive', 'OneDrive'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    layer_type = models.CharField(max_length=10, choices=LAYER_TYPE_CHOICES)
    url = models.URLField(blank=True, null=True, help_text="URL for WMS or Tile layers")
    file = models.FileField(
        upload_to='map_layers/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['json', 'geojson', 'kml', 'kmz', 'zip', 'shp'])]
    )
    
    # OneDrive storage fields
    storage_type = models.CharField(
        max_length=10, 
        choices=FILE_STORAGE_CHOICES, 
        default='local',
        help_text="Storage location for the file"
    )
    onedrive_file_id = models.CharField(max_length=255, blank=True, null=True, help_text="File ID in OneDrive")
    onedrive_file_url = models.TextField(blank=True, null=True, help_text="Download URL for OneDrive file")
    onedrive_file_name = models.CharField(max_length=255, blank=True, null=True, help_text="Original file name in OneDrive")
    
    # Additional fields for shapefile components
    shapefile_dir = models.CharField(max_length=255, blank=True, null=True, 
                                    help_text="Directory containing extracted shapefile components")
    style = models.JSONField(blank=True, null=True, help_text="JSON object with style options")
    
    # If the layer is specific to a region, link it to the region
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=True, blank=True, related_name='layers')
    
    # For ordering in the layer control
    z_index = models.IntegerField(default=0, help_text="Order in layer control (higher values on top)")
    
    # Controls
    is_active = models.BooleanField(default=True)
    is_visible_by_default = models.BooleanField(default=False)
    is_base_layer = models.BooleanField(default=False, help_text="If true, treated as a base map")
    
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='map_layers')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        """Override save to handle shapefile extraction if needed"""
        # Get the file path before save for comparison
        old_file_path = None
        old_shapefile_dir = None
        if self.pk:
            try:
                old_instance = MapLayer.objects.get(pk=self.pk)
                if old_instance.file:
                    old_file_path = old_instance.file.path if hasattr(old_instance.file, 'path') else None
                old_shapefile_dir = old_instance.shapefile_dir
            except Exception:
                pass  # Ignore if we can't get old instance
        
        # First save the model to get an ID
        super().save(*args, **kwargs)
        
        import logging
        logger = logging.getLogger(__name__)
        
        # Process shapefiles if this is a shapefile layer
        if self.layer_type == 'shapefile' and self.file:
            # Conditions to process shapefile:
            # 1. No shapefile directory exists yet
            # 2. The file has changed
            # 3. The shapefile directory exists but is empty
            
            process_file = False
            file_changed = False
            
            # Check if directory doesn't exist or is empty
            if not self.shapefile_dir:
                logger.info(f"No shapefile directory set for layer {self.id}, will process file")
                process_file = True
            elif os.path.exists(self.shapefile_dir):
                # Check if directory is empty
                try:
                    if not os.listdir(self.shapefile_dir):
                        logger.info(f"Shapefile directory exists but is empty for layer {self.id}, will process file")
                        process_file = True
                except Exception as e:
                    logger.error(f"Error checking shapefile directory: {str(e)}")
                    process_file = True
            else:
                logger.info(f"Shapefile directory set but doesn't exist for layer {self.id}, will process file")
                process_file = True
            
            # Check if file has changed
            if old_file_path and hasattr(self.file, 'path'):
                file_changed = old_file_path != self.file.path
                if file_changed:
                    logger.info(f"File has changed for layer {self.id}, will reprocess")
                    process_file = True
            
            # Process the file if needed
            if process_file:
                try:
                    self.process_shapefile()
                except Exception as e:
                    import traceback
                    logger.error(f"Error processing shapefile for layer {self.id}: {str(e)}")
                    logger.error(traceback.format_exc())
    
    def process_shapefile(self):
        """Process uploaded shapefile (from ZIP or individual .shp file)"""
        import os
        import zipfile
        import tempfile
        import shutil
        import logging
        from django.conf import settings
        
        logger = logging.getLogger(__name__)
        logger.info(f"Processing shapefile for layer {self.id}")
        
        # Make sure file exists and is accessible
        if not self.file:
            logger.error("No file attached to layer")
            raise ValueError("No file attached to layer")
            
        try:
            filename = os.path.basename(self.file.name)
            
            # Create a temporary file to handle potential file access issues
            with tempfile.TemporaryDirectory() as temp_dir:
                # Save file to temporary location first to ensure we can access it
                temp_file_path = os.path.join(temp_dir, filename)
                with open(temp_file_path, 'wb') as destination:
                    for chunk in self.file.chunks():
                        destination.write(chunk)
                
                logger.info(f"Processing file: {filename} (saved to temp location)")
                
                # Use the predefined directory from settings
                layer_dir = os.path.join(settings.SHAPEFILES_DIR, f'layer_{self.id}')
                if os.path.exists(layer_dir):
                    # Remove existing directory if it exists
                    shutil.rmtree(layer_dir)
                    
                os.makedirs(layer_dir, exist_ok=True)
                logger.info(f"Created layer directory: {layer_dir}")
                
                # Handle ZIP files with shapefile components
                if filename.lower().endswith('.zip'):
                    logger.info(f"Extracting ZIP file to {layer_dir}")
                    try:
                        # Validate the ZIP file integrity
                        if not zipfile.is_zipfile(temp_file_path):
                            logger.error(f"The file is not a valid ZIP file: {temp_file_path}")
                            raise ValueError("The uploaded file is not a valid ZIP archive")
                            
                        # List the contents before extraction for debugging
                        try:
                            with zipfile.ZipFile(temp_file_path, 'r') as zip_ref:
                                file_list = zip_ref.namelist()
                                logger.info(f"ZIP file contains {len(file_list)} files: {file_list}")
                                
                                # Check for shapefile components in the ZIP
                                shp_files_in_zip = [f for f in file_list if f.lower().endswith('.shp')]
                                logger.info(f"SHP files in ZIP: {shp_files_in_zip}")
                                
                                # Check if the zip contains any nested directories
                                has_dirs = any('/' in f for f in file_list)
                                logger.info(f"ZIP contains nested directories: {has_dirs}")
                                
                                # Extract all files
                                zip_ref.extractall(layer_dir)
                                logger.info(f"Successfully extracted ZIP to {layer_dir}")
                        except Exception as zip_ex:
                            logger.error(f"Error examining ZIP contents: {str(zip_ex)}")
                            raise ValueError(f"Error processing ZIP contents: {str(zip_ex)}")
                        
                        # Verify the extracted files
                        all_extracted = os.listdir(layer_dir)
                        logger.info(f"Extracted files: {all_extracted}")
                        
                        # Find shapefile components recursively if needed
                        import glob
                        shp_files = glob.glob(os.path.join(layer_dir, '**', '*.shp'), recursive=True)
                        if not shp_files:
                            logger.error(f"No .shp files found in extracted ZIP contents")
                            raise ValueError("No .shp file found in the ZIP archive")
                            
                        logger.info(f"Found shapefile(s) in ZIP: {shp_files}")
                    except zipfile.BadZipFile as e:
                        logger.error(f"Bad ZIP file: {str(e)}")
                        raise ValueError(f"Invalid ZIP file: {str(e)}")
                else:
                    # For individual .shp files, try to find related files in the same directory
                    logger.info(f"Processing individual .shp file: {filename}")
                    
                    # Copy the shapefile itself to the final location
                    shutil.copy(temp_file_path, os.path.join(layer_dir, filename))
                    
                    # Since individual .shp files require companion files that would have been
                    # uploaded separately, we'll log a warning but continue
                    logger.warning(f"Uploaded single .shp file without companion files. Functionality may be limited.")
                
                # For individual .shp files, verify we have essential files
                if filename.lower().endswith('.shp'):
                    base_name = os.path.splitext(filename)[0]
                    if not os.path.exists(os.path.join(layer_dir, base_name + '.dbf')) or \
                       not os.path.exists(os.path.join(layer_dir, base_name + '.shx')):
                        logger.warning(f"Missing required related files for shapefile {filename}")
            
            # Update the model with the directory path
            self.shapefile_dir = layer_dir
            logger.info(f"Shapefile directory set to: {layer_dir}")
            super().save(update_fields=['shapefile_dir'])
            
        except Exception as e:
            logger.error(f"Error processing shapefile: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise
        
    def get_geojson_data(self, simplify='auto', max_features=None):
        """
        Convert shapefile to GeoJSON for web display with simplification options
        
        Args:
            simplify (str or float): 'auto' for automatic simplification based on size,
                                    or a float between 0-1 for manual simplification level,
                                    or None for no simplification
            max_features (int): Maximum number of features to include in the output
        
        Returns:
            str: GeoJSON string or None if error
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Handle different layer types
        if self.layer_type == 'geojson' and self.file:
            # If it's a GeoJSON file, just return the file content
            try:
                logger.info(f"Reading GeoJSON file for layer {self.id}: {self.file.path}")
                with open(self.file.path, 'r') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Error reading GeoJSON file: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return None
                
        # For shapefiles, handle both local and OneDrive storage
        if self.layer_type != 'shapefile':
            logger.warning(f"Cannot generate GeoJSON for layer {self.id}: not a shapefile layer")
            return None
            
        import os
        import json
        import glob
        import tempfile
        import zipfile
        import requests
        from datetime import date, datetime
        from django.conf import settings
        
        # For OneDrive storage, we need to download and process the file first
        if self.storage_type == 'onedrive' and self.onedrive_file_url and not self.shapefile_dir:
            try:
                logger.info(f"Processing OneDrive shapefile for layer {self.id}")
                
                # Create a directory for this layer's shapefile
                layer_dir = os.path.join(settings.MEDIA_ROOT, 'shapefiles', f'layer_{self.id}')
                os.makedirs(layer_dir, exist_ok=True)
                
                # Download the file from OneDrive
                logger.info(f"Downloading file from OneDrive: {self.onedrive_file_url}")
                response = requests.get(self.onedrive_file_url, stream=True)
                
                if response.status_code == 200:
                    # Save to a temporary file
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
                        for chunk in response.iter_content(chunk_size=8192):
                            temp_file.write(chunk)
                        temp_path = temp_file.name
                    
                    # Extract the zip file
                    try:
                        logger.info(f"Extracting ZIP file to {layer_dir}")
                        with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                            zip_ref.extractall(layer_dir)
                        
                        # Update the model with the directory path
                        self.shapefile_dir = layer_dir
                        super().save(update_fields=['shapefile_dir'])
                        
                        # Clean up the temporary file
                        os.unlink(temp_path)
                        
                    except Exception as e:
                        logger.error(f"Error extracting ZIP file: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                else:
                    logger.error(f"Failed to download file from OneDrive. Status code: {response.status_code}")
                    return None
                    
            except Exception as e:
                logger.error(f"Error processing OneDrive shapefile: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return None
        
        # After potential OneDrive processing, check if we have a shapefile directory
        if not self.shapefile_dir:
            logger.warning(f"No shapefile directory for layer {self.id}")
            return None
            
        # Check if directory exists
        if not os.path.exists(self.shapefile_dir):
            logger.error(f"Shapefile directory does not exist: {self.shapefile_dir}")
            return None
            
        # Find the .shp file in the directory (recursively)
        logger.info(f"Looking for shapefile in directory: {self.shapefile_dir}")
        shp_files = glob.glob(os.path.join(self.shapefile_dir, '**', '*.shp'), recursive=True)
        
        if not shp_files:
            logger.error(f"No .shp files found in directory (recursive search): {self.shapefile_dir}")
            # List all files in the directory to help debug
            all_files = []
            for root, dirs, files in os.walk(self.shapefile_dir):
                for file in files:
                    all_files.append(os.path.join(root, file).replace(self.shapefile_dir, '').lstrip('/\\'))
            logger.info(f"All files in directory tree: {all_files}")
            return None
            
        try:
            # Use pyshp (shapefile) library to convert to GeoJSON
            import shapefile
            
            shp_file = shp_files[0]
            logger.info(f"Processing shapefile: {shp_file}")
            
            # Read the shapefile
            sf = shapefile.Reader(shp_file)
            
            # Convert to GeoJSON
            geojson = {"type": "FeatureCollection", "features": []}
            
            # Custom JSON serializer to handle dates
            def json_serial(obj):
                if isinstance(obj, (datetime, date)):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")
            
            # Get total number of shapes
            total_shapes = len(sf.shapes())
            logger.info(f"Processing {total_shapes} shapes from shapefile")
            
            # Determine simplification level based on number of shapes and zoom level
            simplify_factor = None
            
            # Get zoom level from request if available
            zoom_level = None
            try:
                # Check if we're being called from a view with request.GET
                if 'zoom' in self._current_request.GET:
                    zoom_level = int(self._current_request.GET.get('zoom'))
                    logger.info(f"Using zoom level from request: {zoom_level}")
            except (AttributeError, ValueError):
                # No zoom level available or invalid
                pass
                
            if simplify == 'auto':
                # Base simplification on feature count
                if total_shapes > 500000:
                    simplify_factor = 0.01  # Very aggressive simplification for huge files
                elif total_shapes > 100000:
                    simplify_factor = 0.005  # High simplification for large files
                elif total_shapes > 50000:
                    simplify_factor = 0.001  # Medium simplification
                elif total_shapes > 10000:
                    simplify_factor = 0.0005  # Light simplification
                
                # Adjust based on zoom level if available
                if zoom_level is not None:
                    if zoom_level <= 10:
                        # Further out - more simplification
                        simplify_factor = max(simplify_factor * 2, 0.01)
                    elif zoom_level >= 16:
                        # Zoomed in - less simplification
                        simplify_factor = min(simplify_factor / 4, 0.0001)
                    elif zoom_level >= 14:
                        # Somewhat zoomed in - moderate simplification
                        simplify_factor = min(simplify_factor / 2, 0.0005)
            
            elif simplify and simplify not in ['none', 'false', '0']:
                try:
                    simplify_factor = float(simplify)
                except (ValueError, TypeError):
                    pass
                    
            if simplify_factor:
                logger.info(f"Using simplification factor: {simplify_factor}")
            
            # Determine number of features to include
            feature_limit = None
            if max_features:
                try:
                    feature_limit = int(max_features)
                    logger.info(f"Limiting output to {feature_limit} features")
                except (ValueError, TypeError):
                    pass
                    
            # Process shapes with potential subsampling
            feature_count = 0
            step = 1
            if feature_limit and total_shapes > feature_limit:
                step = max(1, int(total_shapes / feature_limit))
                logger.info(f"Taking every {step}th feature due to feature limit")
                
            shapes_to_process = sf.shapeRecords()
            if step > 1:
                shapes_to_process = shapes_to_process[::step]
            
            for shape_rec in shapes_to_process:
                # Skip null geometries
                if not shape_rec.shape.points:
                    continue
                    
                # Create feature with geometry
                try:
                    # Get the geometry interface (will be simplified if needed)
                    geometry = shape_rec.shape.__geo_interface__
                    
                    # Apply simplification if enabled and we have a polygon or line
                    if simplify_factor and geometry['type'] in ['Polygon', 'MultiPolygon', 'LineString', 'MultiLineString']:
                        # Simple point count-based simplification for polygons and lines
                        # More sophisticated algorithms would use libraries like shapely or topojson
                        if geometry['type'] in ['Polygon', 'LineString']:
                            if len(geometry['coordinates'][0]) > 10:
                                step = max(1, int(len(geometry['coordinates'][0]) * simplify_factor))
                                geometry['coordinates'][0] = geometry['coordinates'][0][::step]
                        elif geometry['type'] in ['MultiPolygon', 'MultiLineString']:
                            for i, poly in enumerate(geometry['coordinates']):
                                if len(poly[0]) > 10:
                                    step = max(1, int(len(poly[0]) * simplify_factor))
                                    geometry['coordinates'][i][0] = poly[0][::step]
                    
                    feature = {
                        "type": "Feature",
                        "geometry": geometry,
                        "properties": {}
                    }
                    
                    # Add all attributes
                    for field_idx, field_info in enumerate(sf.fields[1:]):  # Skip DeletionFlag
                        field_name = field_info[0]  # Get the name from the field descriptor
                        value = shape_rec.record[field_idx]
                        
                        # Handle binary data (convert to string)
                        if isinstance(value, bytes):
                            try:
                                value = value.decode('utf-8')
                            except UnicodeDecodeError:
                                value = str(value)
                                
                        feature["properties"][field_name] = value
                    
                    # Add feature if valid
                    geojson["features"].append(feature)
                    feature_count += 1
                    
                    # Break if we've reached feature limit
                    if feature_limit and feature_count >= feature_limit:
                        logger.info(f"Reached feature limit of {feature_limit}")
                        break
                        
                except Exception as feature_error:
                    logger.error(f"Error processing feature: {feature_error}")
                    continue
                
            # Add metadata if available
            if hasattr(sf, 'meta'):
                geojson["metadata"] = sf.meta
                
            # Add style information from the model if available
            if self.style:
                geojson["style"] = self.style
                
            # Add info about simplification and feature counts
            geojson["info"] = {
                "total_features": total_shapes,
                "included_features": feature_count,
                "simplification": simplify_factor if simplify_factor else "none"
            }
                
            # Return as JSON string with detailed logging
            logger.info(f"Successfully converted shapefile with {feature_count} features (from {total_shapes} total)")
            logger.info(f"Polygon count: {len([f for f in geojson['features'] if f['geometry']['type'] in ['Polygon', 'MultiPolygon']])}")
            logger.info(f"Line count: {len([f for f in geojson['features'] if f['geometry']['type'] in ['LineString', 'MultiLineString']])}")
            logger.info(f"Point count: {len([f for f in geojson['features'] if f['geometry']['type'] == 'Point'])}")
            
            # Convert to JSON string
            result_json = json.dumps(geojson, default=json_serial)
            
            # Log total string size for debugging
            logger.info(f"GeoJSON size: {len(result_json) / (1024 * 1024):.2f} MB")
            
            return result_json
            
        except Exception as e:
            # Log the error
            logger.error(f"Error converting shapefile to GeoJSON: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
        
    class Meta:
        ordering = ['-z_index', 'name']
