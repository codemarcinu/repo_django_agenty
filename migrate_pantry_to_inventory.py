#!/usr/bin/env python
"""
Script to migrate data 
This consolidates the duplicate models into the more advanced InventoryItem.
"""

import os
import sys
import django
from pathlib import Path
from decimal import Decimal

# Setup Django
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings_dev')
django.setup()

from django.db import transaction
from django.utils import timezone

from inventory.models import InventoryItem, Product, Category


def migrate_pantry_to_inventory():
    """Migrate PantryItem data to InventoryItem model."""
    print("🔄 Starting migration 
    
    migrated_count = 0
    created_products = 0
    
    # Create default category for migrated items
    default_category, created = Category.objects.get_or_create(
        name="Migrated from Pantry",
        defaults={"meta": {"expiry_days": 30}}
    )
    if created:
        print(f"✅ Created default category: {default_category.name}")
    
    with transaction.atomic():
        pantry_items = PantryItem.objects.all()
        print(f"📦 Found {pantry_items.count()} PantryItem records to migrate")
        
        for pantry_item in pantry_items:
            try:
                # Try to find existing product by name
                product = Product.objects.filter(name__iexact=pantry_item.name).first()
                
                if not product:
                    # Create new product for this pantry item
                    product = Product.objects.create(
                        name=pantry_item.name,
                        category=default_category,
                        is_active=True,
                        reorder_point=Decimal('1.000')
                    )
                    created_products += 1
                    print(f"  📝 Created Product: {product.name}")
                
                # Create InventoryItem 
                inventory_item = InventoryItem.objects.create(
                    product=product,
                    purchase_date=pantry_item.added_date.date(),
                    expiry_date=pantry_item.expiry_date,
                    quantity_remaining=Decimal(str(pantry_item.quantity)),
                    unit=_normalize_unit(pantry_item.unit),
                    storage_location='pantry',  # Default for migrated items
                    batch_id=f"MIGRATED-{pantry_item.id}",
                    created_at=pantry_item.added_date,
                    updated_at=pantry_item.updated_date,
                )
                
                migrated_count += 1
                print(f"  ✅ Migrated: {pantry_item.name} -> InventoryItem {inventory_item.id}")
                
            except Exception as e:
                print(f"  ❌ Error migrating {pantry_item.name}: {e}")
                continue
    
    print(f"\n🎉 Migration completed!")
    print(f"📊 Summary:")
    print(f"  - Migrated PantryItems: {migrated_count}")
    print(f"  - Created Products: {created_products}")
    print(f"  - Default Category: {default_category.name}")
    
    return migrated_count, created_products


def _normalize_unit(unit: str) -> str:
    """Normalize unit names to match InventoryItem choices."""
    unit_lower = unit.lower().strip()
    
    # Mapping 
    unit_mapping = {
        'szt.': 'szt',
        'szt': 'szt',
        'sztuki': 'szt',
        'kg': 'kg',
        'kilogram': 'kg',
        'kilogramy': 'kg',
        'g': 'g',
        'gram': 'g',
        'gramy': 'g',
        'l': 'l',
        'litr': 'l',
        'litry': 'l',
        'ml': 'ml',
        'millilitr': 'ml',
        'millilitry': 'ml',
        'opak': 'opak',
        'opakowanie': 'opak',
        'opakowania': 'opak',
    }
    
    return unit_mapping.get(unit_lower, 'szt')  # Default to 'szt'


def verify_migration():
    """Verify the migration was successful."""
    print("\n🔍 Verifying migration...")
    
    pantry_count = PantryItem.objects.count()
    inventory_count = InventoryItem.objects.filter(batch_id__startswith='MIGRATED-').count()
    
    print(f"Original PantryItems: {pantry_count}")
    print(f"Migrated InventoryItems: {inventory_count}")
    
    if pantry_count > 0:
        print("⚠️  Some PantryItems still exist - migration may be incomplete")
        return False
    else:
        print("✅ Migration verification successful!")
        return True


def cleanup_pantry_model():
    """Optional: Clean up PantryItem data after successful migration."""
    print("\n🧹 Cleaning up PantryItem data...")
    
    # Verify migration first
    if not verify_migration():
        print("❌ Migration verification failed - skipping cleanup")
        return False
    
    pantry_count = PantryItem.objects.count()
    if pantry_count > 0:
        with transaction.atomic():
            deleted_count = PantryItem.objects.all().delete()[0]
            print(f"🗑️  Deleted {deleted_count} PantryItem records")
    
    print("✅ Cleanup completed")
    return True


if __name__ == "__main__":
    try:
        # Step 1: Migrate data
        migrated, created = migrate_pantry_to_inventory()
        
        # Step 2: Verify migration
        success = verify_migration()
        
        if success and migrated > 0:
            # Step 3: Ask user about cleanup
            response = input("\n❓ Do you want to delete the original PantryItem data? (y/N): ")
            if response.lower() in ['y', 'yes']:
                cleanup_pantry_model()
            else:
                print("ℹ️  Original PantryItem data preserved")
        
        print("\n🎯 Migration process completed!")
        
    except Exception as e:
        print(f"\n❌ Error during migration: {e}")
        import traceback
        traceback.print_exc()