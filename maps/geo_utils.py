"""
Custom geographic utilities to replace GeoDjango functionality
This module provides simple Point and Polygon classes to store geographic data
without requiring the full GeoDjango/PostGIS stack.
"""
import json
import math

class Point:
    """Simple class to replace GeoDjango Point functionality"""
    
    def __init__(self, x, y, srid=4326):
        self.x = float(x)  # longitude
        self.y = float(y)  # latitude
        self.srid = srid
    
    def __str__(self):
        return f"POINT({self.x} {self.y})"
    
    def as_dict(self):
        return {
            'type': 'Point',
            'coordinates': [self.x, self.y]
        }
    
    def to_json(self):
        return json.dumps(self.as_dict())
    
    @property
    def longitude(self):
        return self.x
    
    @property
    def latitude(self):
        return self.y


class Polygon:
    """Simple class to replace GeoDjango Polygon functionality"""
    
    def __init__(self, coordinates, srid=4326):
        """
        Initialize with list of coordinate tuples [(x1, y1), (x2, y2), ...]
        Coordinates should form a closed polygon (first and last points should match)
        """
        self.coordinates = []
        for coord in coordinates:
            if isinstance(coord, (list, tuple)) and len(coord) >= 2:
                self.coordinates.append((float(coord[0]), float(coord[1])))
        
        # Ensure the polygon is closed (first and last points match)
        if self.coordinates and self.coordinates[0] != self.coordinates[-1]:
            self.coordinates.append(self.coordinates[0])
        
        self.srid = srid
    
    def __str__(self):
        coords_str = ", ".join([f"{x} {y}" for x, y in self.coordinates])
        return f"POLYGON(({coords_str}))"
    
    def as_dict(self):
        return {
            'type': 'Polygon',
            'coordinates': [self.coordinates]
        }
    
    def to_json(self):
        return json.dumps(self.as_dict())


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    # Radius of earth in kilometers
    r = 6371
    return c * r


def point_in_radius(point, center_lat, center_lon, radius_km):
    """Check if a point is within a certain radius of a center point"""
    if not point:
        return False
    
    # Get point coordinates
    if hasattr(point, 'latitude') and hasattr(point, 'longitude'):
        lat = point.latitude
        lon = point.longitude
    elif isinstance(point, (list, tuple)) and len(point) >= 2:
        lon, lat = point[0], point[1]
    else:
        return False
    
    # Calculate distance
    distance = haversine_distance(center_lat, center_lon, lat, lon)
    return distance <= radius_km