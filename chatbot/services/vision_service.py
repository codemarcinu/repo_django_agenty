import base64
import requests
import logging
from pathlib import Path
import io
from PIL import Image

logger = logging.getLogger(__name__)

class VisionService:
    def __init__(self):
        self.base_url = "http://127.0.0.1:11434"
        self.model = "qwen2.5vl:7b"
        
    def _prepare_image_for_ollama(self, image_path: str) -> str:
        """
        Przygotowuje obraz w odpowiednim formacie dla Ollama.
        Rozwiązuje problem 'image: unknown format'.
        """
        try:
            # Wczytaj i przetwórz obraz przez PIL
            with Image.open(image_path) as img:
                # Konwertuj do RGB jeśli potrzebne (usuwa kanał alpha, itp.)
                if img.mode not in ['RGB', 'L']:
                    img = img.convert('RGB')
                
                # Zapisz do buffer jako JPEG (najbardziej kompatybilny format)
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=95)
                buffer.seek(0)
                
                # Enkoduj do base64
                img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
                return img_base64
                
        except Exception as e:
            logger.error(f"Błąd przetwarzania obrazu: {e}")
            # Fallback - spróbuj bezpośrednio
            with open(image_path, 'rb') as img_file:
                return base64.b64encode(img_file.read()).decode('utf-8')
    
    def analyze_receipt(self, image_path: str) -> dict:
        """Analizuje paragon używając Qwen2.5VL przez Ollama."""
        try:
            # POPRAWKA: Użyj nowej metody przygotowania obrazu
            img_base64 = self._prepare_image_for_ollama(image_path)
            
            payload = {
                "model": "qwen2.5vl:7b",
                "prompt": "Analyze this receipt and extract: store name, date, total amount, items with prices. Respond in JSON format in Polish.",
                "images": [img_base64],
                "stream": False,
                "options": {
                    "temperature": 0.1
                }
            }
            
            # Test głównego endpointu
            try:
                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=120  # Zwiększony timeout dla modeli wizyjnych
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return {
                        'success': True,
                        'extracted_text': result.get('response', ''),
                        'endpoint_used': '/api/generate'
                    }
                else:
                    logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Connection error: {e}")
            
            return {
                'success': False,
                'error': 'Ollama vision API failed'
            }
            
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return {'success': False, 'error': str(e)}

# Dodatkowa funkcja pomocnicza
def test_vision_service():
    """Szybki test czy vision service działa."""
    try:
        response = requests.get("http://127.0.0.1:11434/api/tags")
        if response.status_code == 200:
            models = [tag['name'] for tag in response.json().get('models', [])]
            vision_models = [m for m in models if 'vl' in m or 'vision' in m]
            logger.info(f"Available vision models: {vision_models}")
            return len(vision_models) > 0
    except Exception as e:
        logger.error(f"Ollama connection test failed: {e}")
        return False