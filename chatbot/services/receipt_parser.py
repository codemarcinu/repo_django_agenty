# W pliku repo_django_agenty/chatbot/services/receipt_parser.py

import logging
from dataclasses import dataclass  # Added import

from ..config.receipt_config import get_parser_config
from ..interfaces import ReceiptParser
from .receipt_llm_service import ReceiptLLMService

logger = logging.getLogger(__name__)

# Define ParsedProduct dataclass
@dataclass
class ParsedProduct:
    name: str
    quantity: float
    price: float
    total_price: float = 0.0 # Optional: calculated if not provided

    def __post_init__(self):
        if self.total_price == 0.0:
            self.total_price = self.quantity * self.price

# --- Implementacje konkretnych parserów ---

class RegexReceiptParser(ReceiptParser):
    """Prosty parser oparty na wyrażeniach regularnych."""
    def parse(self, raw_text: str) -> list[ParsedProduct]: # Changed return type
        logger.info("Using RegexReceiptParser")
        # Uproszczona logika dla przykładu
        # Return a list of ParsedProduct objects
        return [
            ParsedProduct(name="Unknown Item 1 (Regex)", quantity=1.0, price=10.00),
            ParsedProduct(name="Unknown Item 2 (Regex)", quantity=2.0, price=5.00)
        ]

class LidlReceiptParser(ReceiptParser):
    """Dedykowany parser dla paragonów z Lidla."""
    def parse(self, raw_text: str) -> list[ParsedProduct]: # Changed return type
        logger.info("Using LidlReceiptParser")
        # Tutaj docelowo będzie zaawansowana logika parsowania dla Lidla
        # Return a list of ParsedProduct objects
        return [
            ParsedProduct(name="Lidl Product A", quantity=1.0, price=15.50),
            ParsedProduct(name="Lidl Product B", quantity=0.5, price=20.00)
        ]

# --- GŁÓWNY ADAPTER PARSERA ---

class AdaptiveReceiptParser:
    """
    Klasa-adapter, która dynamicznie wybiera odpowiedni parser
    na podstawie słów kluczowych znalezionych w tekście paragonu.
    """

    def __init__(self, default_parser=None):
        self.parsers = {}
        self.default_parser = default_parser or BasicReceiptParser()
        
    def parse(self, text: str, vision_result: dict = None) -> dict:
        """
        Parse receipt text with optional vision result.
        """
        # NOWA FUNKCJA: Jeśli mamy vision result, użyj go
        if vision_result and vision_result.get('success'):
            try:
                return self._parse_vision_result(vision_result)
            except Exception as e:
                logger.warning(f"Vision parsing failed: {e}, falling back to text")
        
        # Fallback do tekstowego parsowania
        return self.default_parser.parse(text)
    
    def _parse_vision_result(self, vision_result: dict) -> dict:
        """Parse vision model JSON response."""
        import json
        
        vision_text = vision_result.get('extracted_text', '')
        
        # Znajdź JSON
        json_start = vision_text.find('{')
        json_end = vision_text.rfind('}') + 1
        
        if json_start < 0 or json_end <= json_start:
            raise ValueError("No valid JSON in vision result")
        
        vision_json_str = vision_text[json_start:json_end]
        vision_data = json.loads(vision_json_str)
        
        # Konwertuj do standardowego formatu
        products = []
        for item in vision_data.get('items', []):
            price_str = str(item.get('cena', '0')).replace(' PLN', '').replace(',', '.')
            quantity_str = str(item.get('ilość', '1')).replace(',', '.')
            
            try:
                product = {
                    "product": str(item.get('nazwa', '')).strip(),
                    "quantity": float(quantity_str) if quantity_str else 1.0,
                    "unit": "szt.",
                    "price": float(price_str) if price_str else 0.0
                }
                
                if product['product'] and len(product['product']) > 1:
                    products.append(product)
                    
            except (ValueError, TypeError) as e:
                logger.warning(f"Skipping invalid product: {item} ({e})")
                continue
        
        total_str = str(vision_data.get('total', '0')).replace(' PLN', '').replace(',', '.')
        
        result = {
            "store_name": str(vision_data.get('sklep', '')).strip(),
            "total_amount": float(total_str) if total_str else 0.0,
            "date": str(vision_data.get('data', '')).strip(),
            "products": products,
            "parser_used": "vision_parser", 
            "confidence": 0.9
        }
        
        logger.info(f"Vision parser extracted {len(products)} products")
        return result

# --- FUNKCJA TWORZĄCA INSTANCJĘ (Singleton Pattern) ---

_receipt_parser_instance = None

def get_receipt_parser() -> AdaptiveReceiptParser:
    """
    Tworzy i zwraca pojedynczą, w pełni skonfigurowaną instancję AdaptiveReceiptParser.
    To rozwiązuje problem kolistych importów.
    """
    global _receipt_parser_instance
    if _receipt_parser_instance is None:
        # 1. Stwórz domyślny parser (może to być LLM lub prosty Regex)
        # Na razie używamy Regex jako podstawy.
        default_parser = ReceiptLLMService()

        # 2. Stwórz główny adapter z domyślnym parserem
        instance = AdaptiveReceiptParser(default_parser=default_parser)

        # 3. Zarejestruj dedykowane parsery na podstawie konfiguracji
        parser_config = get_parser_config()
        for keyword, parser_info in parser_config.items():
            # Zakładamy, że parser_info['class'] to klasa, a nie string
            parser_class = parser_info.get('class')
            if parser_class:
                # Sprawdzenie, czy klasa jest znana, aby uniknąć dynamicznego importu, który może być niebezpieczny
                # i powodować problemy z zależnościami.
                known_parsers = {
                    "LidlReceiptParser": LidlReceiptParser,
                    "RegexReceiptParser": RegexReceiptParser,
                    "ReceiptLLMService": ReceiptLLMService
                }
                if parser_class in known_parsers:
                    instance.register_parser(keyword, known_parsers[parser_class]())
                else:
                    logger.warning(f"Unknown parser class '{parser_class}' in config for keyword '{keyword}'.")

        _receipt_parser_instance = instance

    return _receipt_parser_instance
