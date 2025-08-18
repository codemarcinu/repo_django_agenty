"""
Vision service for analyzing images using Ollama vision models.
Updated to use /api/chat format for Qwen2.5-VL and other vision models.
"""

import base64
import logging
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class VisionResult:
    """Result from vision model analysis"""
    success: bool
    content: str
    model_used: str
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class VisionService:
    """
    Service for image analysis using Ollama vision models.
    Uses the new /api/chat format for better compatibility.
    """
    
    def __init__(self, ollama_url: str = "http://127.0.0.1:11434"):
        self.ollama_url = ollama_url.rstrip('/')
        self.default_model = "qwen2.5-vl:7b"
        self.timeout = 120.0
        
        # Model-specific configurations
        self.model_configs = {
            "qwen2.5-vl:7b": {
                "temperature": 0.3,
                "top_p": 0.8,
                "num_ctx": 4096,
                "num_predict": 1024
            },
            "llava:7b": {
                "temperature": 0.4,
                "top_p": 0.9,
                "num_ctx": 3072,
                "num_predict": 512
            }
        }
    
    def _encode_image_to_base64(self, image_path: str) -> str:
        """
        Encode image to base64 for API transmission.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Base64 encoded image with data URI prefix
        """
        try:
            with open(image_path, 'rb') as image_file:
                image_data = image_file.read()
                b64_string = base64.b64encode(image_data).decode('utf-8')
                
                # Determine MIME type based on file extension
                import os
                ext = os.path.splitext(image_path)[1].lower()
                mime_type = {
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.gif': 'image/gif',
                    '.bmp': 'image/bmp',
                    '.webp': 'image/webp'
                }.get(ext, 'image/jpeg')
                
                return f"data:{mime_type};base64,{b64_string}"
                
        except Exception as e:
            logger.error(f"Failed to encode image {image_path}: {e}")
            raise
    
    async def analyze_image(
        self, 
        image_path: str, 
        prompt: str,
        model: Optional[str] = None
    ) -> VisionResult:
        """
        Analyze image using vision model with the new /api/chat format.
        
        Args:
            image_path: Path to image file
            prompt: Text prompt for analysis
            model: Vision model to use (defaults to qwen2.5-vl:7b)
            
        Returns:
            VisionResult with analysis
        """
        model = model or self.default_model
        
        try:
            logger.info(f"🖼️ Analyzing image with {model}: {image_path}")
            
            # Encode image
            b64_image = self._encode_image_to_base64(image_path)
            
            # Prepare payload using /api/chat format
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image",
                                "image": b64_image
                            }
                        ]
                    }
                ],
                "stream": False,
                "options": self.model_configs.get(model, {})
            }
            
            # Make API request
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {
                    'Content-Type': 'application/json',
                    'User-Agent': 'agenty-vision-service/1.0'
                }
                
                response = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json=payload,
                    headers=headers
                )
                
                response.raise_for_status()
                result = response.json()
                
                # Extract response content
                content = result.get("message", {}).get("content", "")
                
                if not content:
                    return VisionResult(
                        success=False,
                        content="",
                        model_used=model,
                        error="Empty response from vision model"
                    )
                
                logger.info(f"✅ Vision analysis completed: {len(content)} characters")
                
                return VisionResult(
                    success=True,
                    content=content,
                    model_used=model,
                    metadata={
                        "response_length": len(content),
                        "model_config": self.model_configs.get(model, {}),
                        "image_path": image_path
                    }
                )
                
        except httpx.HTTPError as e:
            error_msg = f"HTTP error during vision analysis: {e}"
            logger.error(error_msg)
            return VisionResult(
                success=False,
                content="",
                model_used=model,
                error=error_msg
            )
        except Exception as e:
            error_msg = f"Vision analysis failed: {e}"
            logger.error(error_msg, exc_info=True)
            return VisionResult(
                success=False,
                content="",
                model_used=model,
                error=error_msg
            )
    
    async def analyze_receipt(self, image_path: str, model: Optional[str] = None) -> VisionResult:
        """
        Specialized method for receipt analysis.
        
        Args:
            image_path: Path to receipt image
            model: Vision model to use
            
        Returns:
            VisionResult with receipt analysis
        """
        receipt_prompt = """Przeanalizuj ten paragon i zwróć TYLKO JSON z produktami w następującym formacie:

[
    {
        "product": "nazwa produktu",
        "quantity": 1.0,
        "unit": "szt.",
        "price": 12.34
    }
]

Wyciągnij wszystkie produkty z ich cenami. Jeśli nie możesz określić ilości, użyj 1.0. Jeśli nie możesz określić jednostki, użyj "szt.".
WAŻNE: Zwróć TYLKO JSON, bez dodatkowych komentarzy."""

        result = await self.analyze_image(image_path, receipt_prompt, model)
        
        if result.success:
            # Try to parse JSON from response
            try:
                # Extract JSON from response
                content = result.content.strip()
                
                # Find JSON array in response
                json_start = content.find("[")
                json_end = content.rfind("]")
                
                if json_start != -1 and json_end != -1 and json_end > json_start:
                    json_string = content[json_start:json_end + 1]
                    parsed_json = json.loads(json_string)
                    
                    # Validate JSON structure
                    if isinstance(parsed_json, list):
                        logger.info(f"✅ Receipt JSON parsed: {len(parsed_json)} products")
                        
                        # Add parsed data to metadata
                        if result.metadata is None:
                            result.metadata = {}
                        result.metadata["parsed_products"] = parsed_json
                        result.metadata["products_count"] = len(parsed_json)
                
            except json.JSONDecodeError as e:
                logger.warning(f"Could not parse JSON from vision response: {e}")
                if result.metadata is None:
                    result.metadata = {}
                result.metadata["json_parse_error"] = str(e)
        
        return result
    
    async def analyze_document(self, image_path: str, model: Optional[str] = None) -> VisionResult:
        """
        Specialized method for general document analysis.
        
        Args:
            image_path: Path to document image
            model: Vision model to use
            
        Returns:
            VisionResult with document analysis
        """
        document_prompt = """Przeanalizuj ten dokument i opisz:
1. Typ dokumentu (faktura, paragon, dokument urzędowy, itp.)
2. Kluczowe informacje (daty, kwoty, nazwy firm, numery)
3. Strukturę dokumentu (tabele, sekcje, nagłówki)
4. Stan dokumentu (czytelność, jakość)

Odpowiedź podaj w języku polskim, w sposób strukturalny."""

        return await self.analyze_image(image_path, document_prompt, model)
    
    async def describe_image(self, image_path: str, model: Optional[str] = None) -> VisionResult:
        """
        General image description.
        
        Args:
            image_path: Path to image
            model: Vision model to use
            
        Returns:
            VisionResult with image description
        """
        description_prompt = """Opisz szczegółowo co widzisz na tym obrazie. 
Uwzględnij obiekty, tekst, kolory, kompozycję i kontekst.
Odpowiedź podaj w języku polskim."""

        return await self.analyze_image(image_path, description_prompt, model)
    
    async def check_model_availability(self, model: str) -> bool:
        """
        Check if vision model is available in Ollama.
        
        Args:
            model: Model name to check
            
        Returns:
            True if model is available
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.ollama_url}/api/tags")
                
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", [])
                    available_models = [m.get("name", "") for m in models]
                    
                    is_available = model in available_models
                    logger.info(f"Model {model} availability: {is_available}")
                    return is_available
                
        except Exception as e:
            logger.error(f"Failed to check model availability: {e}")
        
        return False
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get service configuration and status"""
        return {
            "service": "VisionService",
            "ollama_url": self.ollama_url,
            "default_model": self.default_model,
            "timeout": self.timeout,
            "supported_models": list(self.model_configs.keys()),
            "api_format": "/api/chat",
            "features": [
                "receipt_analysis",
                "document_analysis", 
                "general_description",
                "json_extraction"
            ]
        }


# Global service instance
vision_service = VisionService()