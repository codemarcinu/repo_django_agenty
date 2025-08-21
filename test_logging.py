#!/usr/bin/env python
"""
Testowy skrypt do sprawdzenia konfiguracji logowania
"""
import os

import django
from django.conf import settings

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings_dev')
django.setup()

import logging


def test_logging():
    print("=== Testing Django Logging Configuration ===")

    # Test different loggers
    loggers_to_test = [
        'chatbot.views',
        'chatbot.services.receipt_service',
        'chatbot.receipt_processor',
        'chatbot.tasks',
        'django'
    ]

    for logger_name in loggers_to_test:
        logger = logging.getLogger(logger_name)
        print(f"\n🧪 Testing logger: {logger_name}")
        print(f"Logger level: {logger.level}")
        print(f"Logger handlers: {[h.__class__.__name__ for h in logger.handlers]}")

        # Test different log levels
        logger.debug(f"DEBUG test message from {logger_name}")
        logger.info(f"INFO test message from {logger_name}")
        logger.warning(f"WARNING test message from {logger_name}")
        logger.error(f"ERROR test message from {logger_name}")

    # Check log files
    print("\n📁 Checking log files:")
    logs_dir = settings.BASE_DIR / 'logs'
    for log_file in logs_dir.glob('*.log'):
        size = log_file.stat().st_size
        print(f"  {log_file.name}: {size} bytes")

        if size > 0:
            print("    Last few lines:")
            with open(log_file, encoding='utf-8') as f:
                lines = f.readlines()
                for line in lines[-3:]:
                    print(f"      {line.strip()}")

if __name__ == "__main__":
    test_logging()
