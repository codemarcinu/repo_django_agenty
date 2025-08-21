"""
Management command to migrate data from chatbot.ReceiptProcessing to inventory.Receipt
This implements the unified Receipt model strategy from the improvement plan.
DEPRECATED: ReceiptProcessing model no longer exists after FAZA 1 completion.
"""

import logging
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migrate data from chatbot.ReceiptProcessing to inventory.Receipt'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run migration in dry-run mode without making changes',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of records to process in each batch',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']

        if dry_run:
            self.stdout.write(
                self.style.WARNING('Running in DRY-RUN mode. No changes will be made.')
            )

        try:
            from chatbot.models import ReceiptProcessing
            from inventory.models import Receipt as InventoryReceipt
        except ImportError as e:
            self.stdout.write(
                self.style.ERROR(f'Import error: {e}')
            )
            return

        # Get total count
        total_receipts = ReceiptProcessing.objects.count()
        self.stdout.write(f'Found {total_receipts} ReceiptProcessing records to migrate')

        if total_receipts == 0:
            self.stdout.write(self.style.SUCCESS('No records to migrate'))
            return

        migrated_count = 0
        skipped_count = 0
        error_count = 0

        # Process in batches
        for offset in range(0, total_receipts, batch_size):
            batch = ReceiptProcessing.objects.all()[offset:offset + batch_size]

            for receipt_processing in batch:
                try:
                    # Check if already migrated
                    existing = InventoryReceipt.objects.filter(
                        source_file_path=receipt_processing.receipt_file.name if receipt_processing.receipt_file else ''
                    ).first()

                    if existing:
                        self.stdout.write(f'Skipping already migrated receipt {receipt_processing.id}')
                        skipped_count += 1
                        continue

                    if not dry_run:
                        with transaction.atomic():
                            # Create new unified Receipt
                            unified_receipt = InventoryReceipt.objects.create(
                                # Map fields from ReceiptProcessing
                                receipt_file=receipt_processing.receipt_file,
                                status=self._map_status(receipt_processing.status),
                                raw_ocr_text=receipt_processing.raw_ocr_text,
                                extracted_data=receipt_processing.extracted_data,
                                error_message=receipt_processing.error_message,
                                uploaded_at=receipt_processing.uploaded_at,
                                processed_at=receipt_processing.processed_at,

                                # Set default values for new fields
                                store_name=self._extract_store_name(receipt_processing),
                                purchased_at=receipt_processing.uploaded_at,  # Fallback
                                total=self._extract_total(receipt_processing),
                                currency='PLN',
                                source_file_path=receipt_processing.receipt_file.name if receipt_processing.receipt_file else '',
                                processing_notes=f'Migrated from ReceiptProcessing ID: {receipt_processing.id}',

                                # Preserve timestamps
                                created_at=receipt_processing.uploaded_at,
                                updated_at=timezone.now(),
                            )

                            self.stdout.write(f'Migrated ReceiptProcessing {receipt_processing.id} -> Receipt {unified_receipt.id}')
                    else:
                        self.stdout.write(f'[DRY-RUN] Would migrate ReceiptProcessing {receipt_processing.id}')

                    migrated_count += 1

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error migrating receipt {receipt_processing.id}: {e}')
                    )
                    error_count += 1
                    logger.error(f'Migration error for receipt {receipt_processing.id}: {e}', exc_info=True)

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f'\nMigration summary:\n'
                f'  Migrated: {migrated_count}\n'
                f'  Skipped: {skipped_count}\n'
                f'  Errors: {error_count}\n'
                f'  Total processed: {migrated_count + skipped_count + error_count}'
            )
        )

        if not dry_run and error_count == 0:
            self.stdout.write(
                self.style.SUCCESS('Migration completed successfully!')
            )
        elif error_count > 0:
            self.stdout.write(
                self.style.WARNING(f'Migration completed with {error_count} errors. Check logs for details.')
            )

    def _map_status(self, old_status):
        """Map ReceiptProcessing status to unified Receipt status"""
        status_mapping = {
            'uploaded': 'uploaded',
            'ocr_in_progress': 'ocr_in_progress',
            'ocr_done': 'ocr_done',
            'llm_in_progress': 'llm_in_progress',
            'llm_done': 'llm_done',
            'ready_for_review': 'ready_for_review',
            'completed': 'completed',
            'error': 'error',
        }
        return status_mapping.get(old_status, 'uploaded')

    def _extract_store_name(self, receipt_processing):
        """Extract store name from extracted data"""
        if receipt_processing.extracted_data:
            return receipt_processing.extracted_data.get('store_name', '')
        return ''

    def _extract_total(self, receipt_processing):
        """Extract total amount from extracted data"""
        if receipt_processing.extracted_data:
            total = receipt_processing.extracted_data.get('total_amount')
            if total:
                try:
                    return Decimal(str(total))
                except:
                    pass
        return None
