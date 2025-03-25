import os
import pandas as pd
import xml.etree.ElementTree as ET
from zipfile import ZipFile
import tempfile
import shutil
from io import BytesIO
import re

from django.contrib.gis.geos import Point, Polygon

import logging
logger = logging.getLogger(__name__)


def parse_excel_file(file_path):
    """Parse an Excel file and return a list of property data dictionaries."""
    try:
        # Read Excel file
        df = pd.read_excel(file_path)
        
        # Drop completely empty rows
        df = df.dropna(how='all')
        
        # Convert to list of dictionaries
        records = df.to_dict('records')
        
        # Clean and standardize column names
        cleaned_records = []
        for record in records:
            cleaned_record = {}
            for key, value in record.items():
                if pd.notna(value):  # Skip NaN values
                    # Clean key name: lowercase, replace spaces with underscores
                    clean_key = slugify_field_name(str(key))
                    cleaned_record[clean_key] = value
            
            # Ensure required fields
            if 'lot_number' in cleaned_record:
                cleaned_records.append(cleaned_record)
        
        return cleaned_records
    except Exception as e:
        logger.error(f"Error parsing Excel file: {str(e)}")
        raise


def slugify_field_name(field_name):
    """Convert a field name to a standard format."""
    # Replace common variations of field names
    replacements = {
        'lot #': 'lot_number',
        'lot no': 'lot_number',
        'lot number': 'lot_number',
        'lot_no': 'lot_number',
        'matricule': 'matricule_number',
        'matricule #': 'matricule_number',
        'pin': 'matricule_number',
        'address': 'address',
        'street address': 'address',
        'city': 'city',
        'postal code': 'postal_code',
        'zip': 'postal_code',
        'zip code': 'postal_code',
        'property type': 'property_type',
        'type': 'property_type',
        'land area': 'land_area',
        'lot area': 'land_area',
        'building area': 'building_area',
        'year built': 'year_built',
        'constructed': 'year_built',
        'owner': 'owner',
        'owner name': 'owner',
        'value': 'assessed_value',
        'assessed value': 'assessed_value',
        'lat': 'latitude',
        'latitude': 'latitude',
        'long': 'longitude',
        'lng': 'longitude',
        'longitude': 'longitude',
    }
    
    # Convert to lowercase and check for known replacements
    field_lower = field_name.lower().strip()
    for key, replacement in replacements.items():
        if field_lower == key or field_lower.startswith(key + ' '):
            return replacement
    
    # Default: convert to snake_case
    return re.sub(r'[^a-z0-9]+', '_', field_lower).strip('_')


def parse_kml_file(file_path):
    """Parse a KML file and extract property geometries."""
    result = []
    
    try:
        # Check if it's a KMZ file (zipped KML)
        if file_path.lower().endswith('.kmz'):
            with tempfile.TemporaryDirectory() as temp_dir:
                with ZipFile(file_path, 'r') as kmz:
                    kmz.extractall(temp_dir)
                    
                    # Find the KML file inside the extracted directory
                    kml_files = [f for f in os.listdir(temp_dir) if f.lower().endswith('.kml')]
                    if not kml_files:
                        raise ValueError("No KML file found inside KMZ archive")
                    
                    kml_path = os.path.join(temp_dir, kml_files[0])
                    return parse_kml_content(kml_path)
        else:
            # Regular KML file
            return parse_kml_content(file_path)
    except Exception as e:
        logger.error(f"Error parsing KML file: {str(e)}")
        raise


def parse_kml_content(kml_path):
    """Parse the actual KML content and extract placemarks."""
    result = []
    
    try:
        # Register KML namespaces
        namespaces = {
            'kml': 'http://www.opengis.net/kml/2.2',
            'gx': 'http://www.google.com/kml/ext/2.2'
        }
        
        # Parse the KML file
        tree = ET.parse(kml_path)
        root = tree.getroot()
        
        # Find all Placemark elements
        placemarks = root.findall('.//kml:Placemark', namespaces)
        
        for placemark in placemarks:
            placemark_data = {}
            
            # Extract name
            name_elem = placemark.find('kml:name', namespaces)
            if name_elem is not None and name_elem.text:
                placemark_data['name'] = name_elem.text.strip()
            
            # Extract description
            desc_elem = placemark.find('kml:description', namespaces)
            if desc_elem is not None and desc_elem.text:
                placemark_data['description'] = desc_elem.text.strip()
            
            # Extract Point coordinates
            point_elem = placemark.find('.//kml:Point/kml:coordinates', namespaces)
            if point_elem is not None and point_elem.text:
                coords_text = point_elem.text.strip()
                coords = coords_text.split(',')
                if len(coords) >= 2:
                    try:
                        lon, lat = float(coords[0]), float(coords[1])
                        placemark_data['point'] = (lon, lat)
                    except ValueError:
                        pass
            
            # Extract Polygon coordinates
            polygon_elem = placemark.find('.//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates', namespaces)
            if polygon_elem is not None and polygon_elem.text:
                coords_text = polygon_elem.text.strip()
                coords_list = []
                
                # Parse the coordinate string
                for coord_group in coords_text.split():
                    if not coord_group.strip():
                        continue
                    
                    coords = coord_group.split(',')
                    if len(coords) >= 2:
                        try:
                            lon, lat = float(coords[0]), float(coords[1])
                            coords_list.append((lon, lat))
                        except ValueError:
                            pass
                
                if coords_list:
                    placemark_data['polygon'] = coords_list
            
            # Add to results if we have useful data
            if 'name' in placemark_data and ('point' in placemark_data or 'polygon' in placemark_data):
                result.append(placemark_data)
        
        return result
    except Exception as e:
        logger.error(f"Error parsing KML content: {str(e)}")
        raise
