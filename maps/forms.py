from django import forms
from .models import PropertyDataFile, Region, MapLayer


class PropertySearchForm(forms.Form):
    search_type = forms.ChoiceField(
        choices=[
            ('lot', 'Lot/Matricule Number'),
            ('address', 'Address'),
            ('radius', 'Radius Search'),
        ],
        initial='lot',
        widget=forms.RadioSelect()
    )
    
    lot_number = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Enter lot or matricule number'})
    )
    
    address = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Enter address'})
    )
    
    latitude = forms.FloatField(
        required=False,
        widget=forms.HiddenInput()
    )
    
    longitude = forms.FloatField(
        required=False,
        widget=forms.HiddenInput()
    )
    
    radius = forms.FloatField(
        min_value=0.1,
        max_value=10.0,
        initial=1.0,
        required=False,
        help_text='Radius in kilometers',
        widget=forms.NumberInput(attrs={'step': '0.1'})
    )
    
    region = forms.ModelChoiceField(
        queryset=Region.objects.all(),
        empty_label="All Regions",
        required=False
    )
    
    property_type = forms.ChoiceField(
        choices=[('', 'All Types')],  # Populated dynamically in __init__
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        super(PropertySearchForm, self).__init__(*args, **kwargs)
        
        # Dynamically populate property types from the database
        from .models import Property
        property_types = Property.objects.values_list('property_type', flat=True).distinct()
        property_type_choices = [('', 'All Types')]
        property_type_choices.extend([(pt, pt) for pt in property_types if pt])
        self.fields['property_type'].choices = property_type_choices
    
    def clean(self):
        cleaned_data = super().clean()
        search_type = cleaned_data.get('search_type')
        
        if search_type == 'lot' and not cleaned_data.get('lot_number'):
            self.add_error('lot_number', 'Lot or matricule number is required for this search type')
        
        elif search_type == 'address' and not cleaned_data.get('address'):
            self.add_error('address', 'Address is required for this search type')
        
        elif search_type == 'radius':
            if not cleaned_data.get('latitude') or not cleaned_data.get('longitude'):
                self.add_error(None, 'You must select a point on the map for radius search')
            if not cleaned_data.get('radius'):
                self.add_error('radius', 'Radius is required for this search type')
        
        return cleaned_data


class FileUploadForm(forms.ModelForm):
    class Meta:
        model = PropertyDataFile
        fields = ['file_type', 'title', 'description', 'region', 'file']
        
        
class MapLayerForm(forms.ModelForm):
    class Meta:
        model = MapLayer
        fields = ['name', 'description', 'layer_type', 'url', 'file', 'style', 
                 'region', 'z_index', 'is_active', 'is_visible_by_default', 'is_base_layer']
        widgets = {
            'style': forms.Textarea(attrs={'rows': 5, 'placeholder': '{"color": "#ff7800", "weight": 5, "opacity": 0.65}'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'z_index': forms.NumberInput(attrs={'value': '0'}),
        }
    
    def __init__(self, *args, **kwargs):
        super(MapLayerForm, self).__init__(*args, **kwargs)
        # Set default value for z_index if not provided
        if not self.initial.get('z_index'):
            self.initial['z_index'] = 0
            
    def clean(self):
        cleaned_data = super().clean()
        layer_type = cleaned_data.get('layer_type')
        url = cleaned_data.get('url')
        file = cleaned_data.get('file')
        
        # Ensure z_index is always set - this is critical
        if 'z_index' not in cleaned_data or cleaned_data.get('z_index') is None:
            cleaned_data['z_index'] = 0
            # Add this field to form.data
            if hasattr(self, 'data') and isinstance(self.data, dict):
                self.data['z_index'] = '0'
        
        # For tile or WMS layers, URL is required
        if layer_type in ['tile', 'wms'] and not url:
            self.add_error('url', 'URL is required for tile or WMS layers')
        
        # For file-based layers, only require file for new layers without files
        if layer_type in ['geojson', 'kml', 'shapefile']:
            instance = getattr(self, 'instance', None)
            if not file:  # No new file uploaded
                if instance and instance.pk and instance.file:
                    # This is an edit of an existing layer that already has a file
                    # so we don't need to require a new file upload
                    pass
                else:
                    # This is a new layer or an existing layer without a file
                    # so we need to require a file
                    self.add_error('file', 'File is required for this layer type')
                    
        return cleaned_data
    
    def clean_file(self):
        import logging
        logger = logging.getLogger(__name__)
        
        file = self.cleaned_data.get('file')
        if not file:
            logger.info("No file provided in form submission")
            return None
            
        logger.info(f"Validating file: {file.name}, size: {file.size}, content_type: {file.content_type}")
        
        layer_type = self.cleaned_data.get('layer_type')
        logger.info(f"Layer type: {layer_type}")
        
        # Validate file extensions based on layer type, case-insensitive
        if layer_type == 'geojson' and not file.name.lower().endswith(('.json', '.geojson')):
            logger.error(f"Invalid GeoJSON file extension: {file.name}")
            raise forms.ValidationError('Please upload a valid GeoJSON file (.json or .geojson)')
            
        if layer_type == 'kml' and not file.name.lower().endswith(('.kml', '.kmz')):
            logger.error(f"Invalid KML file extension: {file.name}")
            raise forms.ValidationError('Please upload a valid KML file (.kml or .kmz)')
            
        # More permissive check for shapefiles
        if layer_type == 'shapefile':
            if not file.name.lower().endswith(('.shp', '.zip')):
                logger.error(f"Invalid Shapefile extension: {file.name}")
                raise forms.ValidationError('Please upload a valid Shapefile (.shp) or ZIP file containing shapefile components')
        
        # Check file size (max 3GB)
        max_size = 3 * 1024 * 1024 * 1024  # 3GB
        if file.size > max_size:
            raise forms.ValidationError(f'File size should not exceed 3GB (current size: {file.size/1024/1024:.2f}MB)')
        
        return file
        
    def clean_style(self):
        style = self.cleaned_data.get('style')
        if not style:
            return None
            
        # Validate JSON in style field
        try:
            if isinstance(style, str):
                import json
                return json.loads(style)
            return style
        except Exception as e:
            raise forms.ValidationError(f'Invalid JSON format: {str(e)}')
