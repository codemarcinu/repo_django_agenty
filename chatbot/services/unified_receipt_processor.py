# W pliku repo_django_agenty/chatbot/services/unified_receipt_processor.py

import logging

from ..schemas import ExtractedReceipt, OCRResult
from .ocr_service import ocr_service
from .receipt_parser import get_receipt_parser  # ZMIANA: Import funkcji

logger = logging.getLogger(__name__)

class UnifiedReceiptProcessor:
    """
    Ujednolicony procesor, który hermetyzuje cały proces od OCR do parsowania.
    """
    def __init__(self):
        self.ocr_service = ocr_service
        self.receipt_parser = get_receipt_parser() # ZMIANA: Pobranie instancji przez funkcję

    def process_receipt(self, file_path: str) -> ExtractedReceipt:
        """
        Przetwarza plik paragonu, wykonując OCR, a następnie parsowanie.

        :param file_path: Ścieżka do pliku z obrazem/PDF paragonu.
        :return: Obiekt ExtractedReceipt z wyodrębnionymi danymi.
        """
        logger.info(f"Starting unified processing for file: {file_path}")

        # Krok 1: Wykonaj OCR
        ocr_result: OCRResult = self.ocr_service.process_file(file_path)
        if not ocr_result.success:
            logger.error(f"OCR failed for {file_path}: {ocr_result.error_message}")
            # W zależności od wymagań, można tu rzucić wyjątek lub zwrócić pusty obiekt
            raise ValueError(f"OCR processing failed: {ocr_result.error_message}")

        raw_text = ocr_result.text
        if not raw_text or raw_text.isspace():
            logger.warning(f"OCR returned empty or whitespace-only text for {file_path}")
            raise ValueError("OCR did not return any text to parse.")

        logger.debug(f"OCR successful for {file_path}. Raw text length: {len(raw_text)}")

        # Krok 2: Sparsuj tekst za pomocą AdaptiveReceiptParser
        try:
            parsed_data_dict = self.receipt_parser.parse(raw_text)
            # Konwertuj słownik na model Pydantic dla spójności typów
            extracted_receipt = ExtractedReceipt(**parsed_data_dict)
            logger.info(f"Successfully parsed receipt data for {file_path}")
            return extracted_receipt
        except Exception as e:
            logger.error(f"Parsing failed for {file_path} after successful OCR. Error: {e}", exc_info=True)
            raise

# Opcjonalnie: Utworzenie instancji singleton, jeśli jest potrzebna w innych miejscach
# w ten sam sposób, aby uniknąć wielokrotnego tworzenia.
unified_processor = UnifiedReceiptProcessor()
