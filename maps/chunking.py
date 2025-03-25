"""
Chunking and advanced optimization for handling large shapefiles efficiently.

This module provides functions to:
1. Split large shapefiles into manageable chunks based on geographic boundaries
2. Apply adaptive simplification based on zoom level and feature complexity
3. Implement progressive loading of shapefile features
"""

import os
import math
import json
import logging
import shapefile
import numpy as np
from django.conf import settings
from maps.caching import get_cached_layer_data, cache_layer_data

# Set up logging
logger = logging.getLogger(__name__)

# Constants for chunking
MAX_FEATURES_PER_CHUNK = 5000
MAX_CHUNKS = 20

def chunk_shapefile(shapefile_path, max_features_per_chunk=MAX_FEATURES_PER_CHUNK):
    """
    Split a large shapefile into geographic chunks for more efficient loading
    
    Args:
        shapefile_path: Path to the source shapefile
        max_features_per_chunk: Maximum features per geographic chunk
        
    Returns:
        list: List of dictionaries with chunk info
    """
    logger.info(f"Splitting shapefile {shapefile_path} into chunks")
    
    # Open the shapefile
    reader = shapefile.Reader(shapefile_path)
    
    # Get total number of shapes
    total_shapes = len(reader.shapes())
    logger.info(f"Total shapes in file: {total_shapes}")
    
    if total_shapes <= max_features_per_chunk:
        # No need to chunk if it's already small enough
        logger.info("Shapefile small enough, no chunking needed")
        return [{
            'chunk_id': 'full',
            'bbox': reader.bbox,
            'feature_count': total_shapes,
            'shapefile_path': shapefile_path
        }]
    
    # Get bounding box for the entire shapefile
    full_bbox = reader.bbox
    x_min, y_min, x_max, y_max = full_bbox
    
    # Calculate how many chunks we need in each dimension
    # We aim for roughly square chunks
    total_chunks_needed = math.ceil(total_shapes / max_features_per_chunk)
    chunks_per_side = math.ceil(math.sqrt(total_chunks_needed))
    
    # Don't create too many chunks as it causes overhead
    chunks_per_side = min(chunks_per_side, MAX_CHUNKS // 2)
    
    # Calculate chunk width and height
    chunk_width = (x_max - x_min) / chunks_per_side
    chunk_height = (y_max - y_min) / chunks_per_side
    
    # Create grid of bounding boxes
    chunks = []
    for i in range(chunks_per_side):
        for j in range(chunks_per_side):
            chunk_x_min = x_min + i * chunk_width
            chunk_y_min = y_min + j * chunk_height
            chunk_x_max = chunk_x_min + chunk_width
            chunk_y_max = chunk_y_min + chunk_height
            
            chunk_bbox = (chunk_x_min, chunk_y_min, chunk_x_max, chunk_y_max)
            
            # Count features in this chunk (approximate approach)
            # This is an estimate only - exact count would be too expensive
            chunk_id = f"chunk_{i}_{j}"
            
            chunks.append({
                'chunk_id': chunk_id,
                'bbox': chunk_bbox,
                'estimated_feature_count': total_shapes // (chunks_per_side * chunks_per_side),
                'shapefile_path': shapefile_path
            })
    
    logger.info(f"Created {len(chunks)} geographic chunks")
    return chunks

def extract_chunk_features(shapefile_path, bbox, max_features=None, simplify_factor=None):
    """
    Extract features from a shapefile that are within a specific bounding box
    
    Args:
        shapefile_path: Path to the shapefile
        bbox: Bounding box (x_min, y_min, x_max, y_max)
        max_features: Maximum number of features to extract
        simplify_factor: Factor for simplification (0.0-1.0)
        
    Returns:
        dict: GeoJSON FeatureCollection
    """
    logger.info(f"Extracting features from {shapefile_path} within bbox {bbox}")
    
    # Open the shapefile
    reader = shapefile.Reader(shapefile_path)
    
    # Initialize GeoJSON structure
    geojson = {
        "type": "FeatureCollection",
        "features": []
    }
    
    # Get shapes, records, and fields
    shapes = reader.shapes()
    records = reader.records()
    fields = reader.fields[1:]  # Skip the deletion flag field
    field_names = [field[0] for field in fields]
    
    # Function to convert shapefile record to a property dict
    def record_to_properties(record):
        properties = {}
        for i, value in enumerate(record):
            if i < len(field_names):
                properties[field_names[i]] = value
        return properties
    
    # Function to check if a point is within the bbox
    def point_in_bbox(point, bbox):
        x, y = point
        x_min, y_min, x_max, y_max = bbox
        return x_min <= x <= x_max and y_min <= y <= y_max
    
    # Function to check if any point of a shape is within the bbox
    def shape_intersects_bbox(shape_points, bbox):
        return any(point_in_bbox(point, bbox) for point in shape_points)
    
    # Process shapes
    feature_count = 0
    for i, shape in enumerate(shapes):
        # Skip if we've reached our limit
        if max_features and feature_count >= max_features:
            break
        
        # Skip null shapes
        if not shape.points:
            continue
        
        # Check if shape intersects with the bbox
        if not shape_intersects_bbox(shape.points, bbox):
            continue
        
        # Apply simplification if needed
        shape_points = shape.points
        if simplify_factor and simplify_factor > 0:
            # Simple simplification algorithm (similar to Douglas-Peucker)
            if len(shape_points) > 10:
                # Calculate number of points to keep based on simplification factor
                keep_count = max(3, int(len(shape_points) * (1 - simplify_factor)))
                
                # Keep key points (start, end, and evenly distributed points)
                simplified_points = [shape_points[0]]
                if keep_count < len(shape_points):
                    step = len(shape_points) / keep_count
                    for j in range(1, keep_count - 1):
                        idx = min(int(j * step), len(shape_points) - 1)
                        simplified_points.append(shape_points[idx])
                else:
                    simplified_points = shape_points
                
                # Add last point
                if len(shape_points) > 1:
                    simplified_points.append(shape_points[-1])
                
                shape_points = simplified_points
        
        # Create GeoJSON feature
        feature = {
            "type": "Feature",
            "properties": record_to_properties(records[i]),
            "geometry": {
                "type": None,
                "coordinates": None
            }
        }
        
        # Determine geometry type and format coordinates
        if shape.shapeType == shapefile.POINT:
            feature["geometry"]["type"] = "Point"
            feature["geometry"]["coordinates"] = shape_points[0]
        elif shape.shapeType == shapefile.POLYLINE:
            feature["geometry"]["type"] = "LineString"
            feature["geometry"]["coordinates"] = shape_points
        elif shape.shapeType == shapefile.POLYGON:
            feature["geometry"]["type"] = "Polygon"
            # Handle polygon parts correctly
            if hasattr(shape, 'parts') and len(shape.parts) > 1:
                # Multiple parts - need to separate
                parts = []
                for j in range(len(shape.parts)):
                    start = shape.parts[j]
                    end = shape.parts[j+1] if j+1 < len(shape.parts) else len(shape_points)
                    parts.append(shape_points[start:end])
                feature["geometry"]["coordinates"] = parts
            else:
                # Single part polygon
                feature["geometry"]["coordinates"] = [shape_points]
        else:
            # Skip unsupported shape types
            continue
        
        # Add feature to collection
        geojson["features"].append(feature)
        feature_count += 1
    
    # Add metadata about the chunk
    geojson["chunk_info"] = {
        "bbox": bbox,
        "feature_count": feature_count,
        "simplification": simplify_factor
    }
    
    logger.info(f"Extracted {feature_count} features from chunk")
    
    return geojson

def get_visible_chunks_for_bbox(chunks, view_bbox, zoom_level):
    """
    Get chunks that are visible within the current map view
    
    Args:
        chunks: List of chunks
        view_bbox: Current view bounding box
        zoom_level: Current zoom level
        
    Returns:
        list: List of visible chunks
    """
    # Function to check if bboxes overlap
    def bboxes_overlap(bbox1, bbox2):
        x1_min, y1_min, x1_max, y1_max = bbox1
        x2_min, y2_min, x2_max, y2_max = bbox2
        
        # Check if one bbox is completely to the left/right/above/below the other
        if x1_max < x2_min or x1_min > x2_max or y1_max < y2_min or y1_min > y2_max:
            return False
        return True
    
    visible_chunks = []
    for chunk in chunks:
        if bboxes_overlap(chunk['bbox'], view_bbox):
            # Calculate relevance score based on overlap percentage
            # Higher score = more important to load first
            visible_chunks.append(chunk)
    
    # Sort chunks by relevance (most relevant first)
    # In a real implementation, we'd calculate overlap percentage here
    # For now, we'll just return all visible chunks
    
    logger.info(f"Found {len(visible_chunks)} visible chunks of {len(chunks)} total")
    return visible_chunks

def get_chunk_key(layer_id, chunk_id, simplify, max_features, zoom=None):
    """Generate a cache key for a specific chunk."""
    return f"chunk_{layer_id}_{chunk_id}_{simplify}_{max_features}_{zoom}"

def process_layer_in_chunks(layer, view_bbox, zoom_level, simplify='auto', max_features=None):
    """
    Process a MapLayer by chunking it and only loading visible chunks
    
    Args:
        layer: MapLayer instance
        view_bbox: Current view bounding box
        zoom_level: Current zoom level
        simplify: Simplification factor or 'auto'
        max_features: Maximum features to include
        
    Returns:
        str: GeoJSON string with visible chunks
    """
    # Get shapefile path
    if not layer.shapefile_dir or not os.path.isdir(layer.shapefile_dir):
        logger.error(f"No valid shapefile directory for layer {layer.id}")
        return None
    
    shp_files = [f for f in os.listdir(layer.shapefile_dir) if f.lower().endswith('.shp')]
    if not shp_files:
        logger.error(f"No .shp files found in {layer.shapefile_dir}")
        return None
    
    shapefile_path = os.path.join(layer.shapefile_dir, shp_files[0])
    
    # Generate chunks if not already done
    chunks = chunk_shapefile(shapefile_path)
    
    # Get visible chunks
    visible_chunks = get_visible_chunks_for_bbox(chunks, view_bbox, zoom_level)
    
    # Calculate simplification factor (if auto)
    if simplify == 'auto':
        if zoom_level < 8:
            simplify_factor = 0.05  # Very zoomed out
        elif zoom_level < 10:
            simplify_factor = 0.02
        elif zoom_level < 12:
            simplify_factor = 0.01
        elif zoom_level < 14:
            simplify_factor = 0.005
        elif zoom_level < 16:
            simplify_factor = 0.002
        else:
            simplify_factor = 0.0  # No simplification when zoomed in
    else:
        try:
            simplify_factor = float(simplify)
        except ValueError:
            simplify_factor = 0.0
    
    # Determine max features per chunk based on zoom
    if max_features is None:
        if zoom_level < 8:
            chunk_max_features = 1000
        elif zoom_level < 10:
            chunk_max_features = 2000
        elif zoom_level < 12:
            chunk_max_features = 3000
        elif zoom_level < 14:
            chunk_max_features = 4000
        else:
            chunk_max_features = 5000
    else:
        # If total max features specified, divide among chunks
        chunk_max_features = max(1000, max_features // max(1, len(visible_chunks)))
    
    # Process each visible chunk
    all_features = []
    
    for chunk in visible_chunks:
        # Check for cached chunk
        chunk_key = get_chunk_key(
            layer.id, chunk['chunk_id'], simplify_factor, chunk_max_features, zoom_level
        )
        
        cached_chunk, cache_type = get_cached_layer_data(chunk_key, simplify_factor, chunk_max_features, zoom_level)
        
        if cached_chunk:
            # Use cached chunk
            chunk_data = json.loads(cached_chunk)
            all_features.extend(chunk_data["features"])
        else:
            # Process chunk
            chunk_data = extract_chunk_features(
                chunk['shapefile_path'], 
                chunk['bbox'],
                max_features=chunk_max_features,
                simplify_factor=simplify_factor
            )
            
            # Cache chunk for future use
            cache_layer_data(chunk_key, json.dumps(chunk_data), simplify_factor, chunk_max_features, zoom_level)
            
            # Add features to result
            all_features.extend(chunk_data["features"])
    
    # Create combined GeoJSON
    combined = {
        "type": "FeatureCollection",
        "features": all_features,
        "info": {
            "total_features": sum(c.get('estimated_feature_count', 0) for c in chunks),
            "included_features": len(all_features),
            "visible_chunks": len(visible_chunks),
            "total_chunks": len(chunks),
            "simplification": simplify_factor,
            "zoom_level": zoom_level
        }
    }
    
    logger.info(f"Processed layer {layer.id} with {len(all_features)} features from {len(visible_chunks)} chunks")
    
    return json.dumps(combined)