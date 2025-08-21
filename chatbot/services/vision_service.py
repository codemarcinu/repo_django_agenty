# W pliku chatbot/services/vision_service.py

import base64
import requests
import logging
from pathlib import Path
import io
from PIL import Image
import os

logger = logging.getLogger(__name__)

class VisionService:
    def __init__(self):
        self.base_url = "http://127.0.0.1:11434"
        self.model = "qwen2.5vl:7b"
        
    def _convert_pdf_to_image(self, pdf_path: str) -> str:
        """
        Konwertuje PDF na obraz (pierwsza strona).
        Zwraca ścieżkę do utworzonego obrazu.
        """
        try:
            import fitz  # PyMuPDF
            
            # Otwórz PDF
            doc = fitz.open(pdf_path)
            page = doc[0]  # Pierwsza strona
            
            # Konwertuj do obrazu (300 DPI dla lepszej jakości)
            mat = fitz.Matrix(300/72, 300/72)  # 300 DPI
            pix = page.get_pixmap(matrix=mat)
            
            # Zapisz jako PNG w temp
            temp_image_path = pdf_path.replace('.pdf', '_temp.png')
            pix.save(temp_image_path)
            doc.close()
            
            logger.info(f"PDF converted to image: {temp_image_path}")
            return temp_image_path
            
        except Exception as e:
            logger.error(f"PDF conversion failed: {e}")
            # Fallback - spróbuj pdf2image
            try:
                from pdf2image import convert_from_path
                pages = convert_from_path(pdf_path, first_page=1, last_page=1, dpi=300)
                if pages:
                    temp_image_path = pdf_path.replace('.pdf', '_temp.png')
                    pages[0].save(temp_image_path, 'PNG')
                    logger.info(f"PDF converted via pdf2image: {temp_image_path}")
                    return temp_image_path
            except Exception as e2:
                logger.error(f"pdf2image fallback failed: {e2}")
            
            raise ValueError(f"Cannot convert PDF to image: {e}")
    
    def _prepare_image_for_ollama(self, image_path: str) -> str:
        """
        Przygotowuje obraz w odpowiednim formacie dla Ollama.
        Obsługuje PDF i obrazy.
        """
        try:
            processed_image_path = image_path
            
            # Sprawdź czy to PDF - jeśli tak, konwertuj
            if image_path.lower().endswith('.pdf'):
                processed_image_path = self._convert_pdf_to_image(image_path)
            
            # Wczytaj i przetwórz obraz przez PIL
            with Image.open(processed_image_path) as img:
                # Konwertuj do RGB jeśli potrzebne
                if img.mode not in ['RGB']:
                    img = img.convert('RGB')
                
                # Opcjonalnie zmień rozmiar dla wydajności
                max_size = 2048
                if max(img.size) > max_size:
                    ratio = max_size / max(img.size)
                    new_size = (int(img.width * ratio), int(img.height * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                    logger.info(f"Image resized to {new_size}")
                
                # Zapisz do buffer jako JPEG
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=95)
                buffer.seek(0)
                
                # Enkoduj do base64
                img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
                
            # Wyczyść temp file jeśli był utworzony
            if processed_image_path != image_path and os.path.exists(processed_image_path):
                try:
                    os.remove(processed_image_path)
                    logger.debug(f"Removed temp file: {processed_image_path}")
                except:
                    pass
                
                return img_base64
                
        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            raise ValueError(f"Cannot process image/PDF: {e}")
    
    def analyze_receipt(self, image_path: str) -> dict:
        """Analizuje paragon używając Qwen2.5VL przez Ollama."""
        try:
            logger.info(f"Processing receipt file: {image_path}")
            
            # Przygotuj obraz (obsługuje PDF i obrazy)
            img_base64 = self._prepare_image_for_ollama(image_path)
            
            payload = {
                "model": "qwen2.5vl:7b",
                "prompt": "Analyze this receipt and extract: store name, date, total amount, items with prices. Respond in JSON format in Polish.",
                "images": [img_base64],
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 2000  # Zwiększ limit tokenów dla JSON
                }
            }
            
            logger.info("Sending request to Ollama vision model...")
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=180  # 3 minuty dla vision modelu
            )
            
            if response.status_code == 200:
                result = response.json()
                extracted_text = result.get('response', '')
                
                if extracted_text:
                    logger.info(f"✅ Vision analysis successful (length: {len(extracted_text)})")
                    return {
                        'success': True,
                        'extracted_text': extracted_text,
                        'endpoint_used': '/api/generate',
                        'model_used': 'qwen2.5vl:7b'
                    }
                else:
                    logger.warning("Empty response from vision model")
                    return {
                        'success': False,
                        'error': 'Empty response from vision model'
                    }
            else:
                error_text = response.text
                logger.error(f"❌ Ollama API error: {response.status_code} - {error_text}")
                return {
                    'success': False,
                    'error': f'Ollama API error: {response.status_code}'
                }
                
        except Exception as e:
            logger.error(f"❌ Vision analysis failed: {e}", exc_info=True)
            return {
                'success': False, 
                'error': f'Vision analysis failed: {str(e)}'
            }

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