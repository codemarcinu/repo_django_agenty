"""
Model routing service for selecting appropriate models based on task type.
Based on performance analysis for RTX 3060 12GB VRAM.
"""

import logging
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Types of tasks for model routing"""
    GENERAL_CHAT = "general_chat"
    POLISH_HEAVY = "polish_heavy"
    VISION_RECEIPT = "vision_receipt"
    VISION_DOCUMENT = "vision_document"
    FALLBACK = "fallback"


class ModelRouter:
    """
    Intelligent model router for RTX 3060 optimized performance.
    
    Model Strategy:
    - qwen2:7b: Default workhorse (~4-5GB VRAM, fast)
    - qwen2.5vl:7b: Vision tasks (documents, receipts)
    - jobautomation/OpenEuroLLM-Polish: Heavy Polish tasks only (8.1GB)
    - mistral:7b: Fallback model
    """

    def __init__(self):
        self.models = {
            TaskType.GENERAL_CHAT: "qwen2:7b",
            TaskType.POLISH_HEAVY: "jobautomation/OpenEuroLLM-Polish",
            TaskType.VISION_RECEIPT: "qwen2.5vl:7b",
            TaskType.VISION_DOCUMENT: "qwen2.5vl:7b",
            TaskType.FALLBACK: "mistral:7b"
        }

        # Model configurations optimized for RTX 3060
        self.model_configs = {
            "qwen2:7b": {
                "num_ctx": 8192,
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 2048
            },
            "qwen2.5vl:7b": {
                "num_ctx": 4096,
                "temperature": 0.3,  # Lower for more precise vision analysis
                "top_p": 0.8,
                "num_predict": 1024
            },
            "jobautomation/OpenEuroLLM-Polish": {
                "num_ctx": 4096,  # Reduced to save VRAM
                "temperature": 0.8,
                "top_p": 0.9,
                "num_predict": 2048
            },
            "mistral:7b": {
                "num_ctx": 8192,
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 2048
            }
        }

        # Polish language indicators
        self.polish_indicators = [
            'długi tekst po polsku', 'szczegółowa odpowiedź', 'polskie zwroty',
            'gramatyka polska', 'odmiana', 'sklonenie', 'historia polski',
            'kultura polska', 'literatura polska'
        ]

        # Vision task indicators
        self.vision_indicators = [
            'paragon', 'rachunek', 'faktura', 'dokument', 'zdjęcie', 'obrazek',
            'receipt', 'invoice', 'document', 'image', 'photo', 'picture',
            'przeanalizuj obraz', 'co widzisz', 'opisz zdjęcie'
        ]

    def detect_task_type(self, input_data: dict[str, Any]) -> TaskType:
        """
        Detect task type based on input data.
        
        Args:
            input_data: Dictionary containing message, history, and metadata
            
        Returns:
            TaskType enum value
        """
        message = input_data.get("message", "").lower()
        metadata = input_data.get("metadata", {})

        # Check for vision tasks first (highest priority)
        if self._has_image_data(input_data) or any(indicator in message for indicator in self.vision_indicators):
            # Specific check for receipts
            if any(word in message for word in ['paragon', 'rachunek', 'receipt']):
                return TaskType.VISION_RECEIPT
            return TaskType.VISION_DOCUMENT

        # Check for heavy Polish language tasks
        if self._is_polish_heavy_task(message, metadata):
            return TaskType.POLISH_HEAVY

        # Default to general chat
        return TaskType.GENERAL_CHAT

    def _has_image_data(self, input_data: dict[str, Any]) -> bool:
        """Check if input contains image data"""
        return (
            'image' in input_data or
            'images' in input_data or
            'file_path' in input_data.get('metadata', {}) and
            any(ext in input_data['metadata']['file_path'].lower()
                for ext in ['.jpg', '.jpeg', '.png', '.pdf', '.tiff'])
        )

    def _is_polish_heavy_task(self, message: str, metadata: dict[str, Any]) -> bool:
        """
        Determine if task requires heavy Polish language processing.
        Only use Polish model when it provides clear benefit.
        """
        # Check for explicit Polish language indicators
        polish_score = sum(1 for indicator in self.polish_indicators if indicator in message)

        # Check message length and complexity
        message_length = len(message.split())

        # Use Polish model only for:
        # 1. Long Polish texts (>100 words) OR
        # 2. Tasks with multiple Polish language indicators OR
        # 3. Explicitly marked as Polish-heavy in metadata
        return (
            polish_score >= 2 or
            (message_length > 100 and any(indicator in message for indicator in self.polish_indicators[:3])) or
            metadata.get('force_polish_model', False)
        )

    def get_model_for_task(self, task_type: TaskType, fallback: bool = False) -> str:
        """
        Get appropriate model for task type.
        
        Args:
            task_type: Type of task
            fallback: If True, return fallback model
            
        Returns:
            Model name string
        """
        if fallback:
            return self.models[TaskType.FALLBACK]

        return self.models.get(task_type, self.models[TaskType.GENERAL_CHAT])

    def get_model_config(self, model_name: str) -> dict[str, Any]:
        """Get optimized configuration for model"""
        return self.model_configs.get(model_name, self.model_configs["qwen2:7b"])

    def route_request(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """
        Main routing method. Returns model and config for request.
        
        Args:
            input_data: Request data
            
        Returns:
            Dictionary with model, config, and task_type
        """
        task_type = self.detect_task_type(input_data)
        model_name = self.get_model_for_task(task_type)
        model_config = self.get_model_config(model_name)

        logger.info(f"Routed task to {task_type.value} -> {model_name}")

        return {
            "model": model_name,
            "config": model_config,
            "task_type": task_type.value,
            "routing_metadata": {
                "original_model": "auto-routed",
                "task_detected": task_type.value,
                "model_selected": model_name
            }
        }

    def get_fallback_route(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Get fallback routing when primary model fails"""
        model_name = self.get_model_for_task(TaskType.FALLBACK, fallback=True)
        model_config = self.get_model_config(model_name)

        logger.warning(f"Using fallback model: {model_name}")

        return {
            "model": model_name,
            "config": model_config,
            "task_type": "fallback",
            "routing_metadata": {
                "original_model": "fallback",
                "task_detected": "fallback",
                "model_selected": model_name
            }
        }

    def get_available_models(self) -> dict[str, str]:
        """Get list of available models"""
        return {task_type.value: model for task_type, model in self.models.items()}

    def get_model_info(self) -> dict[str, Any]:
        """Get detailed information about model router configuration"""
        return {
            "strategy": "RTX 3060 optimized 7B stack",
            "models": self.get_available_models(),
            "configs": self.model_configs,
            "routing_logic": {
                "vision_tasks": "qwen2.5vl:7b",
                "polish_heavy": "jobautomation/OpenEuroLLM-Polish (selective)",
                "default": "qwen2:7b",
                "fallback": "mistral:7b"
            },
            "vram_usage": {
                "qwen2:7b": "~4-5GB",
                "qwen2.5vl:7b": "~6GB",
                "jobautomation/OpenEuroLLM-Polish": "~8.1GB",
                "mistral:7b": "~4.4GB"
            }
        }


# Global router instance
model_router = ModelRouter()
