import os
import multiprocessing

from celery import Celery

# Set the multiprocessing start method to 'spawn' for CUDA compatibility
# This must be done before any other imports that might initialize CUDA
try:
    multiprocessing.set_start_method('spawn', force=True)
except RuntimeError:
    # set_start_method can only be called once, ignore if already set
    pass

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("agenty")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
