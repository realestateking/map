"""
Django settings for property_mapper project.
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-key-for-development')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = bool(os.environ.get('DJANGO_DEBUG', True))

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', '.replit.dev', '.repl.co', '.replit.app', 
                'workspace.mbucci8844.repl.co', '48be61ed-b2a1-4541-ae32-dc00d931f7f8-00-1lm1xkyai465y.kirk.replit.dev']

# CSRF settings for Replit
CSRF_TRUSTED_ORIGINS = ['https://*.replit.dev', 'https://*.repl.co', 'https://*.replit.app', 
                        'https://workspace.mbucci8844.repl.co', 
                        'https://48be61ed-b2a1-4541-ae32-dc00d931f7f8-00-1lm1xkyai465y.kirk.replit.dev']

# OneDrive integration settings
ONEDRIVE_CLIENT_ID = os.environ.get('ONEDRIVE_CLIENT_ID', '')
ONEDRIVE_CLIENT_SECRET = os.environ.get('ONEDRIVE_CLIENT_SECRET', '')

# Base URL detection for Replit environment
import os
# Auto-detect the actual domain that's being used
HTTP_HOST = os.environ.get('HTTP_HOST', '')
# If we have an HTTP_HOST environment variable, use that for the base URL
if HTTP_HOST and ('replit.dev' in HTTP_HOST or 'repl.co' in HTTP_HOST or 'replit.app' in HTTP_HOST):
    # Use the host from the HTTP_HOST environment variable
    BASE_URL = f"https://{HTTP_HOST}"
else:
    # Fallback to the workspace URL if HTTP_HOST isn't available or valid
    BASE_URL = "https://48be61ed-b2a1-4541-ae32-dc00d931f7f8-00-1lm1xkyai465y.kirk.replit.dev"

print(f"Using BASE_URL: {BASE_URL}")

# Set the redirect URI to match what's registered in Microsoft Azure
# IMPORTANT: This must match exactly what's configured in the Microsoft app registration
ONEDRIVE_REDIRECT_URI = f"{BASE_URL}/onedrive-callback/"

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # 'django.contrib.gis',  # Temporarily disabled (GeoDjango)
    # 'leaflet',  # Temporarily disabled (requires GeoDjango)
    'maps.apps.MapsConfig',  # Our main application
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'property_mapper.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'property_mapper.wsgi.application'

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('PGDATABASE', 'property_mapper'),
        'USER': os.environ.get('PGUSER', 'postgres'),
        'PASSWORD': os.environ.get('PGPASSWORD', 'postgres'),
        'HOST': os.environ.get('PGHOST', 'localhost'),
        'PORT': os.environ.get('PGPORT', '5432'),
    }
}

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files (Uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Create media directories if they don't exist
import os
if not os.path.exists(MEDIA_ROOT):
    os.makedirs(MEDIA_ROOT)
    
# Create subdirectories for specific upload types
SHAPEFILES_DIR = os.path.join(MEDIA_ROOT, 'shapefiles')
MAP_LAYERS_DIR = os.path.join(MEDIA_ROOT, 'map_layers')
PROPERTY_FILES_DIR = os.path.join(MEDIA_ROOT, 'property_files')

for directory in [SHAPEFILES_DIR, MAP_LAYERS_DIR, PROPERTY_FILES_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Cache settings
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'property-mapper-cache',
    }
}

# File upload settings
# Set high limit for shapefile uploads (3GB)
FILE_UPLOAD_MAX_MEMORY_SIZE = 3 * 1024 * 1024 * 1024  # 3GB
DATA_UPLOAD_MAX_MEMORY_SIZE = 3 * 1024 * 1024 * 1024  # 3GB
FILE_UPLOAD_HANDLERS = [
    'django.core.files.uploadhandler.TemporaryFileUploadHandler',
]  # Force all uploads to disk to handle large files

# GIS libraries configuration (temporarily commented out)
# Note: Using standard PostgreSQL instead of PostGIS while we resolve GeoDjango configuration issues
"""
import subprocess
import os
import glob

# GDAL Configuration
GDAL_LIBRARY_PATH = os.environ.get('GDAL_LIBRARY_PATH', None)
if not GDAL_LIBRARY_PATH:
    try:
        # Try to find the GDAL library path using gdal-config
        gdal_config = subprocess.check_output(['gdal-config', '--prefix']).decode('utf-8').strip()
        potential_paths = [
            os.path.join(gdal_config, 'lib', 'libgdal.so'),
            os.path.join(gdal_config, 'lib64', 'libgdal.so'),
            '/usr/lib/libgdal.so',
            '/usr/lib64/libgdal.so',
            '/usr/local/lib/libgdal.so',
        ]
        
        # Find libgdal.so in nix store
        nix_paths = glob.glob('/nix/store/*/lib/libgdal.so')
        potential_paths.extend(nix_paths)
        
        for path in potential_paths:
            if os.path.exists(path):
                GDAL_LIBRARY_PATH = path
                break
    except Exception as e:
        print(f"Error finding GDAL library path: {e}")

# GEOS Configuration
GEOS_LIBRARY_PATH = os.environ.get('GEOS_LIBRARY_PATH', None)
if not GEOS_LIBRARY_PATH:
    try:
        potential_paths = [
            '/usr/lib/libgeos_c.so',
            '/usr/lib64/libgeos_c.so',
            '/usr/local/lib/libgeos_c.so',
        ]
        
        # Find libgeos_c.so in nix store
        nix_paths = glob.glob('/nix/store/*/lib/libgeos_c.so')
        potential_paths.extend(nix_paths)
        
        for path in potential_paths:
            if os.path.exists(path):
                GEOS_LIBRARY_PATH = path
                break
    except Exception as e:
        print(f"Error finding GEOS library path: {e}")
"""

# Leaflet configuration
LEAFLET_CONFIG = {
    'DEFAULT_CENTER': (45.0, -73.0),
    'DEFAULT_ZOOM': 10,
    'MAX_ZOOM': 20,
    'MIN_ZOOM': 3,
    'SCALE': 'both',
    'ATTRIBUTION_PREFIX': 'Property Mapper',
}

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'maps': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# Auth settings
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# OneDrive settings were moved to the top of this file
print(f"OneDrive redirect URI: {ONEDRIVE_REDIRECT_URI}")
