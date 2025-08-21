import base64
import requests
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class VisionService:
    def __init__(self):
        self.base_url = "http://127.0.0.1:11434"
        self.model = "qwen2.5-vl:7b"
    
    def analyze_receipt(self, image_path: str) -> dict:
        """Analizuje paragon używając Ollama vision model."""
        import requests
        import base64
        
        # Wczytaj obraz jako base64
        with open(image_path, 'rb') as img_file:
            img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
        
        payload = {
            "model": self.model,
            "prompt": "Przeanalizuj ten paragon i wyciągnij: nazwę sklepu, datę, kwotę całkowitą, pozycje zakupów z cenami. Odpowiedz w formacie JSON.",
            "images": [img_base64],
            "stream": False
        }
        
        try:
            # Użyj poprawnego endpoint'u /api/generate zamiast /api/chat
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            return {
                'success': True,
                'extracted_text': result.get('response', ''),
                'model_used': self.model
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Vision analysis failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _prepare_image_data(self, file_path):
        """Przygotowuje dane obrazu do wysłania do API"""
        with open(file_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    
    def _check_model_availability(self):
        """Sprawdza czy model jest dostępny"""
        try:
            response = requests.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                models = response.json().get('models', [])
                available_models = [model['name'] for model in models]
                logger.info(f"Available models: {available_models}")
                
                if self.model not in available_models:
                    logger.error(f"Model {self.model} not available. Try: ollama pull {self.model}")
            else:
                logger.error(f"Cannot check available models: {response.status_code}")
        except Exception as e:
            logger.error(f"Error checking model availability: {e}")

# Test połączenia
def test_vision_service():
    """Szybki test czy vision service działa."""
    import requests
    
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
