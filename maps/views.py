from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse, FileResponse
from django.db.models import Q
from django.views.decorators.cache import cache_page
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
import math  # Required for Haversine formula in radius search
import json
import os
import tempfile

from .models import Region, Property, PropertyDataFile, MapLayer
from .forms import PropertySearchForm, FileUploadForm, MapLayerForm
from .services import process_property_file
from .ml_models import predict_property_height, predict_property_quality
from .onedrive import get_onedrive_client

import logging
logger = logging.getLogger(__name__)


def index(request):
    """Main page with interactive map."""
    regions = Region.objects.all()
    search_form = PropertySearchForm(request.GET or None)
    
    # Get default region or first region in the database
    default_region = regions.filter(name__icontains='default').first() or regions.first()
    
    context = {
        'regions': regions,
        'default_region': default_region,
        'search_form': search_form,
    }
    return render(request, 'maps/index.html', context)


def search_properties(request):
    """Handle property search requests."""
    search_form = PropertySearchForm(request.GET or None)
    properties = None
    
    if search_form.is_valid():
        search_type = search_form.cleaned_data['search_type']
        region = search_form.cleaned_data['region']
        property_type = search_form.cleaned_data['property_type']
        
        # Base query
        query = Property.objects.all()
        
        # Filter by region if provided
        if region:
            query = query.filter(region=region)
        
        # Filter by property type if provided
        if property_type:
            query = query.filter(property_type=property_type)
        
        # Search based on search type
        if search_type == 'lot':
            lot_number = search_form.cleaned_data['lot_number']
            query = query.filter(
                Q(lot_number__icontains=lot_number) | 
                Q(matricule_number__icontains=lot_number)
            )
        
        elif search_type == 'address':
            address = search_form.cleaned_data['address']
            query = query.filter(
                Q(address__icontains=address) |
                Q(city__icontains=address) |
                Q(postal_code__icontains=address)
            )
        
        elif search_type == 'radius':
            latitude = search_form.cleaned_data['latitude']
            longitude = search_form.cleaned_data['longitude']
            radius = search_form.cleaned_data['radius']
            
            # We'll calculate distances manually with Python since we don't have GeoDjango
            # Get all properties with coordinates
            properties_with_coords = []
            
            for prop in query.filter(latitude__isnull=False, longitude__isnull=False):
                # Calculate distance using Haversine formula
                dlat = math.radians(prop.latitude - latitude)
                dlon = math.radians(prop.longitude - longitude)
                a = math.sin(dlat/2)**2 + math.cos(math.radians(latitude)) * math.cos(math.radians(prop.latitude)) * math.sin(dlon/2)**2
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                distance = 6371 * c  # Earth radius in km
                
                if distance <= radius:
                    properties_with_coords.append(prop.id)
            
            # Filter by list of IDs within the radius
            query = query.filter(id__in=properties_with_coords)
        
        properties = query.order_by('lot_number')
    
    # Paginate results
    paginator = Paginator(properties or [], 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Handle AJAX request
        property_list = []
        for prop in page_obj:
            property_data = {
                'id': prop.id,
                'lot_number': prop.lot_number,
                'address': prop.address or 'N/A',
                'property_type': prop.property_type or 'N/A',
                'detail_url': reverse('property_detail', args=[prop.id]),
            }
            
            # Include location data if available
            if prop.latitude is not None and prop.longitude is not None:
                property_data['latitude'] = prop.latitude
                property_data['longitude'] = prop.longitude
            
            property_list.append(property_data)
        
        return JsonResponse({
            'properties': property_list,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'page_number': page_obj.number,
            'total_pages': paginator.num_pages,
            'total_count': paginator.count,
        })
    
    context = {
        'search_form': search_form,
        'properties': page_obj,
    }
    return render(request, 'maps/search_results.html', context)


def property_detail(request, property_id):
    """Show detailed information about a specific property."""
    property = get_object_or_404(Property, id=property_id)
    
    # Get neighboring properties
    neighbors = []
    if property.latitude is not None and property.longitude is not None:
        # Find properties within 1km using similar approach to the radius search
        nearby_properties = Property.objects.filter(
            latitude__isnull=False, 
            longitude__isnull=False
        ).exclude(id=property.id)
        
        for prop in nearby_properties:
            # Calculate distance using Haversine formula
            dlat = math.radians(prop.latitude - property.latitude)
            dlon = math.radians(prop.longitude - property.longitude)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(property.latitude)) * math.cos(math.radians(prop.latitude)) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            distance = 6371 * c  # Earth radius in km
            
            if distance <= 1:  # Within 1km
                # Store the property and its distance
                prop.distance = distance
                neighbors.append(prop)
                
        # Sort by distance and limit to 5
        neighbors = sorted(neighbors, key=lambda p: p.distance)[:5]
    
    context = {
        'property': property,
        'neighbors': neighbors,
        'attributes': property.attributes.all(),
    }
    return render(request, 'maps/property_detail.html', context)


@login_required
def admin_dashboard(request):
    """Admin dashboard for managing data and uploads."""
    # Count statistics
    region_count = Region.objects.count()
    property_count = Property.objects.count()
    file_count = PropertyDataFile.objects.count()
    layer_count = MapLayer.objects.count()
    
    # Recent files
    recent_files = PropertyDataFile.objects.order_by('-uploaded_at')[:5]
    
    # Recent properties
    recent_properties = Property.objects.order_by('-created_at')[:5]
    
    # Map layers
    map_layers = MapLayer.objects.order_by('-updated_at')[:10]
    
    context = {
        'region_count': region_count,
        'property_count': property_count,
        'file_count': file_count,
        'layer_count': layer_count,
        'recent_files': recent_files,
        'recent_properties': recent_properties,
        'map_layers': map_layers,
    }
    return render(request, 'maps/admin_dashboard.html', context)


@login_required
def upload_file(request):
    """Handle file uploads (Excel or KML)."""
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # Save the file with the current user
            file_obj = form.save(commit=False)
            file_obj.uploaded_by = request.user
            file_obj.save()
            
            # Process the file in the background
            try:
                process_property_file(file_obj)
                messages.success(request, f"File '{file_obj.title}' successfully uploaded and processed.")
            except Exception as e:
                logger.error(f"Error processing file {file_obj.id}: {str(e)}")
                messages.error(request, f"File uploaded but could not be processed: {str(e)}")
            
            return redirect('admin_dashboard')
    else:
        form = FileUploadForm()
    
    context = {
        'form': form,
        'regions': Region.objects.all(),
    }
    return render(request, 'maps/upload.html', context)


@login_required
def process_ml(request, property_id):
    """Process ML predictions for a property."""
    property = get_object_or_404(Property, id=property_id)
    
    try:
        # Run ML predictions
        height = predict_property_height(property)
        quality = predict_property_quality(property)
        
        # Update property with predictions
        property.predicted_height = height
        property.predicted_quality_score = quality
        property.save()
        
        messages.success(request, "ML predictions successfully processed.")
    except Exception as e:
        logger.error(f"Error processing ML for property {property_id}: {str(e)}")
        messages.error(request, f"Could not process ML predictions: {str(e)}")
    
    return redirect('property_detail', property_id=property_id)


@cache_page(60 * 15)  # Cache for 15 minutes
def region_properties(request, region_id):
    """API endpoint to get properties for a specific region."""
    properties = Property.objects.filter(region_id=region_id)
    
    property_list = []
    for prop in properties:
        if prop.latitude is not None and prop.longitude is not None:
            property_data = {
                'id': prop.id,
                'lot_number': prop.lot_number,
                'address': prop.address or 'N/A',
                'property_type': prop.property_type or 'N/A',
                'latitude': prop.latitude,
                'longitude': prop.longitude,
                'detail_url': reverse('property_detail', args=[prop.id]),
            }
            property_list.append(property_data)
    
    return JsonResponse({'properties': property_list})


@cache_page(60 * 15)  # Cache for 15 minutes
def map_layers_list(request):
    """API endpoint to get available map layers."""
    region_id = request.GET.get('region_id')
    
    # Base query for active layers
    query = MapLayer.objects.filter(is_active=True)
    
    # Filter by region if provided
    if region_id:
        query = query.filter(Q(region_id=region_id) | Q(region__isnull=True))
    
    layers = []
    for layer in query.order_by('is_base_layer', '-z_index', 'name'):
        layer_data = {
            'id': layer.id,
            'name': layer.name,
            'description': layer.description,
            'layer_type': layer.layer_type,
            'is_base_layer': layer.is_base_layer,
            'is_visible_by_default': layer.is_visible_by_default,
            'z_index': layer.z_index,
        }
        
        # Add URL for remote layers
        if layer.url:
            layer_data['url'] = layer.url
            
        # Add style information if available
        if layer.style:
            layer_data['style'] = layer.style
            
        layers.append(layer_data)
    
    return JsonResponse({'layers': layers})


def map_layer_data(request, layer_id):
    """API endpoint to get the data for a specific map layer."""
    import logging
    import hashlib
    import os
    from django.core.cache import cache
    
    logger = logging.getLogger(__name__)
    
    layer = get_object_or_404(MapLayer, id=layer_id, is_active=True)
    
    # Get simplification parameter for large datasets
    simplify = request.GET.get('simplify', 'auto')
    max_features = request.GET.get('max_features')
    zoom = request.GET.get('zoom')
    
    if max_features:
        try:
            max_features = int(max_features)
        except ValueError:
            max_features = None
    
    # Handle different layer types
    if layer.layer_type == 'shapefile':
        # For shapefiles, convert to GeoJSON
        try:
            # Generate cache key based on parameters
            cache_params = f"{layer_id}:{simplify}:{max_features}:{zoom}"
            cache_key = f"shapefile_data_{hashlib.md5(cache_params.encode()).hexdigest()}"
            
            # Try to get from cache first
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.info(f"Using cached GeoJSON for layer {layer_id} with params: {simplify}, {max_features}, zoom={zoom}")
                response = HttpResponse(cached_data, content_type='application/json')
                if zoom:
                    response['Cache-Control'] = f'max-age=1800'  # Cache for 30 minutes when zoom-specific
                else:
                    response['Cache-Control'] = 'max-age=3600'  # Cache for 1 hour otherwise
                response['X-Cache'] = 'HIT'
                return response
                
            # Also try file-based cache for very large files
            cache_dir = os.path.join('media', 'cache', 'shapefiles')
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, f"{cache_key}.geojson")
            
            if os.path.exists(cache_file):
                logger.info(f"Using file-cached GeoJSON for layer {layer_id}")
                with open(cache_file, 'r') as f:
                    cached_data = f.read()
                response = HttpResponse(cached_data, content_type='application/json')
                if zoom:
                    response['Cache-Control'] = f'max-age=1800'
                else:
                    response['Cache-Control'] = 'max-age=3600'
                response['X-Cache'] = 'FILE-HIT'
                return response
                
            # Not in cache, generate the data
            logger.info(f"Cache miss for layer {layer_id}, generating GeoJSON")
            
            # Store the request temporarily on the model instance for access to zoom parameter
            layer._current_request = request
            
            geojson_data = layer.get_geojson_data(simplify=simplify, max_features=max_features)
            
            # Clean up the temporary reference
            delattr(layer, '_current_request')
            
            if geojson_data:
                # Cache the result (in memory for smaller results, file for larger)
                data_size = len(geojson_data)
                if data_size < 1024 * 1024 * 5:  # 5MB limit for memory cache
                    # Cache time varies by zoom level - longer cache for less detailed views
                    if zoom and int(zoom) < 12:
                        cache_time = 60 * 60 * 24  # 24 hours for far-out zooms
                    elif zoom:
                        cache_time = 60 * 60 * 2   # 2 hours for closer zooms
                    else:
                        cache_time = 60 * 60 * 12  # 12 hours default
                    
                    cache.set(cache_key, geojson_data, cache_time)
                    logger.info(f"Cached {data_size/1024/1024:.2f}MB of GeoJSON in memory for {cache_time/60/60:.1f} hours")
                else:
                    # For very large results, use file-based caching
                    with open(cache_file, 'w') as f:
                        f.write(geojson_data)
                    logger.info(f"Cached {data_size/1024/1024:.2f}MB of GeoJSON to file: {cache_file}")
                
                # Enable gzip compression for large responses
                response = HttpResponse(geojson_data, content_type='application/json')
                # Add cache headers for better performance - use shorter cache for dynamic zoom-dependent data
                if zoom:
                    response['Cache-Control'] = f'max-age=1800'  # Cache for 30 minutes when zoom-specific
                else:
                    response['Cache-Control'] = 'max-age=3600'  # Cache for 1 hour otherwise
                response['X-Cache'] = 'MISS'
                return response
            else:
                logger.error(f"Failed to get GeoJSON data for layer {layer_id}")
                return JsonResponse({'error': 'Could not process shapefile'}, status=500)
        except Exception as e:
            logger.exception(f"Error serving shapefile layer {layer_id}: {str(e)}")
            return JsonResponse({'error': f'Error processing shapefile: {str(e)}'}, status=500)
            
    elif layer.layer_type in ['geojson', 'kml']:
        # For file-based layers, serve the file directly
        if layer.file:
            response = FileResponse(layer.file)
            response['Cache-Control'] = 'max-age=3600'  # Cache for 1 hour
            return response
        else:
            return JsonResponse({'error': 'No file available'}, status=404)
            
    else:
        # For URL-based layers (WMS, tile), just return the layer info
        return JsonResponse({
            'id': layer.id,
            'name': layer.name,
            'layer_type': layer.layer_type,
            'url': layer.url,
            'style': layer.style,
        })


@login_required
def map_layer_list(request):
    """List all map layers with management options."""
    layers = MapLayer.objects.all().order_by('-updated_at')
    
    context = {
        'layers': layers,
        'regions': Region.objects.all(),
    }
    return render(request, 'maps/map_layer_list.html', context)


@login_required
def add_map_layer(request):
    """Add a new map layer."""
    import logging
    logger = logging.getLogger(__name__)
    
    # Check for pending OneDrive upload after authentication
    pending_layer_data = request.session.get('pending_layer_data')
    if pending_layer_data and pending_layer_data.get('onedrive_authenticated'):
        logger.info(f"Found pending OneDrive upload after authentication: {pending_layer_data}")
        messages.info(
            request, 
            "Your OneDrive authentication was successful. Please reselect your file and continue the upload process."
        )
        # Keep the authentication status but remove the form data which might be stale
        request.session['pending_layer_data'] = {
            'onedrive_authenticated': True
        }
        request.session.modified = True
    
    if request.method == 'POST':
        # Debug the POST data for troubleshooting
        logger.info(f"POST data: {dict(request.POST)}")
        logger.info(f"FILES data: {dict(request.FILES)}")
        
        # Extra file validation
        if 'file' in request.FILES:
            uploaded_file = request.FILES['file']
            logger.info(f"Uploaded file details - Name: {uploaded_file.name}, Size: {uploaded_file.size}, Content-Type: {uploaded_file.content_type}")
            
            # Check if the file is a zip file by examining the content
            if uploaded_file.name.lower().endswith('.zip'):
                try:
                    # Read the first few bytes to check magic number for ZIP
                    header = uploaded_file.read(4)
                    # Reset file pointer
                    uploaded_file.seek(0)
                    
                    if header != b'PK\x03\x04':
                        logger.error(f"File {uploaded_file.name} has .zip extension but wrong ZIP header: {header}")
                        messages.error(request, "The uploaded ZIP file appears to be corrupted. Please check the file and try again.")
                except Exception as file_check_err:
                    logger.error(f"Error checking ZIP file header: {file_check_err}")
        
        # Force z_index if it's missing
        if 'z_index' not in request.POST or not request.POST['z_index']:
            post_data = request.POST.copy()
            post_data['z_index'] = '0'
            form = MapLayerForm(post_data, request.FILES)
        else:
            form = MapLayerForm(request.POST, request.FILES)
        
        try:
            # First check if the form is valid
            if form.is_valid():
                # Form is valid, access cleaned_data
                if 'z_index' not in form.cleaned_data or form.cleaned_data.get('z_index') is None:
                    form.cleaned_data['z_index'] = 0
                
                # Save the layer with the current user
                layer = form.save(commit=False)
                layer.uploaded_by = request.user
                
                # Set z_index explicitly to avoid validation errors
                if not layer.z_index and layer.z_index != 0:
                    layer.z_index = 0
                
                # For shapefile layer, check file is present and valid
                if layer.layer_type == 'shapefile':
                    # Check if we should use OneDrive for large files
                    storage_type = request.POST.get('storage_type', 'local')
                    file_obj = request.FILES.get('file')
                    
                    if storage_type == 'local':
                        if not file_obj:
                            messages.error(request, "You must upload a file for shapefile layers")
                            form.add_error('file', 'File is required for shapefile layers')
                            raise ValueError("Missing required file for shapefile layer")
                        
                        # Additional check for zip file integrity
                        if file_obj.name.lower().endswith('.zip'):
                            try:
                                # Try to use zipfile to validate
                                import zipfile
                                import io
                                
                                # Create in-memory file for validation
                                in_memory_file = io.BytesIO(file_obj.read())
                                # Reset file pointer
                                file_obj.seek(0)
                                
                                if not zipfile.is_zipfile(in_memory_file):
                                    messages.error(request, "The uploaded ZIP file is invalid or corrupted. Please check the file and try again.")
                                    form.add_error('file', 'Invalid or corrupted ZIP file')
                                    raise ValueError("Invalid ZIP file format")
                                
                                # Check ZIP contents
                                with zipfile.ZipFile(in_memory_file) as test_zip:
                                    file_list = test_zip.namelist()
                                    shp_files = [f for f in file_list if f.lower().endswith('.shp')]
                                    
                                    if not shp_files:
                                        messages.error(request, "The ZIP file doesn't contain any shapefile (.shp) components.")
                                        form.add_error('file', 'ZIP file does not contain any .shp files')
                                        raise ValueError("No .shp files found in ZIP")
                                    
                                    logger.info(f"Valid ZIP file with shapefiles: {shp_files}")
                                
                                # Reset file pointer again after validation
                                file_obj.seek(0)
                                
                            except zipfile.BadZipFile as zip_err:
                                logger.error(f"Bad ZIP file: {zip_err}")
                                messages.error(request, "The uploaded ZIP file is corrupted. Please check the file and try again.")
                                form.add_error('file', f'Corrupted ZIP file: {str(zip_err)}')
                                raise ValueError(f"Bad ZIP file: {str(zip_err)}")
                            except Exception as other_zip_err:
                                logger.error(f"Error validating ZIP: {other_zip_err}")
                                messages.error(request, f"Error validating ZIP file: {str(other_zip_err)}")
                                form.add_error('file', f'Error processing ZIP: {str(other_zip_err)}')
                                raise ValueError(f"ZIP validation error: {str(other_zip_err)}")
                    
                    elif storage_type == 'onedrive':
                        # User has selected OneDrive storage option
                        logger.info(f"Processing OneDrive storage option for layer '{layer.name}'")
                        
                        if file_obj:
                            # Check if OneDrive client is authenticated first
                            from maps.onedrive import get_onedrive_client
                            onedrive_client = get_onedrive_client()
                            
                            # Check if we already have authenticated during this session
                            onedrive_already_authenticated = (
                                request.session.get('pending_layer_data', {}).get('onedrive_authenticated', False)
                            )
                            
                            logger.info(f"OneDrive status - Already authenticated in session: {onedrive_already_authenticated}")
                            
                            if not (onedrive_client.is_authenticated() or onedrive_already_authenticated):
                                logger.info(f"OneDrive client not authenticated. Saving form data and redirecting to auth.")
                                # Store important upload information in session
                                request.session['pending_layer_data'] = {
                                    'form_data': {k: v for k, v in request.POST.items()},
                                    'layer_name': layer.name,
                                    'file_name': file_obj.name,
                                    'file_size': file_obj.size,
                                    'content_type': file_obj.content_type,
                                }
                                
                                # Show a clear message
                                messages.info(
                                    request, 
                                    "Your file needs to be uploaded to OneDrive. " +
                                    "You'll be redirected to Microsoft to authorize this application. " +
                                    "After authorization, please try uploading the file again."
                                )
                                
                                # Redirect to OneDrive authentication view
                                logger.info("Redirecting to OneDrive authentication.")
                                return redirect('onedrive_auth')
                            
                            try:
                                # OneDrive is authenticated, continue with upload
                                logger.info(f"OneDrive client authenticated. Processing file upload to OneDrive.")
                                
                                # Write the uploaded file to a temporary location
                                import os
                                import tempfile
                                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_obj.name)[1]) as temp_file:
                                    for chunk in file_obj.chunks():
                                        temp_file.write(chunk)
                                    temp_path = temp_file.name
                                
                                # Upload the file to OneDrive
                                logger.info(f"Uploading {temp_path} to OneDrive")
                                
                                # Show a message about large file upload
                                messages.info(
                                    request,
                                    f"Uploading {file_obj.name} ({file_obj.size/1024/1024:.1f} MB) to OneDrive. " +
                                    "This may take some time for large files."
                                )
                                
                                # Upload to a folder specifically for this map layer
                                folder_path = f"/property_mapper_layers/{layer.name.replace(' ', '_')}"
                                result = onedrive_client.upload_file(temp_path, folder_path)
                                
                                # Clean up the temporary file
                                os.unlink(temp_path)
                                
                                if not result:
                                    messages.error(request, "Failed to upload file to OneDrive")
                                    raise ValueError("OneDrive upload failed")
                                
                                # Set OneDrive file info in the model
                                layer.storage_type = 'onedrive'
                                layer.onedrive_file_id = result.get('id', '')
                                layer.onedrive_file_name = file_obj.name
                                
                                # Get download URL (temporary, will need to be refreshed)
                                download_url = onedrive_client.get_download_url(result.get('id', ''))
                                if download_url:
                                    layer.onedrive_file_url = download_url
                                
                                logger.info(f"File uploaded to OneDrive with ID: {layer.onedrive_file_id}")
                                
                            except Exception as onedrive_err:
                                logger.error(f"OneDrive upload error: {str(onedrive_err)}")
                                messages.error(request, f"Error uploading to OneDrive: {str(onedrive_err)}")
                                raise ValueError(f"OneDrive upload error: {str(onedrive_err)}")
                        else:
                            messages.error(request, "You must upload a file for shapefile layers")
                            form.add_error('file', 'File is required even when using OneDrive storage')
                            raise ValueError("Missing required file for shapefile layer with OneDrive storage")
                
                # Save the model to generate an ID and process the file
                layer.save()
                
                # Process shapefile if necessary (will be called in the model's save method)
                
                # Clear any pending layer data from session after successful upload
                if 'pending_layer_data' in request.session:
                    logger.info("Clearing pending layer data from session after successful upload")
                    request.session.pop('pending_layer_data', None)
                    request.session.modified = True
                
                messages.success(request, f"Map layer '{layer.name}' successfully added.")
                return redirect('map_layer_list')
            else:
                # Debug form errors with detailed information
                error_details = {}
                for field, errors in form.errors.items():
                    error_details[field] = str(errors)
                    
                logger.error(f"Form validation errors: {error_details}")
                
                # Check for issues with file upload specifically
                if 'file' in form.errors:
                    file_field = request.FILES.get('file')
                    if file_field:
                        logger.error(f"File upload validation failed for {file_field.name}, size: {file_field.size}, content_type: {file_field.content_type}")
                
                logger.error(f"Form errors: {error_details}")
                # More detailed debugging
                logger.error(f"Form data: {form.data}")
                logger.error(f"Form cleaned_data: {getattr(form, 'cleaned_data', None)}")
                
                # Display more specific message
                error_message = "Please correct the form errors below."
                messages.error(request, error_message)
        except ValueError as ve:
            # These are validation errors we've raised ourselves
            logger.error(f"Validation error: {str(ve)}")
            # Error message already added in the code above
        except Exception as e:
            # Log any exceptions that occur during save
            logger.error(f"Error saving map layer: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            messages.error(request, f"Error creating map layer: {str(e)}")
    else:
        form = MapLayerForm()
    
    context = {
        'form': form,
        'regions': Region.objects.all(),
        'is_add': True,
    }
    return render(request, 'maps/map_layer_form.html', context)


@login_required
def edit_map_layer(request, layer_id):
    """Edit an existing map layer."""
    layer = get_object_or_404(MapLayer, id=layer_id)
    
    if request.method == 'POST':
        # Debug the POST data for troubleshooting
        logger.info(f"EDIT - POST data: {dict(request.POST)}")
        logger.info(f"EDIT - FILES data: {dict(request.FILES)}")
        
        # Extra file validation for edits
        if 'file' in request.FILES:
            uploaded_file = request.FILES['file']
            logger.info(f"EDIT - Uploaded file details - Name: {uploaded_file.name}, Size: {uploaded_file.size}, Content-Type: {uploaded_file.content_type}")
            
            # Check if the file is a zip file by examining the content
            if uploaded_file.name.lower().endswith('.zip'):
                try:
                    # Read the first few bytes to check magic number for ZIP
                    header = uploaded_file.read(4)
                    # Reset file pointer
                    uploaded_file.seek(0)
                    
                    if header != b'PK\x03\x04':
                        logger.error(f"EDIT - File {uploaded_file.name} has .zip extension but wrong ZIP header: {header}")
                        messages.error(request, "The uploaded ZIP file appears to be corrupted. Please check the file and try again.")
                except Exception as file_check_err:
                    logger.error(f"EDIT - Error checking ZIP file header: {file_check_err}")
        
        # Force z_index if it's missing
        if 'z_index' not in request.POST or not request.POST['z_index']:
            post_data = request.POST.copy()
            post_data['z_index'] = '0'
            form = MapLayerForm(post_data, request.FILES, instance=layer)
        else:
            form = MapLayerForm(request.POST, request.FILES, instance=layer)
        
        # Import zipfile module at top level to avoid unbound errors
        import zipfile
        import io
        
        try:
            # First check if the form is valid
            if form.is_valid():
                # Form is valid, access cleaned_data
                if 'z_index' not in form.cleaned_data or form.cleaned_data.get('z_index') is None:
                    form.cleaned_data['z_index'] = 0
                
                # Additional validation for shapefile layer uploads during edit
                if layer.layer_type == 'shapefile' and 'file' in request.FILES:
                    file_obj = request.FILES.get('file')
                    if file_obj.name.lower().endswith('.zip'):
                        try:
                            # Try to use zipfile to validate
                            import zipfile
                            import io
                            
                            # Create in-memory file for validation
                            in_memory_file = io.BytesIO(file_obj.read())
                            # Reset file pointer
                            file_obj.seek(0)
                            
                            if not zipfile.is_zipfile(in_memory_file):
                                messages.error(request, "The uploaded ZIP file is invalid or corrupted. Please check the file and try again.")
                                form.add_error('file', 'Invalid or corrupted ZIP file')
                                raise ValueError("Invalid ZIP file format")
                            
                            # Check ZIP contents
                            with zipfile.ZipFile(in_memory_file) as test_zip:
                                file_list = test_zip.namelist()
                                shp_files = [f for f in file_list if f.lower().endswith('.shp')]
                                
                                if not shp_files:
                                    messages.error(request, "The ZIP file doesn't contain any shapefile (.shp) components.")
                                    form.add_error('file', 'ZIP file does not contain any .shp files')
                                    raise ValueError("No .shp files found in ZIP")
                                
                                logger.info(f"EDIT - Valid ZIP file with shapefiles: {shp_files}")
                            
                            # Reset file pointer again after validation
                            file_obj.seek(0)
                            
                        except zipfile.BadZipFile as zip_err:
                            logger.error(f"EDIT - Bad ZIP file: {zip_err}")
                            messages.error(request, "The uploaded ZIP file is corrupted. Please check the file and try again.")
                            form.add_error('file', f'Corrupted ZIP file: {str(zip_err)}')
                            raise ValueError(f"Bad ZIP file: {str(zip_err)}")
                        except Exception as other_zip_err:
                            logger.error(f"EDIT - Error validating ZIP: {other_zip_err}")
                            messages.error(request, f"Error validating ZIP file: {str(other_zip_err)}")
                            form.add_error('file', f'Error processing ZIP: {str(other_zip_err)}')
                            raise ValueError(f"ZIP validation error: {str(other_zip_err)}")
                
                # Save the model with z_index explicitly set to avoid validation errors
                layer_obj = form.save(commit=False)
                if not layer_obj.z_index and layer_obj.z_index != 0:
                    layer_obj.z_index = 0
                layer_obj.save()
                
                messages.success(request, f"Map layer '{layer.name}' successfully updated.")
                return redirect('map_layer_list')
            else:
                # Debug form errors
                error_details = {}
                for field, errors in form.errors.items():
                    error_details[field] = str(errors)
                
                logger.error(f"EDIT - Form errors: {error_details}")
                
                # Check for issues with file upload specifically
                if 'file' in form.errors:
                    file_field = request.FILES.get('file')
                    if file_field:
                        logger.error(f"EDIT - File upload validation failed for {file_field.name}, size: {file_field.size}, content_type: {file_field.content_type}")
                
                # More detailed debugging
                logger.error(f"EDIT - Form data: {form.data}")
                logger.error(f"EDIT - Form cleaned_data: {getattr(form, 'cleaned_data', None)}")
                
                # Display more specific message
                error_message = "Please correct the form errors below."
                messages.error(request, error_message)
        except ValueError as ve:
            # These are validation errors we've raised ourselves
            logger.error(f"EDIT - Validation error: {str(ve)}")
            # Error message already added in the code above
        except Exception as e:
            # Log any exceptions that occur during save
            logger.error(f"Error updating map layer: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            messages.error(request, f"Error updating map layer: {str(e)}")
    else:
        form = MapLayerForm(instance=layer)
    
    context = {
        'form': form,
        'layer': layer,
        'regions': Region.objects.all(),
        'is_add': False,
    }
    return render(request, 'maps/map_layer_form.html', context)


@login_required
def delete_map_layer(request, layer_id):
    """Delete a map layer."""
    layer = get_object_or_404(MapLayer, id=layer_id)
    
    if request.method == 'POST':
        layer_name = layer.name
        layer.delete()
        messages.success(request, f"Map layer '{layer_name}' successfully deleted.")
        return redirect('map_layer_list')
    
    context = {
        'layer': layer,
    }
    return render(request, 'maps/map_layer_confirm_delete.html', context)
