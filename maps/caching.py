"""
Advanced caching and optimization systems for large map layer handling.

This module provides caching, chunking, and optimization functionality to
allow the system to handle very large shapefiles and many map layers efficiently.
"""
import os
import io
import json
import logging
import hashlib
import time
import threading
import multiprocessing
import zipfile
from functools import lru_cache
from pathlib import Path
from django.core.cache import cache
from django.conf import settings

# Set up logging
logger = logging.getLogger(__name__)

# Cache configuration
MEMORY_CACHE_SIZE_LIMIT = 1024 * 1024 * 10  # 10MB max size for memory cache
FILE_CACHE_DIR = os.path.join('media', 'cache', 'shapefiles')
FILE_CACHE_EXPIRY = 60 * 60 * 24 * 7  # 7 days
MEMORY_CACHE_EXPIRY = {
    # Different expiry times based on zoom levels (in seconds)
    'far': 60 * 60 * 24,     # 24 hours for far zoom levels (< 8)
    'medium': 60 * 60 * 6,   # 6 hours for medium zoom levels (8-12)
    'close': 60 * 60 * 2,    # 2 hours for close zoom levels (13-15)
    'detailed': 60 * 60,     # 1 hour for very detailed zoom levels (16+)
    'default': 60 * 60 * 12  # 12 hours default
}


# Ensure cache directory exists
os.makedirs(FILE_CACHE_DIR, exist_ok=True)


def get_zoom_category(zoom_level):
    """Get the zoom category for a specific zoom level."""
    if zoom_level is None:
        return 'default'
    zoom = int(zoom_level)
    if zoom < 8:
        return 'far'
    elif zoom < 13:
        return 'medium'
    elif zoom < 16:
        return 'close'
    else:
        return 'detailed'


def get_cache_expiry(zoom_level):
    """Get the cache expiry time for a specific zoom level."""
    category = get_zoom_category(zoom_level)
    return MEMORY_CACHE_EXPIRY.get(category, MEMORY_CACHE_EXPIRY['default'])


def get_cache_key(layer_id, simplify, max_features, zoom=None):
    """Generate a cache key for layer data with specific parameters."""
    params = f"{layer_id}:{simplify}:{max_features}:{zoom}"
    return f"shapefile_data_{hashlib.md5(params.encode()).hexdigest()}"


def get_file_cache_path(cache_key):
    """Get the path to a file cache entry."""
    return os.path.join(FILE_CACHE_DIR, f"{cache_key}.geojson")


def is_in_memory_cache(cache_key):
    """Check if a key is in the memory cache."""
    return cache.get(cache_key) is not None


def is_in_file_cache(cache_key):
    """Check if a key is in the file cache."""
    cache_file = get_file_cache_path(cache_key)
    if os.path.exists(cache_file):
        # Check if file is not too old
        file_age = time.time() - os.path.getmtime(cache_file)
        if file_age < FILE_CACHE_EXPIRY:
            return True
        else:
            # File exists but is expired, remove it
            try:
                os.remove(cache_file)
            except OSError:
                logger.error(f"Failed to remove expired cache file: {cache_file}")
    return False


def get_from_memory_cache(cache_key):
    """Get data from memory cache."""
    return cache.get(cache_key)


def get_from_file_cache(cache_key):
    """Get data from file cache."""
    cache_file = get_file_cache_path(cache_key)
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading cache file {cache_file}: {e}")
    return None


def save_to_memory_cache(cache_key, data, expiry):
    """Save data to memory cache."""
    cache.set(cache_key, data, expiry)


def save_to_file_cache(cache_key, data):
    """Save data to file cache."""
    cache_file = get_file_cache_path(cache_key)
    try:
        with open(cache_file, 'w') as f:
            f.write(data)
        return True
    except Exception as e:
        logger.error(f"Error writing to cache file {cache_file}: {e}")
        return False


def get_cached_layer_data(layer_id, simplify, max_features, zoom=None):
    """Get layer data from cache if available."""
    cache_key = get_cache_key(layer_id, simplify, max_features, zoom)
    
    # Try memory cache first (fastest)
    data = get_from_memory_cache(cache_key)
    if data:
        logger.info(f"Memory cache hit for layer {layer_id}")
        return data, 'memory'
    
    # Try file cache next
    data = get_from_file_cache(cache_key)
    if data:
        logger.info(f"File cache hit for layer {layer_id}")
        
        # Put in memory cache for faster access next time
        expiry = get_cache_expiry(zoom)
        save_to_memory_cache(cache_key, data, expiry)
        
        return data, 'file'
    
    # Not in any cache
    return None, None


def cache_layer_data(layer_id, data, simplify, max_features, zoom=None):
    """Cache layer data in appropriate caches based on size."""
    cache_key = get_cache_key(layer_id, simplify, max_features, zoom)
    data_size = len(data)
    
    # Log caching operation
    logger.info(f"Caching {data_size / (1024*1024):.2f} MB of data for layer {layer_id}")
    
    # Always cache in file for persistence
    file_cached = save_to_file_cache(cache_key, data)
    
    # Only cache in memory if not too large
    if data_size <= MEMORY_CACHE_SIZE_LIMIT:
        expiry = get_cache_expiry(zoom)
        save_to_memory_cache(cache_key, data, expiry)
        if file_cached:
            logger.info(f"Layer {layer_id} cached in both memory and file")
            return 'both'
        else:
            logger.info(f"Layer {layer_id} cached in memory only")
            return 'memory'
    else:
        logger.info(f"Layer {layer_id} cached in file only (too large for memory)")
        return 'file' if file_cached else None


def clear_layer_cache(layer_id=None):
    """Clear cache for a specific layer or all layers."""
    # Clear memory cache for the layer
    if layer_id:
        pattern = f"shapefile_data_{layer_id}_*"
        # Django cache doesn't support pattern deletion natively, so we'd need
        # a different cache backend or another approach for this
        logger.info(f"Memory cache pattern clearing not supported - layer {layer_id}")
        
        # Clear file cache for the layer
        for file in os.listdir(FILE_CACHE_DIR):
            if file.startswith(f"shapefile_data_{layer_id}_"):
                os.remove(os.path.join(FILE_CACHE_DIR, file))
        logger.info(f"File cache cleared for layer {layer_id}")
    else:
        # Clear all shapefile data from memory cache
        # This is a simplification - in production we'd need a more targeted approach
        logger.info("Full memory cache clearing not supported")
        
        # Clear all file cache
        for file in os.listdir(FILE_CACHE_DIR):
            if file.startswith("shapefile_data_"):
                os.remove(os.path.join(FILE_CACHE_DIR, file))
        logger.info("All file cache cleared")