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
        """Analizuje paragon używając Qwen2.5VL przez Ollama."""
        import requests
        import base64
        
        # Konwertuj obraz na base64
        with open(image_path, 'rb') as img_file:
            img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
        
        payload = {
            "model": "qwen2.5vl:7b",
            "prompt": "Analyze this receipt and extract: store name, date, total amount, items with prices. Respond in JSON format in Polish.",
            "images": [img_base64],
            "stream": False,
            "options": {
                "temperature": 0.1
            }
        }
        
        try:
            # Test różnych endpoint'ów
            endpoints_to_try = [
                "/api/generate",
                "/v1/chat/completions", 
                "/api/chat"
            ]
            
            for endpoint in endpoints_to_try:
                try:
                    response = requests.post(
                        f"http://127.0.0.1:11434{endpoint}",
                        json=payload,
                        timeout=60
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        return {
                            'success': True,
                            'extracted_text': result.get('response', result.get('message', {}).get('content', '')),
                            'endpoint_used': endpoint
                        }
                        
                except requests.exceptions.RequestException:
                    continue
                    
            # Jeśli żaden endpoint nie działa
            return {
                'success': False,
                'error': 'All Ollama endpoints failed'
            }
            
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return {'success': False, 'error': str(e)}

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
