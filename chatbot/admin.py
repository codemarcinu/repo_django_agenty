from django.contrib import admin
from django.utils.html import format_html

from .models import Agent, Conversation, Document, Message


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "uploaded_at")
    list_filter = ("status", "uploaded_at")
    search_fields = ("title",)
    readonly_fields = ("uploaded_at", "processed_at")


class MessageInline(admin.TabularInline):
    model = Message
    extra = 1
    readonly_fields = ("created_at",)
    fields = ("role", "content", "created_at")


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "agent_type",
        "is_active",
        "created_at",
        "capabilities_count",
    )
    list_filter = ("agent_type", "is_active", "created_at")
    search_fields = ("name", "persona_prompt")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Podstawowe informacje", {"fields": ("name", "agent_type", "is_active")}),
        (
            "Konfiguracja AI",
            {"fields": ("persona_prompt", "system_prompt", "capabilities", "config")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def capabilities_count(self, obj):
        return len(obj.capabilities) if obj.capabilities else 0

    capabilities_count.short_description = "Zdolności"


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        "title_display",
        "agent",
        "session_id_short",
        "user_id",
        "is_active",
        "message_count",
        "created_at",
    )
    list_filter = ("agent", "is_active", "created_at")
    search_fields = ("title", "user_id", "session_id")
    readonly_fields = ("session_id", "created_at", "updated_at", "message_count")
    inlines = [MessageInline]

    fieldsets = (
        (
            "Informacje o konwersacji",
            {"fields": ("agent", "user_id", "title", "is_active")},
        ),
        ("Szczegóły", {"fields": ("session_id", "summary", "metadata")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def title_display(self, obj):
        return obj.title or f"Konwersacja z {obj.agent.name}"

    title_display.short_description = "Tytuł"

    def session_id_short(self, obj):
        return str(obj.session_id)[:8] + "..."

    session_id_short.short_description = "Session ID"

    def message_count(self, obj):
        return obj.messages.count()

    message_count.short_description = "Wiadomości"


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation_title", "role", "content_preview", "created_at")
    list_filter = ("role", "conversation__agent", "created_at")
    search_fields = ("content", "conversation__title")
    readonly_fields = ("created_at",)

    def conversation_title(self, obj):
        return str(obj.conversation)

    conversation_title.short_description = "Konwersacja"

    def content_preview(self, obj):
        return format_html(
            '<span title="{}">{}</span>',
            obj.content,
            obj.content[:100] + "..." if len(obj.content) > 100 else obj.content,
        )

    content_preview.short_description = "Treść"
