
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.urls import reverse
import json
import uuid
from typing import Dict, List, Optional
from .validators import validate_receipt_file


class PantryItem(models.Model):
    name = models.CharField(max_length=200, unique=True, verbose_name="Nazwa produktu")
    quantity = models.FloatField(default=1.0, verbose_name="Ilość")
    unit = models.CharField(max_length=50, default='szt.', verbose_name="Jednostka")
    added_date = models.DateTimeField(auto_now_add=True, verbose_name="Data dodania")
    updated_date = models.DateTimeField(auto_now=True, verbose_name="Data modyfikacji")
    expiry_date = models.DateField(null=True, blank=True, verbose_name="Data ważności") # New field

    class Meta:
        verbose_name = "Produkt w spiżarni"
        verbose_name_plural = "Produkty w spiżarni"
        ordering = ['-updated_date']
        indexes = [
            models.Index(fields=['expiry_date']),
            models.Index(fields=['updated_date']),
        ]

    def __str__(self):
        return f"{self.name} - {self.quantity} {self.unit}"
    
    # Business logic methods (Fat Model pattern)
    def is_expired(self) -> bool:
        """Check if the item is expired"""
        if not self.expiry_date:
            return False
        return self.expiry_date < timezone.now().date()
    
    def days_until_expiry(self) -> Optional[int]:
        """Get number of days until expiry (negative if expired)"""
        if not self.expiry_date:
            return None
        delta = self.expiry_date - timezone.now().date()
        return delta.days
    
    def is_expiring_soon(self, days: int = 7) -> bool:
        """Check if item expires within specified days"""
        days_left = self.days_until_expiry()
        return days_left is not None and 0 <= days_left <= days
    
    def update_quantity(self, new_quantity: float):
        """Update item quantity and save"""
        self.quantity = new_quantity
        self.save()
    
    def add_quantity(self, amount: float):
        """Add to existing quantity"""
        self.quantity += amount
        self.save()
    
    def subtract_quantity(self, amount: float):
        """Subtract from existing quantity (doesn't allow negative)"""
        self.quantity = max(0, self.quantity - amount)
        self.save()
    
    @classmethod
    def get_expired_items(cls):
        """Get all expired items"""
        today = timezone.now().date()
        return cls.objects.filter(expiry_date__lt=today)
    
    @classmethod
    def get_expiring_soon(cls, days: int = 7):
        """Get items expiring within specified days"""
        today = timezone.now().date()
        future_date = today + timezone.timedelta(days=days)
        return cls.objects.filter(
            expiry_date__gte=today,
            expiry_date__lte=future_date
        )
    
    @classmethod
    def get_low_stock_items(cls, threshold: float = 1.0):
        """Get items with low stock"""
        return cls.objects.filter(quantity__lte=threshold)
    
    @classmethod
    def get_statistics(cls) -> Dict:
        """Get pantry statistics"""
        from django.db.models import Count, Avg
        today = timezone.now().date()
        
        return {
            'total_items': cls.objects.count(),
            'expired_count': cls.objects.filter(expiry_date__lt=today).count(),
            'expiring_soon_count': cls.get_expiring_soon().count(),
            'low_stock_count': cls.get_low_stock_items().count(),
            'average_quantity': cls.objects.aggregate(avg=Avg('quantity'))['avg'] or 0,
        }


class ReceiptProcessing(models.Model):
    STATUS_CHOICES = [
        ('uploaded', 'Plik przesłany'),
        ('ocr_in_progress', 'Rozpoznawanie tekstu (OCR)'),
        ('ocr_done', 'Tekst rozpoznany'),
        ('llm_in_progress', 'Analiza przez AI'),
        ('llm_done', 'Analiza zakończona'),
        ('ready_for_review', 'Gotowe do weryfikacji'),
        ('completed', 'Zakończone'),
        ('error', 'Wystąpił błąd'),
    ]
    
    receipt_file = models.FileField(
        upload_to='receipt_files/', 
        verbose_name="Plik paragonu (obraz lub PDF)",
        validators=[validate_receipt_file],
        help_text="Obsługiwane formaty: JPG, PNG, WebP, PDF (maks. 10MB)",
        null=True, blank=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded', verbose_name="Status przetwarzania")
    raw_ocr_text = models.TextField(blank=True, verbose_name="Surowy tekst z OCR")
    extracted_data = models.JSONField(null=True, blank=True, verbose_name="Wyodrębnione dane (JSON)")
    error_message = models.TextField(blank=True, verbose_name="Komunikat błędu")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Data przesłania")
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name="Data przetworzenia")

    class Meta:
        verbose_name = "Przetwarzanie paragonu"
        verbose_name_plural = "Przetwarzanie paragonów"
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['uploaded_at']),
        ]

    def __str__(self):
        return f"Paragon {self.id} - Status: {self.get_status_display()}"
    
    # Business logic methods (Fat Model pattern)
    def mark_as_processing(self):
        """Mark receipt as being processed"""
        self.status = 'ocr_in_progress'
        self.save()
    
    def mark_ocr_done(self, raw_text: str):
        """Mark OCR processing as completed"""
        self.status = 'ocr_done'
        self.raw_ocr_text = raw_text
        self.save()
    
    def mark_llm_processing(self):
        """Mark LLM processing as started"""
        self.status = 'llm_in_progress'
        self.save()
    
    def mark_llm_done(self, extracted_data: dict):
        """Mark LLM processing as completed"""
        self.status = 'llm_done'
        self.extracted_data = extracted_data
        self.save()
    
    def mark_as_ready_for_review(self):
        """Mark receipt as ready for user review"""
        self.status = 'ready_for_review'
        self.save()
    
    def mark_as_completed(self):
        """Mark receipt processing as completed"""
        self.status = 'completed'
        self.processed_at = timezone.now()
        self.save()
    
    def mark_as_error(self, error_message: str):
        """Mark receipt processing as failed with error message"""
        self.status = 'error'
        self.error_message = error_message
        self.save()
    
    def is_ready_for_review(self) -> bool:
        """Check if receipt is ready for user review"""
        return self.status == 'ready_for_review'
    
    def is_completed(self) -> bool:
        """Check if receipt processing is completed"""
        return self.status == 'completed'
    
    def has_error(self) -> bool:
        """Check if receipt processing has an error"""
        return self.status == 'error'
    
    def is_processing(self) -> bool:
        """Check if receipt is currently being processed"""
        return self.status in ['ocr_in_progress', 'llm_in_progress']
    
    def get_redirect_url(self):
        """Get appropriate redirect URL based on status"""
        if self.is_ready_for_review():
            return reverse('chatbot:receipt_review', kwargs={'receipt_id': self.id})
        return None
    
    def get_status_display_with_message(self) -> str:
        """Get status display with error message if applicable"""
        if self.has_error() and self.error_message:
            return f"{self.get_status_display()}: {self.error_message}"
        return self.get_status_display()
    
    def get_extracted_products(self) -> List[Dict]:
        """Get extracted products from receipt data"""
        if not self.extracted_data:
            return []
        return self.extracted_data.get('products', [])
    
    def update_pantry_from_extracted_data(self, products_data: List[Dict]) -> bool:
        """Update pantry with extracted receipt data"""
        try:
            from .services.pantry_service import PantryService
            pantry_service = PantryService()
            
            for product in products_data:
                name = product.get('name', '').strip()
                quantity = float(product.get('quantity', 1.0))
                unit = product.get('unit', 'szt.').strip()
                
                if name:
                    pantry_service.add_or_update_item(name, quantity, unit)
            
            self.mark_as_completed()
            return True
            
        except Exception as e:
            self.mark_as_error(f"Błąd podczas aktualizacji spiżarni: {str(e)}")
            return False
    
    @classmethod
    def get_recent_receipts(cls, limit: int = 5):
        """Get recent receipts for dashboard"""
        return cls.objects.order_by('-uploaded_at')[:limit]
    
    @classmethod
    def get_statistics(cls) -> Dict:
        """Get receipt processing statistics"""
        from django.db.models import Count, Q
        return {
            'total': cls.objects.count(),
            'uploaded': cls.objects.filter(status='uploaded').count(),
            'processing': cls.objects.filter(
                status__in=['ocr_in_progress', 'llm_in_progress']
            ).count(),
            'ready_for_review': cls.objects.filter(status='ready_for_review').count(),
            'completed': cls.objects.filter(status='completed').count(),
            'error': cls.objects.filter(status='error').count(),
        }


class Agent(models.Model):
    AGENT_TYPE_CHOICES = [
        ('router', 'Router Agent'),
        ('ollama', 'Ollama (Legacy)'),
    ]
    
    name = models.CharField(max_length=100, unique=True, help_text="Unikalna nazwa agenta, np. 'Generalista'")
    agent_type = models.CharField(max_length=20, choices=AGENT_TYPE_CHOICES, default='general')
    persona_prompt = models.TextField(help_text="Opis osobowości i zadania agenta, który będzie używany w promptach LLM.")
    system_prompt = models.TextField(blank=True, help_text="Systemowy prompt dla agenta")
    capabilities = models.JSONField(default=list, help_text="Lista zdolności agenta")
    config = models.JSONField(default=dict, help_text="Konfiguracja agenta")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['agent_type', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_agent_type_display()})"

    def save(self, *args, **kwargs):
        # Force-correct the known bad model name for Ollama agents
        if self.agent_type == 'ollama' and self.config and isinstance(self.config, dict) and 'model' in self.config:
            bad_name = 'SpeakLeash/bielik-11b-v2.3 instruct:Q5_K_M'
            correct_name = 'SpeakLeash/bielik-11b-v2.3-instruct:Q5_K_M'
            if self.config.get('model') == bad_name:
                self.config['model'] = correct_name
        
        super().save(*args, **kwargs) # Call the original save method
    
    # Business logic methods (Fat Model pattern)
    def get_description(self) -> str:
        """Get truncated description for display"""
        if len(self.persona_prompt) > 200:
            return self.persona_prompt[:200] + "..."
        return self.persona_prompt
    
    def has_capability(self, capability: str) -> bool:
        """Check if agent has specific capability"""
        return capability in (self.capabilities or [])
    
    def add_capability(self, capability: str):
        """Add capability to agent"""
        if not self.capabilities:
            self.capabilities = []
        if capability not in self.capabilities:
            self.capabilities.append(capability)
            self.save()
    
    def remove_capability(self, capability: str):
        """Remove capability from agent"""
        if self.capabilities and capability in self.capabilities:
            self.capabilities.remove(capability)
            self.save()
    
    def update_config(self, key: str, value):
        """Update agent configuration"""
        if not self.config:
            self.config = {}
        self.config[key] = value
        self.save()
    
    def get_config_value(self, key: str, default=None):
        """Get configuration value"""
        return (self.config or {}).get(key, default)
    
    def activate(self):
        """Activate agent"""
        self.is_active = True
        self.save()
    
    def deactivate(self):
        """Deactivate agent"""
        self.is_active = False
        self.save()
    
    def get_conversation_count(self) -> int:
        """Get number of conversations for this agent"""
        return self.conversations.count()
    
    def get_recent_conversations(self, limit: int = 5):
        """Get recent conversations for this agent"""
        return self.conversations.filter(is_active=True).order_by('-updated_at')[:limit]
    
    @classmethod
    def get_active_agents(cls):
        """Get all active agents"""
        return cls.objects.filter(is_active=True).order_by('name')
    
    @classmethod
    def get_by_type(cls, agent_type: str):
        """Get agents by type"""
        return cls.objects.filter(agent_type=agent_type, is_active=True)
    
    @classmethod
    def get_statistics(cls) -> Dict:
        """Get agent statistics"""
        from django.db.models import Count
        return {
            'total_agents': cls.objects.count(),
            'active_agents': cls.objects.filter(is_active=True).count(),
            'total_conversations': cls.objects.aggregate(
                count=Count('conversations')
            )['count'] or 0,
        }

class Document(models.Model):
    STATUS_CHOICES = [
        ('processing', 'Przetwarzanie'),
        ('ready', 'Gotowy'),
        ('error', 'Błąd'),
    ]

    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['uploaded_at']),
        ]

    def __str__(self):
        return self.title

class Conversation(models.Model):
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='conversations')
    user_id = models.CharField(max_length=100, blank=True, help_text="ID użytkownika (opcjonalne)")
    title = models.CharField(max_length=200, blank=True, help_text="Tytuł konwersacji")
    summary = models.TextField(blank=True, help_text="Podsumowanie konwersacji")
    metadata = models.JSONField(default=dict, help_text="Dodatkowe dane konwersacji")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['session_id']),
            models.Index(fields=['agent', 'is_active']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        title = self.title or f"Konwersacja z {self.agent.name}"
        return f"{title} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"

class Message(models.Model):
    ROLE_CHOICES = [
        ('user', 'Użytkownik'),
        ('assistant', 'Agent/Asystent'),
        ('system', 'System'),
    ]
    
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    metadata = models.JSONField(default=dict, help_text="Metadata wiadomości (tokeny, model, itp.)")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['role']),
        ]

    def __str__(
        self,
    ):
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M')}] {self.get_role_display()}: {self.content[:50]}..."
