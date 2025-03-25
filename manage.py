#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def ensure_directories_exist():
    """Ensure all necessary directories exist for the application."""
    directories = [
        'media',
        'media/property_files',
        'media/map_layers',
        'media/shapefiles',
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            print(f"Creating directory: {directory}")
            os.makedirs(directory, exist_ok=True)


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'property_mapper.settings')
    
    # Create necessary directories
    ensure_directories_exist()
    
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
