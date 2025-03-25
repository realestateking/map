"""
WSGI config for property_mapper project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'property_mapper.settings')

application = get_wsgi_application()
