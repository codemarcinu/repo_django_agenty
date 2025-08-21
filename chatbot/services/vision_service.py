# W pliku chatbot/services/vision_service.py

import httpx
import base64
import logging
from django.conf import settings
from typing import Dict, Any, Optional
import json
from pathlib import Path
from pdf2image import convert_from_path
import tempfile

logger = logging.getLogger(__name__)


class VisionService:
    """
    Serwis do interakcji z modelami wizyjnymi w celu ekstrakcji danych z obrazów.
    Używa lokalnego serwera Ollama.
    """
    DEFAULT_PROMPT = """
    Jesteś ekspertem w analizie paragonów. Przeanalizuj ten obraz paragonu i zwróć listę produktów w formacie JSON.
    Każdy produkt powinien zawierać 'name' (nazwa), 'quantity' (ilość) i 'price' (cena).
    Odpowiedź zwracaj w postaci samego JSONa, bez żadnych dodatkowych opisów.
    """

    def __init__(self, model_name: str = "qwen2.5vl:7b", ollama_base_url: Optional[str] = None):
        self.model_name = model_name
        self.ollama_base_url = ollama_base_url or settings.OLLAMA_API_BASE_URL
        self.api_url = f"{self.ollama_base_url}/api/generate"
        logger.info(f"VisionService initialized for model: {self.model_name} at {self.api_url}")

    def _get_image_bytes(self, image_path: Path) -> Optional[bytes]:
        """
        Konwertuje plik (w tym PDF) na bajty obrazu PNG.
        """
        try:
            if image_path.suffix.lower() == '.pdf':
                logger.info(f"Wykryto plik PDF. Konwertowanie na obraz: {image_path}")
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_image:
                    # Konwertuj pierwszą stronę PDF do obrazu
                    images = convert_from_path(image_path, first_page=1, last_page=1, fmt='png', single_file=True, poppler_path=settings.POPPLER_PATH)
                    if images:
                        images[0].save(temp_image.name, 'PNG')
                        temp_image.seek(0)
                        return temp_image.read()
                    else:
                        logger.error(f"Nie udało się skonwertować PDF: {image_path}")
                        return None
            else:
                # Dla standardowych formatów obrazu, po prostu odczytaj plik
                with image_path.open("rb") as f:
                    return f.read()
        except Exception as e:
            logger.error(f"Błąd podczas przetwarzania pliku {image_path}: {e}")
            return None

    async def extract_data_from_image(self, image_path: str, prompt: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Przesyła obraz do modelu wizyjnego i zwraca wyekstrahowane dane w formacie JSON.
        """
        final_prompt = prompt or self.DEFAULT_PROMPT
        logger.info(f"🖼️ Analizuję plik z {self.model_name}: {image_path}")
        
        path = Path(image_path)
        image_bytes = self._get_image_bytes(path)

        if not image_bytes:
            logger.error(f"Nie udało się odczytać lub skonwertować pliku obrazu: {image_path}")
            return None

        encoded_image = base64.b64encode(image_bytes).decode("utf-8")

        payload = {
            "model": self.model_name,
            "prompt": final_prompt,
            "images": [encoded_image],
            "stream": False,
            "options": {"temperature": 0.0}
        }

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(self.api_url, json=payload)
                response.raise_for_status()
                response_json = response.json()
                
                if 'response' in response_json:
                    try:
                        clean_response = response_json['response'].replace("```json", "").replace("```", "").strip()
                        return json.loads(clean_response)
                    except json.JSONDecodeError:
                        logger.error(f"Błąd dekodowania JSON: {response_json['response']}")
                        return {"error": "Invalid JSON response", "raw_response": response_json['response']}
                return response_json

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during vision analysis: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Niespodziewany błąd podczas analizy wizualnej: {e}")
            return None
