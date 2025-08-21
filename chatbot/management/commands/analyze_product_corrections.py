# chatbot/management/commands/analyze_product_corrections.py

import logging

from django.core.management.base import BaseCommand
from django.db.models import Count

from chatbot.models import ProductCorrection
from inventory.models import Product

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Analyzes ProductCorrection entries and adds frequent corrections as product aliases.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--threshold',
            type=int,
            default=10,
            help='Minimum number of corrections for a pair to be considered significant.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Do not actually save changes, just show what would be done.',
        )

    def handle(self, *args, **options):
        threshold = options['threshold']
        dry_run = options['dry_run']

        self.stdout.write(self.style.SUCCESS(f'Starting analysis of product corrections with threshold: {threshold}'))
        if dry_run:
            self.stdout.write(self.style.WARNING('Running in DRY-RUN mode. No changes will be saved.'))

        # Group corrections by original and corrected product names
        frequent_corrections = ProductCorrection.objects.values(
            'original_product_name', 'corrected_product_name', 'matched_product'
        ).annotate(
            count=Count('id')
        ).filter(
            count__gte=threshold,
            matched_product__isnull=False # Only consider corrections linked to an existing product
        ).order_by('-count')

        if not frequent_corrections:
            self.stdout.write(self.style.SUCCESS('No frequent corrections found above the threshold.'))
            return

        self.stdout.write(self.style.SUCCESS(f'Found {len(frequent_corrections)} frequent correction pairs.'))

        for correction_data in frequent_corrections:
            original_name = correction_data['original_product_name']
            corrected_name = correction_data['corrected_product_name']
            matched_product_id = correction_data['matched_product']
            count = correction_data['count']

            try:
                product = Product.objects.get(id=matched_product_id)

                # Check if the original name is already an alias or the product's main name
                if original_name == product.name or original_name in product.aliases:
                    self.stdout.write(
                        self.style.NOTICE(
                            f'Skipping "{original_name}" -> "{corrected_name}" (Product: {product.name}) '
                            f'as it is already an alias or main name. Count: {count}'
                        )
                    )
                    continue

                self.stdout.write(
                    self.style.SUCCESS(
                        f'Identified significant correction: "{original_name}" -> "{corrected_name}" '
                        f'(Product: {product.name}, Count: {count})'
                    )
                )

                if not dry_run:
                    product.add_alias(original_name)
                    self.stdout.write(self.style.SUCCESS(f'Added "{original_name}" as alias to product "{product.name}".'))
                else:
                    self.stdout.write(self.style.WARNING(f'DRY-RUN: Would add "{original_name}" as alias to product "{product.name}".'))

            except Product.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f'Product with ID {matched_product_id} not found for correction '
                        f'"{original_name}" -> "{corrected_name}". Skipping.'
                    )
                )
            except Exception as e:
                logger.error(f"Error processing correction {original_name} -> {corrected_name}: {e}", exc_info=True)
                self.stdout.write(self.style.ERROR(f'An error occurred: {e}'))

        self.stdout.write(self.style.SUCCESS('Product correction analysis completed.'))
