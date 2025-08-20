import uuid

from django.db import models
from django.urls import reverse
from django.utils import timezone

from .validators import validate_receipt_file





class Agent(models.Model):
    AGENT_TYPE_CHOICES = [
        ("router", "Router Agent"),
        ("ollama", "Ollama (Legacy)"),
    ]

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unikalna nazwa agenta, np. 'Generalista'",
    )
    agent_type = models.CharField(
        max_length=20, choices=AGENT_TYPE_CHOICES, default="general"
    )
    persona_prompt = models.TextField(
        help_text="Opis osobowości i zadania agenta, który będzie używany w promptach LLM."
    )
    system_prompt = models.TextField(
        blank=True, help_text="Systemowy prompt dla agenta"
    )
    capabilities = models.JSONField(default=list, help_text="Lista zdolności agenta")
    config = models.JSONField(default=dict, help_text="Konfiguracja agenta")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["agent_type", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_agent_type_display()})"

    def save(self, *args, **kwargs):
        # Force-correct the known bad model name for Ollama agents
        if (
            self.agent_type == "ollama"
            and self.config
            and isinstance(self.config, dict)
            and "model" in self.config
        ):
            bad_name = "SpeakLeash/bielik-11b-v2.3 instruct:Q5_K_M"
            correct_name = "SpeakLeash/bielik-11b-v2.3-instruct:Q5_K_M"
            if self.config.get("model") == bad_name:
                self.config["model"] = correct_name

        super().save(*args, **kwargs)  # Call the original save method

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
        return self.conversations.filter(is_active=True).order_by("-updated_at")[:limit]

    @classmethod
    def get_active_agents(cls):
        """Get all active agents"""
        return cls.objects.filter(is_active=True).order_by("name")

    @classmethod
    def get_by_type(cls, agent_type: str):
        """Get agents by type"""
        return cls.objects.filter(agent_type=agent_type, is_active=True)

    @classmethod
    def get_statistics(cls) -> dict:
        """Get agent statistics"""
        from django.db.models import Count

        return {
            "total_agents": cls.objects.count(),
            "active_agents": cls.objects.filter(is_active=True).count(),
            "total_conversations": cls.objects.aggregate(count=Count("conversations"))[
                "count"
            ]
            or 0,
        }


class Document(models.Model):
    STATUS_CHOICES = [
        ("processing", "Przetwarzanie"),
        ("ready", "Gotowy"),
        ("error", "Błąd"),
    ]

    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="documents/")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="processing"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["uploaded_at"]),
        ]

    def __str__(self):
        return self.title


class Conversation(models.Model):
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    agent = models.ForeignKey(
        Agent, on_delete=models.CASCADE, related_name="conversations"
    )
    user_id = models.CharField(
        max_length=100, blank=True, help_text="ID użytkownika (opcjonalne)"
    )
    title = models.CharField(max_length=200, blank=True, help_text="Tytuł konwersacji")
    summary = models.TextField(blank=True, help_text="Podsumowanie konwersacji")
    metadata = models.JSONField(default=dict, help_text="Dodatkowe dane konwersacji")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["session_id"]),
            models.Index(fields=["agent", "is_active"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        title = self.title or f"Konwersacja z {self.agent.name}"
        return f"{title} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"


class Message(models.Model):
    ROLE_CHOICES = [
        ("user", "Użytkownik"),
        ("assistant", "Agent/Asystent"),
        ("system", "System"),
    ]

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    metadata = models.JSONField(
        default=dict, help_text="Metadata wiadomości (tokeny, model, itp.)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["role"]),
        ]

    def __str__(
        self,
    ):
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M')}] {self.get_role_display()}: {self.content[:50]}..."


class ProductCorrection(models.Model):
    """
    Records a user's correction to a product name extracted from a receipt.
    This data can be used to improve future OCR and product matching.
    """
    original_product_name = models.CharField(
        max_length=255,
        help_text="The product name as initially extracted by OCR/LLM."
    )
    corrected_product_name = models.CharField(
        max_length=255,
        help_text="The product name as corrected by the user."
    )
    # Link to the specific line item that was corrected
    receipt_line_item = models.ForeignKey(
        'inventory.ReceiptLineItem', # Assuming ReceiptLineItem is in the inventory app
        on_delete=models.CASCADE,
        related_name='corrections',
        null=True, # Allow null if the line item is deleted
        blank=True
    )
    # Link to the Product model if the user selected an existing product
    matched_product = models.ForeignKey(
        'inventory.Product', # Assuming Product is in the inventory app
        on_delete=models.SET_NULL,
        related_name='corrections_as_matched',
        null=True,
        blank=True,
        help_text="The product that the user matched the item to (if existing)."
    )
    # Optional: User who made the correction
    user = models.ForeignKey(
        'auth.User', # Assuming Django's default User model
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="The user who made the correction."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Product Correction"
        verbose_name_plural = "Product Corrections"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['original_product_name']),
            models.Index(fields=['corrected_product_name']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"'{self.original_product_name}' corrected to '{self.corrected_product_name}'"
