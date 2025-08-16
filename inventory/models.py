"""
Models for inventory management system.
Implements the receipt processing pipeline: OCR→parse→match→inventory
"""

from django.db import models

try:
    # Try Django 3.1+ native JSONField
    from django.db.models import JSONField
except ImportError:
    # Fallback for older Django or PostgreSQL-specific JSONField
    try:
        from django.contrib.postgres.fields import JSONField
    except ImportError:
        # For SQLite compatibility, use TextField with JSON serialization
        import json

        class JSONField(models.TextField):
            def __init__(self, *args, **kwargs):
                kwargs.setdefault("default", dict)
                super().__init__(*args, **kwargs)

            def from_db_value(self, value, expression, connection):
                if value is None:
                    return value
                try:
                    return json.loads(value)
                except (TypeError, ValueError):
                    return value

            def to_python(self, value):
                if isinstance(value, (dict, list)):
                    return value
                if value is None:
                    return value
                try:
                    return json.loads(value)
                except (TypeError, ValueError):
                    return value

            def get_prep_value(self, value):
                if value is None:
                    return value
                return json.dumps(value)


from decimal import Decimal

from django.core.validators import MinValueValidator
from django.utils import timezone


class Category(models.Model):
    """Product categories with hierarchical structure."""

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200, unique=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="subcategories",
    )
    meta = JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata like expiry_days for automatic expiry calculation",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["parent"]),
        ]

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} → {self.name}"
        return self.name

    def get_full_path(self):
        """Returns full category path from root to this category."""
        path = [self.name]
        parent = self.parent
        while parent:
            path.insert(0, parent.name)
            parent = parent.parent
        return " → ".join(path)

    def get_default_expiry_days(self):
        """Get default expiry days from category metadata."""
        return self.meta.get("expiry_days", 30)  # Default 30 days


class Product(models.Model):
    """Product catalog with normalization and matching capabilities."""

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=300, db_index=True)
    brand = models.CharField(max_length=100, blank=True, default="")
    barcode = models.CharField(
        max_length=50,
        blank=True,
        default="",
        db_index=True,
        help_text="EAN/UPC barcode for exact matching",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    nutrition = JSONField(
        default=dict,
        blank=True,
        help_text="Nutritional information from OpenFoodFacts API",
    )
    aliases = JSONField(
        default=list,
        blank=True,
        help_text="Alternative names and variations for fuzzy matching",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="False for 'ghost' products created from unmatched receipt items",
    )
    reorder_point = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal("1.000"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Minimum quantity before reorder alert",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["barcode"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["category"]),
        ]
        # GIN indexes for JSONB fields (added in migration)

    def __str__(self):
        if self.brand:
            return f"{self.brand} {self.name}"
        return self.name

    def add_alias(self, alias_name):
        """Add a new alias for fuzzy matching."""
        if alias_name not in self.aliases:
            self.aliases.append(alias_name)
            self.save(update_fields=["aliases"])

    def get_all_names(self):
        """Returns all possible names including aliases for matching."""
        names = [self.name]
        if self.brand:
            names.append(f"{self.brand} {self.name}")
        names.extend(self.aliases)
        return names


class Receipt(models.Model):
    """Receipt record from OCR processing."""

    CURRENCY_CHOICES = [
        ("PLN", "Polish Złoty"),
        ("EUR", "Euro"),
        ("USD", "US Dollar"),
    ]

    STATUS_CHOICES = [
        ("pending_ocr", "Pending OCR"),
        ("processing_ocr", "OCR in Progress"),
        ("ocr_completed", "OCR Completed"),
        ("processing_parsing", "Processing Parsing"),
        ("parsing_completed", "Parsing Completed"),
        ("matching", "Matching Products"),
        ("completed", "Completed"),
        ("error", "Error"),
    ]

    id = models.AutoField(primary_key=True)
    store_name = models.CharField(max_length=200, blank=True, default="")
    purchased_at = models.DateTimeField(
        help_text="Date and time when the receipt was issued"
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Total amount from receipt",
    )
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="PLN")
    raw_text = JSONField(
        default=dict,
        blank=True,
        help_text="Raw OCR output with confidence scores and metadata",
    )
    parsed_data = JSONField(
        default=dict, blank=True, help_text="Parsed structured data from receipt text"
    )
    source_file_path = models.CharField(
        max_length=500, help_text="Path to original receipt file"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending_ocr"
    )
    processing_notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["store_name"]),
            models.Index(fields=["purchased_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]
        # GIN index for raw_text JSONB field (added in migration)

    def __str__(self):
        return f"Receipt {self.id} - {self.store_name} ({self.purchased_at.date()})"

    def get_total_from_items(self):
        """Calculate total from line items for validation."""
        return sum(item.line_total for item in self.line_items.all())

    def get_total_discrepancy(self):
        """Get discrepancy between receipt total and calculated total."""
        calculated = self.get_total_from_items()
        return abs(self.total - calculated)


class ReceiptLineItem(models.Model):
    """Individual line item from a receipt."""

    VAT_CODE_CHOICES = [
        ("A", "VAT A"),
        ("B", "VAT B"),
        ("C", "VAT C"),
        ("D", "VAT D"),
        ("", "Unknown"),
    ]

    id = models.AutoField(primary_key=True)
    receipt = models.ForeignKey(
        Receipt, on_delete=models.CASCADE, related_name="line_items"
    )
    product_name = models.CharField(
        max_length=300, db_index=True, help_text="Original product name from receipt"
    )
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
        help_text="Quantity purchased",
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Price per unit",
    )
    line_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Total for this line item",
    )
    vat_code = models.CharField(
        max_length=1, choices=VAT_CODE_CHOICES, blank=True, default=""
    )
    meta = JSONField(
        default=dict,
        blank=True,
        help_text="Additional parsing metadata and original text fragments",
    )
    matched_product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receipt_items",
        help_text="Matched product from catalog",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["receipt"]),
            models.Index(fields=["product_name"]),
            models.Index(fields=["matched_product"]),
        ]
        # GIN index for meta JSONB field (added in migration)

    def __str__(self):
        return f"{self.product_name} x{self.quantity} = {self.line_total}"

    def calculate_line_total(self):
        """Calculate line total from quantity and unit price."""
        return self.quantity * self.unit_price

    def validate_line_total(self, tolerance=Decimal("0.05")):
        """Validate that line_total matches quantity * unit_price within tolerance."""
        calculated = self.calculate_line_total()
        return abs(self.line_total - calculated) <= tolerance


class InventoryItem(models.Model):
    """Individual inventory item tracking current stock."""

    UNIT_CHOICES = [
        ("szt", "Sztuki"),
        ("kg", "Kilogramy"),
        ("g", "Gramy"),
        ("l", "Litry"),
        ("ml", "Mililitry"),
        ("opak", "Opakowania"),
    ]

    STORAGE_CHOICES = [
        ("fridge", "Lodówka"),
        ("freezer", "Zamrażarka"),
        ("pantry", "Spiżarnia"),
        ("cabinet", "Szafka"),
        ("other", "Inne"),
    ]

    id = models.AutoField(primary_key=True)
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="inventory_items"
    )
    purchase_date = models.DateField(help_text="Date when the product was purchased")
    expiry_date = models.DateField(
        null=True, blank=True, help_text="Expiry date (calculated or manual)"
    )
    quantity_remaining = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Current remaining quantity",
    )
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default="szt")
    storage_location = models.CharField(
        max_length=20, choices=STORAGE_CHOICES, default="pantry"
    )
    batch_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Batch identifier for tracking",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["product"]),
            models.Index(fields=["purchase_date"]),
            models.Index(fields=["expiry_date"]),
            models.Index(fields=["quantity_remaining"]),
            models.Index(fields=["storage_location"]),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.quantity_remaining}{self.unit}"

    def is_expired(self):
        """Check if item is past expiry date."""
        if not self.expiry_date:
            return False
        return timezone.now().date() > self.expiry_date

    def days_until_expiry(self):
        """Get days until expiry (negative if expired)."""
        if not self.expiry_date:
            return None
        return (self.expiry_date - timezone.now().date()).days

    def is_expiring_soon(self, days=2):
        """Check if item expires within specified days."""
        days_left = self.days_until_expiry()
        return days_left is not None and 0 <= days_left <= days

    def is_low_stock(self):
        """Check if quantity is below reorder point."""
        return self.quantity_remaining <= self.product.reorder_point

    def consume(self, quantity, notes=""):
        """Consume specified quantity and create consumption event."""
        if quantity > self.quantity_remaining:
            raise ValueError("Cannot consume more than available quantity")

        # Create consumption event
        consumption = ConsumptionEvent.objects.create(
            inventory_item=self,
            consumed_qty=quantity,
            consumed_at=timezone.now(),
            notes=notes,
        )

        # Update remaining quantity
        self.quantity_remaining -= quantity
        self.save(update_fields=["quantity_remaining", "updated_at"])

        return consumption

    def add_quantity(self, amount):
        """Add to existing quantity"""
        self.quantity_remaining += Decimal(str(amount))
        self.save(update_fields=["quantity_remaining", "updated_at"])

    def subtract_quantity(self, amount):
        """Subtract from existing quantity (doesn't allow negative)"""
        amount_decimal = Decimal(str(amount))
        self.quantity_remaining = max(Decimal('0'), self.quantity_remaining - amount_decimal)
        self.save(update_fields=["quantity_remaining", "updated_at"])

    @classmethod
    def get_expired_items(cls):
        """Get all expired items"""
        today = timezone.now().date()
        return cls.objects.filter(expiry_date__lt=today, quantity_remaining__gt=0)

    @classmethod
    def get_expiring_soon(cls, days: int = 7):
        """Get items expiring within specified days"""
        today = timezone.now().date()
        future_date = today + timezone.timedelta(days=days)
        return cls.objects.filter(
            expiry_date__gte=today, 
            expiry_date__lte=future_date,
            quantity_remaining__gt=0
        )

    @classmethod
    def get_low_stock_items(cls, threshold=None):
        """Get items with low stock"""
        from django.db.models import F
        
        if threshold is not None:
            return cls.objects.filter(
                quantity_remaining__lte=Decimal(str(threshold)),
                quantity_remaining__gt=0
            )
        else:
            # Use product reorder point
            return cls.objects.filter(
                quantity_remaining__lte=F("product__reorder_point"),
                quantity_remaining__gt=0
            )

    @classmethod
    def get_statistics(cls):
        """Get inventory statistics"""
        from django.db.models import Count, Avg, Sum
        
        today = timezone.now().date()
        
        return {
            "total_items": cls.objects.filter(quantity_remaining__gt=0).count(),
            "expired_count": cls.get_expired_items().count(),
            "expiring_soon_count": cls.get_expiring_soon().count(),
            "low_stock_count": cls.get_low_stock_items().count(),
            "average_quantity": cls.objects.filter(quantity_remaining__gt=0).aggregate(
                avg=Avg("quantity_remaining")
            )["avg"] or 0,
            "total_value": cls.objects.filter(quantity_remaining__gt=0).aggregate(
                total=Sum("quantity_remaining")
            )["total"] or 0,
        }


class ConsumptionEvent(models.Model):
    """Track consumption of inventory items."""

    id = models.AutoField(primary_key=True)
    inventory_item = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE, related_name="consumption_events"
    )
    consumed_qty = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
        help_text="Quantity consumed",
    )
    consumed_at = models.DateTimeField(
        default=timezone.now, help_text="When the consumption occurred"
    )
    notes = models.TextField(
        blank=True, default="", help_text="Optional notes about consumption"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["inventory_item"]),
            models.Index(fields=["consumed_at"]),
        ]
        ordering = ["-consumed_at"]

    def __str__(self):
        return f"Consumed {self.consumed_qty} of {self.inventory_item.product.name}"
