from rest_framework import serializers

from inventory.models import Receipt
from chatbot.models import Agent, Document


class AgentSerializer(serializers.ModelSerializer):
    description = serializers.SerializerMethodField()

    class Meta:
        model = Agent
        fields = ["name", "agent_type", "capabilities", "description", "is_active"]

    def get_description(self, obj):
        if len(obj.persona_prompt) > 200:
            return obj.persona_prompt[:200] + "..."
        return obj.persona_prompt


class ConversationCreateSerializer(serializers.Serializer):
    agent_name = serializers.CharField(max_length=100)
    user_id = serializers.CharField(max_length=100, default="anonymous")
    title = serializers.CharField(max_length=200, required=False)


class ChatMessageSerializer(serializers.Serializer):
    session_id = serializers.CharField(max_length=100)
    message = serializers.CharField()


class ReceiptStatusSerializer(serializers.ModelSerializer):
    redirect_url = serializers.SerializerMethodField()

    class Meta:
        model = Receipt
        fields = ["status", "error_message", "redirect_url"]

    def get_redirect_url(self, obj):
        if obj.status == "ready_for_review":
            from django.urls import reverse

            return reverse("chatbot:receipt_review", kwargs={"receipt_id": obj.id})
        return None


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["id", "title", "file", "uploaded_at"]



