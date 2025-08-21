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

    def __init__(self, default_parser: ReceiptParser):
        self._parsers: dict[str, ReceiptParser] = {}
        self._default_parser: ReceiptParser = default_parser
        self.register_parser("default", default_parser)
        logger.info(f"Initialized AdaptiveReceiptParser with default: {default_parser.__class__.__name__}")

    def register_parser(self, keyword: str, parser: ReceiptParser):
        """Rejestruje nowy parser dla danego słowa kluczowego."""
        self._parsers[keyword.lower()] = parser
        logger.info(f"Registered parser {parser.__class__.__name__} for keyword '{keyword}'")

    def select_parser(self, raw_text: str) -> ReceiptParser:
        """Wybiera najlepszy parser na podstawie treści paragonu."""
        lower_text = raw_text.lower()
        for keyword, parser in self._parsers.items():
            if keyword != "default" and keyword in lower_text:
                logger.info(f"Keyword '{keyword}' found. Selecting {parser.__class__.__name__}.")
                return parser
        logger.info("No specific keyword found. Using default parser.")
        return self._default_parser

    def parse(self, raw_text: str) -> list[ParsedProduct]: # Changed return type
        """Używa wybranego parsera do przetworzenia tekstu."""
        selected_parser = self.select_parser(raw_text)
        return selected_parser.parse(raw_text)

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
