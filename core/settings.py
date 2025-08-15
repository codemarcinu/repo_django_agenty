# Default development settings import
# This file serves as the main entry point for Django settings
# It defaults to development settings unless explicitly configured otherwise

import os

# Determine which settings to use based on environment
DJANGO_SETTINGS_MODULE = os.environ.get('DJANGO_SETTINGS_MODULE', 'core.settings_dev')

if DJANGO_SETTINGS_MODULE == 'core.settings_dev':
    from .settings_dev import *
elif DJANGO_SETTINGS_MODULE == 'core.settings_prod':
    from .settings_prod import *
elif DJANGO_SETTINGS_MODULE == 'core.settings':
    # If someone explicitly sets DJANGO_SETTINGS_MODULE to core.settings,
    # default to development settings
    from .settings_dev import *
else:
    raise ImportError(f"Unknown settings module: {DJANGO_SETTINGS_MODULE}")