"""
Django management command to enable and test ReceiptProcessorV2.
"""

import asyncio
import logging
from django.core.management.base import BaseCommand
from django.conf import settings

from chatbot.services.receipt_processor_v2 import create_receipt_processor
from chatbot.services.receipt_processor_adapter import receipt_processor_adapter
from chatbot.config.receipt_config import get_config

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Enable and test ReceiptProcessorV2'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-config',
            action='store_true',
            help='Test configuration validation',
        )
        parser.add_argument(
            '--test-services',
            action='store_true',
            help='Test service initialization',
        )
        parser.add_argument(
            '--enable',
            action='store_true',
            help='Enable ReceiptProcessorV2 (updates settings)',
        )
        parser.add_argument(
            '--status',
            action='store_true',
            help='Show current processor status',
        )

    def handle(self, *args, **options):
        if options['test_config']:
            self._test_configuration()
        
        if options['test_services']:
            asyncio.run(self._test_services())
        
        if options['enable']:
            self._enable_processor_v2()
        
        if options['status']:
            self._show_status()
        
        if not any(options.values()):
            self._show_status()

    def _test_configuration(self):
        """Test configuration validation."""
        self.stdout.write("Testing configuration...")
        
        try:
            config = get_config()
            is_valid, errors = config.validate()
            
            if is_valid:
                self.stdout.write(
                    self.style.SUCCESS("✅ Configuration is valid")
                )
                self.stdout.write(f"Config summary: {config.to_dict()}")
            else:
                self.stdout.write(
                    self.style.ERROR("❌ Configuration validation failed:")
                )
                for error in errors:
                    self.stdout.write(f"  - {error}")
                    
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Configuration test failed: {e}")
            )

    async def _test_services(self):
        """Test service initialization."""
        self.stdout.write("Testing service initialization...")
        
        try:
            # Test processor creation
            processor = create_receipt_processor()
            
            # Test service status
            status_info = processor.get_status_info()
            self.stdout.write(
                self.style.SUCCESS("✅ ReceiptProcessorV2 initialized successfully")
            )
            self.stdout.write(f"Processor info: {status_info}")
            
            # Test cleanup
            await processor.cleanup()
            self.stdout.write(
                self.style.SUCCESS("✅ Service cleanup completed")
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Service test failed: {e}")
            )
            logger.exception("Service test error")

    def _enable_processor_v2(self):
        """Enable ReceiptProcessorV2 in settings."""
        self.stdout.write("Enabling ReceiptProcessorV2...")
        
        # Check if already enabled
        current_setting = getattr(settings, 'USE_RECEIPT_PROCESSOR_V2', False)
        
        if current_setting:
            self.stdout.write(
                self.style.WARNING("⚠️ ReceiptProcessorV2 is already enabled")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "⚠️ Cannot modify settings at runtime. "
                    "Please add 'USE_RECEIPT_PROCESSOR_V2 = True' to your settings.py"
                )
            )
        
        self._show_status()

    def _show_status(self):
        """Show current processor status."""
        self.stdout.write("Current Receipt Processor Status:")
        self.stdout.write("-" * 40)
        
        try:
            # Check adapter status
            processor_info = receipt_processor_adapter.get_processor_info()
            
            version = processor_info.get('version', 'unknown')
            use_v2_enabled = processor_info.get('use_v2_enabled', False)
            v2_available = processor_info.get('v2_available', False)
            
            if version == 'v2':
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Active: ReceiptProcessorV2")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"⚠️ Active: ReceiptProcessor (legacy)")
                )
            
            self.stdout.write(f"USE_RECEIPT_PROCESSOR_V2 setting: {use_v2_enabled}")
            self.stdout.write(f"V2 available: {v2_available}")
            
            # Show configuration if V2 is active
            if version == 'v2' and 'config' in processor_info:
                self.stdout.write("\nV2 Configuration:")
                config = processor_info['config']
                for section, settings_dict in config.items():
                    self.stdout.write(f"  {section}:")
                    for key, value in settings_dict.items():
                        self.stdout.write(f"    {key}: {value}")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error getting status: {e}")
            )

    def _check_dependencies(self):
        """Check if all dependencies are available."""
        self.stdout.write("Checking dependencies...")
        
        dependencies = [
            ('redis', 'Redis cache support'),
            ('easyocr', 'OCR processing'),
            ('fitz', 'PDF processing'),
        ]
        
        for module_name, description in dependencies:
            try:
                __import__(module_name)
                self.stdout.write(f"✅ {description}: Available")
            except ImportError:
                self.stdout.write(f"❌ {description}: Not available (optional)")