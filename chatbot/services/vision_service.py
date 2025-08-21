import base64
import httpx
import logging
import json
from django.conf import settings
from chatbot.schemas import ParsedReceipt, ProductSchema

logger = logging.getLogger(__name__)

class VisionService:
    def __init__(self):
        # Używamy /api/generate, który jest właściwy dla zapytań z obrazami
        self.api_url = f"{settings.OLLAMA_API_BASE_URL}/api/generate"
        self.model = settings.OLLAMA_VISION_MODEL

    async def extract_data_from_image(self, image_path: str) -> ParsedReceipt:
        logger.info(f"🖼️ Analizuję obraz z {self.model}: {image_path}")
        
        try:
            with open(image_path, "rb") as image_file:
                encoded_image = base64.b64encode(image_file.read()).decode('utf-8')

            # Struktura payloadu dostosowana do /api/generate i modeli wizyjnych
            payload = {
                "model": self.model,
                "prompt": '''
                    Jesteś ekspertem w analizowaniu paragonów. Przeanalizuj ten obraz paragonu i zwróć listę produktów w formacie JSON.
                    Każdy produkt musi mieć 'name', 'quantity' i 'price'.
                    Zwróć TYLKO i WYŁĄCZNIE listę JSON, bez żadnych dodatkowych komentarzy.
                    Przykład: [{"name": "Mleko 2%", "quantity": 1.0, "price": 3.49}, {"name": "Chleb", "quantity": 1.0, "price": 4.50}]
                ''',
                "images": [encoded_image], # Kluczowe dla modeli wizyjnych
                "stream": False,
                "format": "json" # Prosimy Ollamę o zwrócenie JSON
            }

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(self.api_url, json=payload)
                response.raise_for_status()
                
                # Ollama z opcją format: "json" zwraca JSON w polu 'response' jako string
                response_json = response.json()
                parsed_items_data = json.loads(response_json.get("response", "[]"))

                # Konwersja na nasze obiekty Pydantic
                items = [ProductSchema(**item) for item in parsed_items_data]
                return ParsedReceipt(items=items)

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during vision analysis: {e}")
            raise  # Rzucamy błąd dalej, aby Celery mógł go obsłużyć
        except Exception as e:
            logger.error(f"An unexpected error occurred in VisionService: {e}", exc_info=True)
            raise

# Global service instance
vision_service = VisionService()
