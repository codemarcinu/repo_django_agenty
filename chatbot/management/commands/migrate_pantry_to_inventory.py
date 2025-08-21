import logging
from datetime import timedelta
from django.utils import timezone
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import connection
from django.apps import apps
from inventory.models import Category, InventoryItem, Product

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Migrates data from deleted PantryItem table to InventoryItem (if data still exists in DB)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without actually doing it',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force migration even if no pantry data is found',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']

        self.stdout.write("🔍 Checking for remnant PantryItem data...")

        # Sprawdź czy tabela pantryitem nadal istnieje w bazie danych
        with connection.cursor() as cursor:
            # Lista wszystkich tabel w bazie
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name LIKE '%pantryitem%';
            """)
            pantry_tables = cursor.fetchall()

            if not pantry_tables:
                self.stdout.write(
                    self.style.WARNING(
                        "❌ No PantryItem tables found in database. "
                        "Migration 0013 has already removed the schema."
                    )
                )

                if not force:
                    self.stdout.write(
                        self.style.ERROR(
                            "Migration cannot proceed. Data no longer exists.\n"
                            "Use --force if you want to create sample inventory items instead."
                        )
                    )
                    return
                else:
                    self._create_sample_data(dry_run)
                    return

            # Jeśli tabela istnieje, spróbuj migrować dane
            self.stdout.write(f"✅ Found pantry tables: {[t[0] for t in pantry_tables]}")
            self._migrate_existing_data(cursor, dry_run)

    def _migrate_existing_data(self, cursor, dry_run):
        """Migruje istniejące dane z tabeli PantryItem"""
        try:
            # Dynamically get the PantryItem model from its historical state
            # This assumes the model definition is still available in a migration file
            # or that the table structure is simple enough to infer.
            # For a robust solution, you might need to load the model from a specific migration.
            # For now, we'll try to query the table directly.

            # Check if the table actually has columns that match the old PantryItem model
            # This is a simplified check. A real migration would need to be more robust.
            cursor.execute("PRAGMA table_info(pantryitem)")
            columns_info = cursor.fetchall()
            column_names = [col[1] for col in columns_info]

            required_columns = ['id', 'name', 'quantity', 'unit', 'added_date', 'expiry_date', 'updated_date']
            if not all(col in column_names for col in required_columns):
                self.stdout.write(self.style.ERROR("❌ PantryItem table schema does not match expected for migration."))
                return

            cursor.execute("SELECT * FROM pantryitem")
            rows = cursor.fetchall()

            if not rows:
                self.stdout.write(
                    self.style.WARNING("⚠️ PantryItem table exists but contains no data")
                )
                return

            # Pobierz nazwy kolumn
            # cursor.execute("PRAGMA table_info(pantryitem)")
            # columns = [col[1] for col in cursor.fetchall()]
            columns = column_names # Use the already fetched column names

            self.stdout.write(f"📊 Found {len(rows)} pantry items to migrate")
            self.stdout.write(f"📋 Columns: {columns}")

            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS("🔍 DRY RUN - Would migrate these items:")
                )
                for row in rows[:3]:  # Pokaż pierwsze 3
                    item_data = dict(zip(columns, row, strict=False))
                    self.stdout.write(f"  - {item_data}")
            else:
                self._perform_migration(cursor, columns, rows)

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error accessing pantry data: {e}")
            )

    def _perform_migration(self, cursor, columns, rows):
        """Wykonuje właściwą migrację danych"""
        # cursor.execute("SELECT * FROM pantryitem")
        # rows = cursor.fetchall()

        migrated_count = 0

        # Create default category for migrated items if it doesn't exist
        default_category, created = Category.objects.get_or_create(
            name="Migrated from Pantry",
            defaults={"meta": {"expiry_days": 30}}
        )
        if created:
            self.stdout.write(f"✅ Created default category: {default_category.name}")

        for row in rows:
            item_data = dict(zip(columns, row, strict=False))

            # Try to find existing product by name
            product = Product.objects.filter(name__iexact=item_data.get('name')).first()

            if not product:
                # Create new product for this pantry item
                product = Product.objects.create(
                    name=item_data.get('name', 'Unknown Item'),
                    category=default_category,
                    is_active=True,
                    reorder_point=0 # Default reorder point
                )
                self.stdout.write(f"  📝 Created Product: {product.name}")

            # Create InventoryItem
            try:
                # Convert types explicitly
                purchase_date = item_data.get('added_date')
                if purchase_date:
                    purchase_date = timezone.datetime.fromisoformat(purchase_date) if isinstance(purchase_date, str) else purchase_date
                    purchase_date = purchase_date.date() if isinstance(purchase_date, timezone.datetime) else purchase_date

                expiry_date = item_data.get('expiry_date')
                if expiry_date:
                    expiry_date = timezone.datetime.fromisoformat(expiry_date) if isinstance(expiry_date, str) else expiry_date
                    expiry_date = expiry_date.date() if isinstance(expiry_date, timezone.datetime) else expiry_date

                quantity_remaining = item_data.get('quantity')
                if quantity_remaining is not None:
                    quantity_remaining = Decimal(str(quantity_remaining))

                created_at = item_data.get('added_date')
                if created_at:
                    created_at = timezone.datetime.fromisoformat(created_at) if isinstance(created_at, str) else created_at
                    created_at = timezone.make_aware(created_at) if isinstance(created_at, timezone.datetime) and timezone.is_naive(created_at) else created_at

                updated_at = item_data.get('updated_date')
                if updated_at:
                    updated_at = timezone.datetime.fromisoformat(updated_at) if isinstance(updated_at, str) else updated_at
                    updated_at = timezone.make_aware(updated_at) if isinstance(updated_at, timezone.datetime) and timezone.is_naive(updated_at) else updated_at

                inventory_item = InventoryItem.objects.create(
                    product=product,
                    purchase_date=purchase_date,
                    expiry_date=expiry_date,
                    quantity_remaining=quantity_remaining,
                    unit=self._normalize_unit(item_data.get('unit', 'szt.')),
                    storage_location='pantry',  # Default for migrated items
                    batch_id=f"MIGRATED-{item_data.get('id')}",
                    created_at=created_at,
                    updated_at=updated_at,
                )
                migrated_count += 1
                self.stdout.write(f"✅ Migrated: {inventory_item.product.name}")
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Failed to create InventoryItem for {item_data.get('name')}: {e}")
                )

        self.stdout.write(
            self.style.SUCCESS(f"🎉 Successfully migrated {migrated_count} items")
        )

    def _normalize_unit(self, unit: str) -> str:
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

    def _create_sample_data(self, dry_run):
        """Tworzy przykładowe dane inventory jeśli oryginalne dane nie istnieją"""
        sample_items = [
            {"name": "Milk", "quantity": 2, "unit": "liters"},
            {"name": "Bread", "quantity": 1, "unit": "loaf"},
            {"name": "Eggs", "quantity": 12, "unit": "pieces"},
        ]

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS("🔍 DRY RUN - Would create sample items:")
            )
            for item in sample_items:
                self.stdout.write(f"  - {item}")
        else:
            # Ensure default category exists for sample data
            default_category, created = Category.objects.get_or_create(
                name="Sample Data",
                defaults={"meta": {"expiry_days": 30}}
            )
            if created:
                self.stdout.write(f"✅ Created default category for sample data: {default_category.name}")

            for item_data in sample_items:
                product, _ = Product.objects.get_or_create(
                    name=item_data['name'],
                    defaults={'category': default_category, 'reorder_point': 0}
                )
                InventoryItem.objects.create(
                    product=product,
                    quantity_remaining=item_data['quantity'],
                    unit=self._normalize_unit(str(item_data['unit'])),
                    storage_location='pantry', # Default for sample items
                    batch_id='SAMPLE-DATA',
                    purchase_date=timezone.now().date(),
                    expiry_date=timezone.now().date() + timedelta(days=7) # 7 days expiry
                )
                self.stdout.write(f"✅ Created sample item: {item_data['name']}")

            self.stdout.write(
                self.style.SUCCESS(f"🎉 Created {len(sample_items)} sample inventory items")
            )


