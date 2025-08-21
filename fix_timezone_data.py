#!/usr/bin/env python
"""
Script to fix naive datetime objects in the database.
Converts all naive datetimes to timezone-aware datetimes.
"""

import os
import sys
from pathlib import Path

import django

# Add project root to Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings_dev')
django.setup()


from django.db import transaction
from django.utils import timezone

from inventory.models import ConsumptionEvent, Product, Receipt


def fix_naive_datetimes():
    """Fix all naive datetime objects in the database."""
    print("🔧 Starting timezone fix...")

    fixed_count = 0

    with transaction.atomic():
        # Fix Receipt.purchased_at
        print("📄 Fixing Receipt.purchased_at fields...")
        for receipt in Receipt.objects.all():
            if receipt.purchased_at and receipt.purchased_at.tzinfo is None:
                receipt.purchased_at = timezone.make_aware(receipt.purchased_at)
                receipt.save(update_fields=['purchased_at'])
                fixed_count += 1
                print(f"  ✅ Fixed Receipt {receipt.id}")

        # Fix ConsumptionEvent.consumed_at
        print("🍽️ Fixing ConsumptionEvent.consumed_at fields...")
        for event in ConsumptionEvent.objects.all():
            if event.consumed_at and event.consumed_at.tzinfo is None:
                event.consumed_at = timezone.make_aware(event.consumed_at)
                event.save(update_fields=['consumed_at'])
                fixed_count += 1
                print(f"  ✅ Fixed ConsumptionEvent {event.id}")

        # Fix Product.created_at (if it exists and is naive)
        print("🛍️ Fixing Product.created_at fields...")
        for product in Product.objects.all():
            if hasattr(product, 'created_at') and product.created_at and product.created_at.tzinfo is None:
                product.created_at = timezone.make_aware(product.created_at)
                product.save(update_fields=['created_at'])
                fixed_count += 1
                print(f"  ✅ Fixed Product {product.id}")

        # Fix PantryItem date fields
        print("🥫 Fixing PantryItem fields...")
        for item in PantryItem.objects.all():
            updated_fields = []

            if item.added_date and item.added_date.tzinfo is None:
                item.added_date = timezone.make_aware(item.added_date)
                updated_fields.append('added_date')

            if item.updated_date and item.updated_date.tzinfo is None:
                item.updated_date = timezone.make_aware(item.updated_date)
                updated_fields.append('updated_date')

            if updated_fields:
                item.save(update_fields=updated_fields)
                fixed_count += 1
                print(f"  ✅ Fixed PantryItem {item.id}")

        # Fix ReceiptProcessing fields
        print("📋 Fixing ReceiptProcessing fields...")
        for processing in ReceiptProcessing.objects.all():
            updated_fields = []

            if processing.uploaded_at and processing.uploaded_at.tzinfo is None:
                processing.uploaded_at = timezone.make_aware(processing.uploaded_at)
                updated_fields.append('uploaded_at')

            if processing.processed_at and processing.processed_at.tzinfo is None:
                processing.processed_at = timezone.make_aware(processing.processed_at)
                updated_fields.append('processed_at')

            if updated_fields:
                processing.save(update_fields=updated_fields)
                fixed_count += 1
                print(f"  ✅ Fixed ReceiptProcessing {processing.id}")

    print(f"\n🎉 Timezone fix completed! Fixed {fixed_count} datetime fields.")
    return fixed_count


def verify_fix():
    """Verify that all datetime fields are now timezone-aware."""
    print("\n🔍 Verifying timezone fix...")

    issues = []

    # Check Receipt.purchased_at
    for receipt in Receipt.objects.all()[:5]:
        if receipt.purchased_at and receipt.purchased_at.tzinfo is None:
            issues.append(f"Receipt {receipt.id} still has naive purchased_at")

    # Check ConsumptionEvent.consumed_at
    for event in ConsumptionEvent.objects.all()[:5]:
        if event.consumed_at and event.consumed_at.tzinfo is None:
            issues.append(f"ConsumptionEvent {event.id} still has naive consumed_at")

    # Check Product.created_at
    for product in Product.objects.all()[:5]:
        if hasattr(product, 'created_at') and product.created_at and product.created_at.tzinfo is None:
            issues.append(f"Product {product.id} still has naive created_at")

    if issues:
        print("❌ Found remaining issues:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("✅ All datetime fields are now timezone-aware!")
        return True


if __name__ == "__main__":
    try:
        fixed_count = fix_naive_datetimes()
        success = verify_fix()

        if success:
            print("\n🎯 Timezone fix successful!")
        else:
            print("\n⚠️ Some issues remain - manual review needed")

    except Exception as e:
        print(f"\n❌ Error during timezone fix: {e}")
        import traceback
        traceback.print_exc()
