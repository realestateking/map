import os
import pandas as pd
import xml.etree.ElementTree as ET
from zipfile import ZipFile
from io import BytesIO
import json

# Use regular Django instead of GeoDjango
from django.db import transaction
from django.utils.text import slugify

from .models import Property, PropertyAttribute, PropertyDataFile, Region
from .parsers import parse_kml_file, parse_excel_file
from .geo_utils import Point, Polygon

import logging
logger = logging.getLogger(__name__)


def process_property_file(file_obj):
    """Process uploaded property files (Excel or KML)."""
    try:
        if file_obj.processed:
            logger.info(f"File {file_obj.id} already processed, skipping")
            return
        
        if file_obj.file_type == 'excel':
            process_excel_file(file_obj)
        elif file_obj.file_type == 'kml':
            process_kml_file(file_obj)
        
        # Mark as processed
        file_obj.processed = True
        file_obj.save()
        
        logger.info(f"Successfully processed file {file_obj.id}")
    except Exception as e:
        logger.error(f"Error processing file {file_obj.id}: {str(e)}")
        file_obj.processing_errors = str(e)
        file_obj.save()
        raise


def process_excel_file(file_obj):
    """Process an Excel file containing property data."""
    data = parse_excel_file(file_obj.file.path)
    
    if not data:
        raise ValueError("No valid data found in the Excel file")
    
    with transaction.atomic():
        for row in data:
            # Create or update property
            property_data = {
                'lot_number': row.get('lot_number', ''),
                'matricule_number': row.get('matricule_number'),
                'address': row.get('address'),
                'city': row.get('city'),
                'postal_code': row.get('postal_code'),
                'property_type': row.get('property_type'),
                'land_area': row.get('land_area'),
                'building_area': row.get('building_area'),
                'year_built': row.get('year_built'),
                'owner': row.get('owner'),
                'assessed_value': row.get('assessed_value'),
                'region': file_obj.region,
                'source_file': file_obj,
            }
            
            # Handle location if lat/lng are provided
            if row.get('latitude') and row.get('longitude'):
                try:
                    # Store coordinates as simple lat/lng fields
                    property_data['latitude'] = float(row['latitude'])
                    property_data['longitude'] = float(row['longitude'])
                except (ValueError, TypeError):
                    # Skip location if coordinates are invalid
                    pass
            
            # Try to find existing property to update
            property, created = Property.objects.update_or_create(
                lot_number=property_data['lot_number'],
                region=file_obj.region,
                defaults=property_data
            )
            
            # Process additional attributes
            for key, value in row.items():
                if key not in property_data and value is not None:
                    PropertyAttribute.objects.update_or_create(
                        property=property,
                        name=key,
                        defaults={'value': str(value)}
                    )


def process_kml_file(file_obj):
    """Process a KML file containing property geometry data."""
    kml_data = parse_kml_file(file_obj.file.path)
    
    if not kml_data:
        raise ValueError("No valid data found in the KML file")
    
    with transaction.atomic():
        for placemark in kml_data:
            # Extract property identifier
            lot_number = placemark.get('name', '').strip()
            if not lot_number:
                continue  # Skip entries without a valid lot number
            
            # Find the corresponding property
            try:
                property = Property.objects.get(
                    lot_number=lot_number,
                    region=file_obj.region
                )
                
                # Update with geometric data
                if placemark.get('point'):
                    # Store coordinates as simple lat/lng fields
                    property.longitude = placemark['point'][0]
                    property.latitude = placemark['point'][1]
                
                if placemark.get('polygon'):
                    # Store polygon as JSON string in boundary_coordinates
                    coords = placemark['polygon']
                    if coords and len(coords) >= 4:  # Must have at least 4 points for a valid polygon
                        property.boundary_coordinates = json.dumps(coords)
                
                # Save description as an attribute if present
                if placemark.get('description'):
                    PropertyAttribute.objects.update_or_create(
                        property=property,
                        name='kml_description',
                        defaults={'value': placemark['description']}
                    )
                
                property.save()
                
            except Property.DoesNotExist:
                logger.warning(f"Property with lot number {lot_number} not found in region {file_obj.region}")
            except Exception as e:
                logger.error(f"Error updating property {lot_number}: {str(e)}")
