from django.contrib import admin
from .models import Region, PropertyDataFile, Property, PropertyAttribute, MapLayer
from .services import process_property_file

# Note: Using standard ModelAdmin instead of OSMGeoAdmin


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ('name', 'center_latitude', 'center_longitude', 'default_zoom')
    search_fields = ('name',)


class PropertyAttributeInline(admin.TabularInline):
    model = PropertyAttribute
    extra = 1


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('lot_number', 'address', 'city', 'property_type', 'region')
    list_filter = ('region', 'property_type', 'city')
    search_fields = ('lot_number', 'matricule_number', 'address')
    inlines = [PropertyAttributeInline]
    readonly_fields = ('predicted_height', 'predicted_quality_score')


@admin.register(PropertyDataFile)
class PropertyDataFileAdmin(admin.ModelAdmin):
    list_display = ('title', 'file_type', 'region', 'uploaded_by', 'uploaded_at', 'processed')
    list_filter = ('file_type', 'region', 'processed')
    search_fields = ('title', 'description')
    readonly_fields = ('processed', 'processing_errors')
    
    actions = ['process_selected_files']
    
    def process_selected_files(self, request, queryset):
        processed_count = 0
        for file_obj in queryset.filter(processed=False):
            try:
                process_property_file(file_obj)
                processed_count += 1
            except Exception as e:
                self.message_user(request, f"Error processing {file_obj.title}: {str(e)}", level='error')
        
        if processed_count > 0:
            self.message_user(request, f"Successfully processed {processed_count} files.")
    
    process_selected_files.short_description = "Process selected files"


admin.site.register(PropertyAttribute)


@admin.register(MapLayer)
class MapLayerAdmin(admin.ModelAdmin):
    list_display = ('name', 'layer_type', 'region', 'is_active', 'is_base_layer', 'z_index')
    list_filter = ('layer_type', 'region', 'is_active', 'is_base_layer')
    search_fields = ('name', 'description')
    readonly_fields = ('shapefile_dir',)
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'layer_type', 'region')
        }),
        ('Layer Source', {
            'fields': ('url', 'file', 'shapefile_dir')
        }),
        ('Display Options', {
            'fields': ('style', 'z_index', 'is_active', 'is_visible_by_default', 'is_base_layer')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Override save_model to set the uploaded_by field"""
        if not change:  # Only set uploaded_by on creation
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)
        
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'layer_type' in form.base_fields:
            field = form.base_fields['layer_type']
            
            # Add help text based on layer type
            help_texts = {
                'shapefile': 'Upload a ZIP file containing all shapefile components (.shp, .dbf, .prj, etc)',
                'geojson': 'Upload a GeoJSON file (.json or .geojson)',
                'kml': 'Upload a KML or KMZ file',
                'wms': 'Enter the WMS service URL',
                'tile': 'Enter the tile service URL template'
            }
            
            # Update help text for file field when layer type changes
            if 'file' in form.base_fields:
                file_field = form.base_fields['file']
                
                # Update help text based on selected layer type
                if obj and obj.layer_type:
                    file_field.help_text = help_texts.get(obj.layer_type, '')
        
        return form
