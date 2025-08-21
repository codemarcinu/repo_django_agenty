# chatbot/services/registry.py

from .receipt_parser import AdaptiveReceiptParser, LidlReceiptParser, RegexReceiptParser

# Tutaj tworzymy jedną, centralną instancję parsera
receipt_parser = AdaptiveReceiptParser()

# Tutaj rejestrujemy konkretne parsery dla sklepów
receipt_parser.register_parser("lidl", LidlReceiptParser())
# Używamy domyślnego parsera dla Biedronki, dopóki nie powstanie dedykowany
receipt_parser.register_parser("biedronka", RegexReceiptParser())
# Możemy też zarejestrować parser domyślny
receipt_parser.register_parser("default", RegexReceiptParser())


def get_receipt_parser():
    """
    Zwraca skonfigurowaną instancję parsera paragonów.
    """
    return receipt_parser
