import json
from django.core.serializers import serialize
from django.core.serializers.json import DjangoJSONEncoder

class GeoJSONEncoder(DjangoJSONEncoder):
    """Extended JSON encoder for serialization."""
    def default(self, obj):
        return super().default(obj)


def properties_to_geojson(properties):
    """Convert property objects to GeoJSON format."""
    features = []
    
    for prop in properties:
        # Skip properties without coordinates
        if prop.latitude is None or prop.longitude is None:
            continue
        
        feature = {
            "type": "Feature",
            "properties": {
                "id": prop.id,
                "lot_number": prop.lot_number,
                "address": prop.address or "N/A",
                "property_type": prop.property_type or "N/A",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [prop.longitude, prop.latitude]  # GeoJSON uses [longitude, latitude] order
            }
        }
        
        # Add boundary if available
        if prop.boundary_coordinates:
            try:
                # Try to parse the boundary coordinates from JSON stored in text field
                boundary_geojson = json.loads(prop.boundary_coordinates)
                # Replace the point geometry with the boundary geometry
                feature["geometry"] = boundary_geojson
            except (json.JSONDecodeError, TypeError):
                # If parsing fails, keep the point geometry
                pass
        
        features.append(feature)
    
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    return geojson


def safe_convert_to_float(value, default=None):
    """Safely convert a value to float."""
    if value is None:
        return default
    
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_convert_to_int(value, default=None):
    """Safely convert a value to integer."""
    if value is None:
        return default
    
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def get_color_for_value(value, min_value, max_value, color_scheme='viridis'):
    """Generate a color for a value within a range.
    
    Args:
        value (float): The value to convert to a color
        min_value (float): The minimum value in the range
        max_value (float): The maximum value in the range
        color_scheme (str): Color scheme name ('viridis', 'plasma', 'inferno', etc.)
        
    Returns:
        str: A hex color code
    """
    try:
        import numpy as np
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors
        
        # Normalize the value
        if min_value == max_value:
            normalized = 0.5  # Avoid division by zero
        else:
            normalized = (value - min_value) / (max_value - min_value)
            normalized = max(0, min(1, normalized))  # Clamp to [0, 1]
        
        # Get color map
        cmap = plt.get_cmap(color_scheme)
        
        # Convert to hex
        rgb = cmap(normalized)[:3]  # Get RGB values (ignore alpha)
        hex_color = mcolors.rgb2hex(rgb)
        
        return hex_color
    
    except (ImportError, ValueError, TypeError):
        # Fallback to a simple gradient from red to green
        if min_value == max_value:
            normalized = 0.5
        else:
            normalized = (value - min_value) / (max_value - min_value)
            normalized = max(0, min(1, normalized))
        
        # Simple red to green gradient
        r = int(255 * (1 - normalized))
        g = int(255 * normalized)
        b = 0
        
        return f'#{r:02x}{g:02x}{b:02x}'
