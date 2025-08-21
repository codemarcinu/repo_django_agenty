import base64
import requests
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class VisionService:
    def __init__(self):
        self.base_url = "http://127.0.0.1:11434"
        self.model = "qwen2.5-vl:7b"
    
    def analyze_receipt(self, file_path):
        """Analizuje paragon używając modelu wizyjnego"""
        try:
            # Sprawdź czy plik istnieje
            if not Path(file_path).exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Konwersja PDF do base64 (jeśli potrzebne)
            image_data = self._prepare_image_data(file_path)
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": "Przeanalizuj ten paragon i wyciągnij produkty wraz z cenami.",
                        "images": [image_data]
                    }
                ],
                "stream": False
            }
            
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=60
            )
            
            if response.status_code == 400:
                # Loguj szczegóły błędu 400
                logger.error(f"API returned 400 Bad Request. Response: {response.text}")
                
                # Sprawdź czy model jest dostępny
                self._check_model_availability()
                return None
            
            response.raise_for_status()
            result = response.json()
            
            return result.get('message', {}).get('content', '')
            
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error during vision analysis: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in vision service: {e}")
            return None
    
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