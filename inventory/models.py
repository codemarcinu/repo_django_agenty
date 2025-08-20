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
        help_text="List of dictionaries, each representing an alias with its metadata (name, count, first_seen, last_seen, status).",
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
        """
        Add a new alias for fuzzy matching or update an existing one.
        If the alias already exists, increment its count and update last_seen.
        Otherwise, add a new alias entry.
        """
        from django.utils import timezone

        found = False
        for alias_entry in self.aliases:
            if alias_entry.get("name") == alias_name:
                alias_entry["count"] = alias_entry.get("count", 0) + 1
                alias_entry["last_seen"] = timezone.now().isoformat()
                found = True
                break
        if not found:
            self.aliases.append(
                {
                    "name": alias_name,
                    "count": 1,
                    "first_seen": timezone.now().isoformat(),
                    "last_seen": timezone.now().isoformat(),
                    "status": "unverified",  # Initial status
                }
            )
        self.save(update_fields=["aliases"])

    def get_all_names(self):
        """Returns all possible names including aliases for matching."""
        names = [self.name]
        if self.brand:
            names.append(f"{self.brand} {self.name}")
        # Extract 'name' from each alias dictionary
        names.extend([alias_entry.get("name") for alias_entry in self.aliases if alias_entry.get("name")])
        return names


class Receipt(models.Model):
    """Receipt record from OCR processing."""

    CURRENCY_CHOICES = [
        ("PLN", "Polish Złoty"),
        ("EUR", "Euro"),
        ("USD", "US Dollar"),
    ]

    STATUS_CHOICES = [
        ("pending", "Oczekuje"),
        ("processing", "W trakcie przetwarzania"),
        ("review_pending", "Oczekuje na weryfikację"),
        ("completed", "Zakończono"),
        ("error", "Błąd"),
    ]

    PROCESSING_STEP_CHOICES = [
        ("uploaded", "File Uploaded"),
        ("ocr_in_progress", "OCR in Progress"),
        ("ocr_completed", "OCR Completed"),
        ("parsing_in_progress", "Parsing in Progress"),
        ("parsing_completed", "Parsing Completed"),
        ("matching_in_progress", "Matching Products"),
        ("matching_completed", "Matching Completed"),
        ("finalizing_inventory", "Finalizing Inventory"),
        ("review_pending", "Review Pending"),
        ("done", "Done"),
        ("failed", "Failed"),
    ]

    id = models.AutoField(primary_key=True)
    store_name = models.CharField(max_length=200, blank=True, default="")
    purchased_at = models.DateTimeField(
        null=True, blank=True, help_text="Date and time when the receipt was issued"
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        null=True, blank=True,
        help_text="Total amount from receipt",
    )
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="PLN")
    
    # UNIFIED FIELDS - combining ReceiptProcessing functionality
    receipt_file = models.FileField(
        upload_to="receipt_files/",
        verbose_name="Plik paragonu (obraz lub PDF)",
        help_text="Obsługiwane formaty: JPG, PNG, WebP, PDF (maks. 10MB)",
        null=True,
        blank=True,
    )
    raw_ocr_text = models.TextField(blank=True, verbose_name="Surowy tekst z OCR")
    raw_text = JSONField(
        default=dict,
        blank=True,
        help_text="Raw OCR output with confidence scores and metadata",
    )
    extracted_data = JSONField(
        null=True, blank=True, verbose_name="Wyodrębnione dane (JSON)"
    )
    parsed_data = JSONField(
        default=dict, blank=True, help_text="Parsed structured data from receipt text"
    )
    source_file_path = models.CharField(
        max_length=500, blank=True, default="", help_text="Path to original receipt file"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    processing_step = models.CharField(
        max_length=30, choices=PROCESSING_STEP_CHOICES, default="uploaded",
        help_text="Current granular step in the receipt processing pipeline"
    )
    processing_notes = models.TextField(blank=True, default="")
    error_message = models.TextField(blank=True, verbose_name="Komunikat błędu")
    uploaded_at = models.DateTimeField(
        default=timezone.now, verbose_name="Data przesłania"
    )
    processed_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Data przetworzenia"
    )

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
        if self.purchased_at:
            return f"Receipt {self.id} - {self.store_name} ({self.purchased_at.date()})"
        return f"Receipt {self.id} - {self.store_name} - Status: {self.get_status_display()}"

    def get_total_from_items(self):
        """Calculate total from line items for validation."""
        return sum(item.line_total for item in self.line_items.all())

    def get_total_discrepancy(self):
        """Get discrepancy between receipt total and calculated total."""
        if not self.total:
            return Decimal('0')
        calculated = self.get_total_from_items()
        return abs(self.total - calculated)

    # UNIFIED BUSINESS LOGIC - combining methods from ReceiptProcessing
    def mark_as_processing(self):
        """Mark receipt as being processed"""
        self.status = "processing"
        self.processing_step = "ocr_in_progress"
        self.save()

    def mark_ocr_done(self, raw_text: str):
        """Mark OCR processing as completed"""
        self.status = "processing"
        self.processing_step = "ocr_completed"
        self.raw_ocr_text = raw_text
        self.save()

    def mark_llm_processing(self):
        """Mark LLM processing as started"""
        self.status = "processing"
        self.processing_step = "parsing_in_progress"
        self.save()

    def mark_llm_done(self, extracted_data: dict):
        """Mark LLM processing as completed"""
        self.status = "processing"
        self.processing_step = "parsing_completed"
        self.extracted_data = extracted_data
        self.save()

    def mark_as_ready_for_review(self):
        """Mark receipt as ready for user review"""
        self.status = "review_pending"
        self.processing_step = "review_pending"
        self.save()

    def mark_as_completed(self):
        """Mark receipt processing as completed"""
        self.status = "completed"
        self.processing_step = "done"
        self.processed_at = timezone.now()
        self.save()

    def mark_as_error(self, error_message: str):
        """Mark receipt processing as failed with error message"""
        self.status = "error"
        self.processing_step = "failed"
        self.error_message = error_message
        self.save()

    def is_ready_for_review(self) -> bool:
        """Check if receipt is ready for user review"""
        return self.status == "review_pending"

    def is_completed(self) -> bool:
        """Check if receipt processing is completed"""
        return self.status == "completed"

    def has_error(self) -> bool:
        """Check if receipt processing has an error"""
        return self.status == "error"

    def is_processing(self) -> bool:
        """Check if receipt is currently being processed"""
        return self.status == "processing"

    def get_redirect_url(self):
        """Get appropriate redirect URL based on status"""
        if self.is_ready_for_review():
            from django.urls import reverse
            return reverse("chatbot:receipt_review", kwargs={"receipt_id": self.id})
        return None

    def get_status_display_with_message(self) -> str:
        """Get status display with error message if applicable"""
        base_display = self.get_status_display()
        step_display = self.get_processing_step_display()
        
        if self.has_error() and self.error_message:
            return f"{base_display} ({step_display}): {self.error_message}"
        elif self.status == "processing":
            return f"{base_display} ({step_display})"
        return base_display

    def get_extracted_products(self) -> list[dict]:
        """Get extracted products from receipt data"""
        if not self.extracted_data:
            return []
        return self.extracted_data.get("products", [])

    def update_inventory_from_extracted_data(self, products_data: list[dict]) -> bool:
        """Update inventory with extracted receipt data"""
        try:
            from chatbot.services.inventory_service import get_inventory_service
            
            inventory_service = get_inventory_service()
            
            for product in products_data:
                name = product.get("name", "").strip()
                quantity = float(product.get("quantity", 1.0))
                unit = product.get("unit", "szt.").strip()
                
                if name:
                    inventory_service.add_or_update_item(name, quantity, unit)
            
            self.mark_as_completed()
            return True
            
        except Exception as e:
            self.mark_as_error(f"Błąd podczas aktualizacji inwentarza: {str(e)}")
            return False

    @classmethod
    def get_recent_receipts(cls, limit: int = 5):
        """Get recent receipts for dashboard"""
        return cls.objects.order_by("-uploaded_at")[:limit]

    @classmethod
    def get_statistics(cls) -> dict:
        """Get receipt processing statistics"""
        return {
            "total": cls.objects.count(),
            "pending": cls.objects.filter(status="pending").count(),
            "processing": cls.objects.filter(
                status="processing"
            ).count(),
            "review_pending": cls.objects.filter(status="review_pending").count(),
            "completed": cls.objects.filter(status="completed").count(),
            "error": cls.objects.filter(status="error").count(),
        }


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


class Rule(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    # Używamy prostego JSON-a do definicji warunków. Jest to bezpieczne i elastyczne.
    # Przykład: {"field": "product.category.name", "operator": "equals", "value": "Nabiał"}
    condition = JSONField()
    # Przykład: {"action_type": "set_expiry", "params": {"days": 7}}
    action = JSONField()
    priority = models.IntegerField(default=100, help_text="Niższa liczba = wyższy priorytet")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['priority']

    def __str__(self):
        return self.name