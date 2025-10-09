"""
ASGI config for Tracker_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/asgi/
"""

import os
environment = os.getenv('ENV_CLASSIFICATION', 'local')
print(f"Initializing WSGI environment: {environment}")

# Dynamically set settings module based on environment
if environment == 'prod':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Tracker_backend.settings-prod')
elif environment == 'test':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Tracker_backend.settings-test')
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Tracker_backend.settings')
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Tracker_backend.settings')

application = get_asgi_application()
