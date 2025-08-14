from django.db import models
from django.core.exceptions import ValidationError
import json
import uuid
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

    def __str__(self):
        return f"{self.name} - {self.quantity} {self.unit}"


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

    def __str__(self):
        return f"Paragon {self.id} - Status: {self.get_status_display()}"


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
