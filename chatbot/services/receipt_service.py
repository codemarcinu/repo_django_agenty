"""
Receipt processing service implementing business logic for receipt operations.
Part of the fat model, thin view pattern implementation.
"""

import hashlib
import logging

# Get the dedicated diagnostic logger
diag_logger = logging.getLogger("receipt_pipeline_diag")

from django.db import transaction

from inventory.models import Receipt

from .exceptions_receipt import (
    MatchingError,
    OCRError,
    ParsingError,
    ReceiptNotFoundError,
)
from .image_processor import get_image_processor
from .ocr_service import get_ocr_service
from .pantry_service_v2 import PantryServiceV2
from .receipt_cache import get_cache_manager
from .registry import get_receipt_parser
from .websocket_notifier import get_websocket_notifier

logger = logging.getLogger(__name__)


# Global service instance
_receipt_service_instance = None


def get_receipt_service() -> "ReceiptService":
    """Get global ReceiptService instance."""
    global _receipt_service_instance
    if _receipt_service_instance is None:
        _receipt_service_instance = ReceiptService()
    return _receipt_service_instance


class ReceiptService:
    """Service class for receipt processing operations"""

    def __init__(self):
        self.pantry_service = PantryServiceV2()
        self.notifier = get_websocket_notifier()

    def process_and_queue_receipt(self, receipt_file, user):
        """
        Tworzy rekord paragonu w bazie danych, zapisuje plik i kolejkuje zadanie Celery.
        """
        receipt = None  # Inicjalizujemy zmienną, aby była dostępna w bloku except
        try:
            # Krok 1: Stwórz obiekt Receipt w bazie danych
            receipt = Receipt.objects.create(
                user=user,
                status='pending',
                processing_step='queued'
            )

            # Krok 2: Zapisz plik. Django automatycznie przypisze go do obiektu.
            receipt.receipt_file.save(receipt_file.name, receipt_file, save=True)

            logger.info(f"✅ New Receipt record created successfully with ID: {receipt.id}")

            # Krok 3: Wywołaj zadanie asynchroniczne Celery
            from ..tasks import orchestrate_receipt_processing
            orchestrate_receipt_processing.delay(receipt.id)
            logger.info(f"✅ Queued orchestration task for receipt {receipt.id}")

            return receipt

        except Exception as e:
            # Ten blok jest OBOWIĄZKOWY i musi następować zaraz po bloku `try`
            logger.error(f"❌ Failed to create or queue receipt: {e}", exc_info=True)

            # Jeśli paragon został już utworzony, oznacz go jako błędny
            if receipt and receipt.pk:
                receipt.mark_as_error(f"Failed during initial creation/queuing: {e}")

            return None

    def start_processing(self, receipt_id: int):
        """
        Start receipt processing by triggering Celery task.
        """
        diag_logger.debug(f"Attempting to start processing for receipt ID: {receipt_id}")
        logger.info(f"🔄 Attempting to queue processing for receipt ID: {receipt_id}")
        try:
            receipt = Receipt.objects.get(id=receipt_id)
            diag_logger.info(f"Found receipt {receipt_id}. Current status: {receipt.status}, step: {receipt.processing_step}")
            receipt.status = "processing"
            receipt.processing_step = "ocr_in_progress"
            receipt.error_message = ""
            receipt.save()
            diag_logger.debug(f"Receipt {receipt_id} status updated to 'processing', step to 'ocr_in_progress'.")

            self.notifier.send_status_update(
                receipt_id, "processing", "Rozpoczynam przetwarzanie...", 15
            )
            diag_logger.debug(f"Sent status update for receipt {receipt_id}: 'Rozpoczynam przetwarzanie...'")

            from ..tasks import orchestrate_receipt_processing
            task_result = orchestrate_receipt_processing.delay(receipt_id)
            logger.info(f"✅ Celery task queued for receipt {receipt_id}, task ID: {task_result.id}")
            diag_logger.info(f"Celery task 'orchestrate_receipt_processing' queued for receipt {receipt_id}. Task ID: {task_result.id}")
        except Receipt.DoesNotExist as e:
            diag_logger.error(f"Receipt {receipt_id} not found during start_processing: {e}", exc_info=True)
            raise ReceiptNotFoundError(f"Receipt {receipt_id} not found") from e
        except Exception as e:
            logger.error(f"❌ Failed to queue orchestration task for receipt {receipt.id}: {e}", exc_info=True)
            if 'receipt' in locals() and receipt.pk:
                receipt.mark_as_error(f"Failed to queue task: {e}")
            # Możesz tutaj rzucić wyjątek dalej lub zwrócić None, w zależności od logiki
            return None

    def process_receipt_ocr(self, receipt_id: int, use_fallback: bool = True):
        """
        Process receipt with OCR, raising exceptions on failure.
        """
        diag_logger.debug(f"Starting OCR processing for receipt ID: {receipt_id}")
        cache_manager = get_cache_manager()
        receipt = Receipt.objects.get(id=receipt_id)

        self.notifier.send_status_update(receipt_id, "processing", "Przygotowanie obrazu...", 20)
        diag_logger.debug(f"Sent status update for receipt {receipt_id}: 'Przygotowanie obrazu...'")

        try:
            if not receipt.receipt_file:
                diag_logger.error(f"No receipt file found for receipt {receipt_id}.")
                raise OCRError("No file uploaded for receipt", receipt_id=receipt_id)

            image_path = receipt.receipt_file.path
            diag_logger.debug(f"Receipt {receipt_id} file path: {image_path}")

            # --- Image Preprocessing ---
            diag_logger.debug(f"Starting image preprocessing for receipt {receipt_id}.")
            image_processor = get_image_processor()
            processing_result = image_processor.preprocess_image(image_path)
            if processing_result.success:
                image_path = processing_result.processed_path
                logger.info(f"Image for receipt {receipt_id} preprocessed successfully.")
                diag_logger.info(f"Image for receipt {receipt_id} preprocessed successfully. Processed path: {image_path}")
                self.notifier.send_status_update(receipt_id, "processing", "Obraz przetworzony.", 25)
                diag_logger.debug(f"Sent status update for receipt {receipt_id}: 'Obraz przetworzony.'")
            else:
                logger.warning(f"Image preprocessing failed for receipt {receipt_id}: {processing_result.message}")
                diag_logger.warning(f"Image preprocessing failed for receipt {receipt_id}: {processing_result.message}")
            # --- End Image Preprocessing ---

            # --- Caching Logic ---
            diag_logger.debug(f"Checking OCR cache for receipt {receipt_id}.")
            try:
                with open(image_path, 'rb') as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                cached_ocr = cache_manager.get_cached_ocr_result(file_hash)
                if cached_ocr:
                    logger.info(f"CACHE HIT: Found cached OCR for receipt {receipt_id}")
                    diag_logger.info(f"CACHE HIT: Found cached OCR for receipt {receipt_id}. Using cached result.")
                    receipt.raw_text = cached_ocr
                    receipt.processing_step = "ocr_completed"
                    receipt.save()
                    self.notifier.send_status_update(receipt_id, "processing", "OCR zakończone (cache)", 50)
                    diag_logger.debug(f"Sent status update for receipt {receipt_id}: 'OCR zakończone (cache)'.")
                    return
                diag_logger.debug(f"CACHE MISS: No cached OCR found for receipt {receipt_id}.")
            except Exception as e:
                logger.warning(f"OCR cache check failed for receipt {receipt_id}: {e}")
                diag_logger.warning(f"OCR cache check failed for receipt {receipt_id}: {e}", exc_info=True)
            # --- End Caching ---

            self.notifier.send_status_update(receipt_id, "processing", "Przetwarzanie OCR...", 30)
            diag_logger.debug(f"Sent status update for receipt {receipt_id}: 'Przetwarzanie OCR...'.")
            receipt.processing_step = "ocr_in_progress"
            receipt.save()
            diag_logger.debug(f"Receipt {receipt_id} status updated to 'ocr_in_progress'.")

            ocr_service = get_ocr_service()
            if not ocr_service.is_available():
                diag_logger.error(f"No OCR backends available for receipt {receipt_id}.")
                raise OCRError("No OCR backends available", receipt_id=receipt_id)
            diag_logger.debug(f"OCR service is available for receipt {receipt_id}. Processing file with OCR.")

            # Set processing context for status updates
            if hasattr(ocr_service, 'set_processing_context'):
                ocr_service.set_processing_context(receipt_id, self.notifier)
                diag_logger.debug(f"Set processing context for OCR service (receipt {receipt_id})")

            ocr_result = ocr_service.process_file(image_path, use_fallback)
            diag_logger.debug(f"OCR service returned result for receipt {receipt_id}. Success: {ocr_result.success}")

            if ocr_result.success and ocr_result.text.strip():
                receipt.raw_text = ocr_result.to_dict()
                receipt.processing_step = "ocr_completed"
                receipt.save()
                self.notifier.send_status_update(receipt_id, "processing", "OCR zakończone", 50)
                diag_logger.info(f"OCR completed successfully for receipt {receipt_id}. Extracted text length: {len(ocr_result.text.strip())}")
                diag_logger.debug(f"Sent status update for receipt {receipt_id}: 'OCR zakończone'.")
                # --- Cache successful result ---
                diag_logger.debug(f"Caching successful OCR result for receipt {receipt_id}.")
                with open(image_path, 'rb') as f:
                    file_hash_for_cache = hashlib.sha256(f.read()).hexdigest()
                cache_manager.cache_ocr_result(file_hash_for_cache, ocr_result.to_dict())
                diag_logger.debug(f"OCR result cached for receipt {receipt_id}.")
            else:
                error_msg = ocr_result.error_message or "OCR failed to extract text"
                diag_logger.error(f"OCR failed for receipt {receipt_id}: {error_msg}")
                raise OCRError(error_msg, receipt_id=receipt_id)

        except (Receipt.DoesNotExist, OCRError, Exception) as e:
            error_message = getattr(e, 'message', str(e))
            receipt.mark_as_error(f"OCR Error: {error_message}")
            self.notifier.send_error(receipt_id, f"Błąd OCR: {error_message}")
            diag_logger.critical(f"CRITICAL ERROR during OCR processing for receipt {receipt_id}: {error_message}", exc_info=True)
            if isinstance(e, Receipt.DoesNotExist):
                 raise ReceiptNotFoundError(f"Receipt {receipt_id} not found for OCR") from e
            elif isinstance(e, OCRError):
                raise
            else:
                raise OCRError(f"OCR critical error: {e}") from e

    def process_receipt_parsing(self, receipt_id: int):
        """
        Process receipt parsing, raising exceptions on failure.
        """
        diag_logger.debug(f"Starting parsing processing for receipt ID: {receipt_id}")
        cache_manager = get_cache_manager()
        receipt = Receipt.objects.get(id=receipt_id)
        self.notifier.send_status_update(receipt_id, "processing", "Parsowanie danych...", 65)
        diag_logger.debug(f"Sent status update for receipt {receipt_id}: 'Parsowanie danych...'.")

        try:
            # --- Caching Logic ---
            diag_logger.debug(f"Checking parsing cache for receipt {receipt_id}.")
            cached_parsing = cache_manager.get_cached_parsed_receipt(receipt_id)
            if cached_parsing:
                logger.info(f"CACHE HIT: Found cached parsed data for receipt {receipt_id}")
                diag_logger.info(f"CACHE HIT: Found cached parsed data for receipt {receipt_id}. Using cached result.")
                receipt.parsed_data = cached_parsing
                receipt.processing_step = "parsing_completed"
                receipt.save()
                self.notifier.send_status_update(receipt_id, "processing", "Parsowanie zakończone (cache)", 80)
                diag_logger.debug(f"Sent status update for receipt {receipt_id}: 'Parsowanie zakończone (cache)'.")
                return
            diag_logger.debug(f"CACHE MISS: No cached parsed data found for receipt {receipt_id}.")
            # --- End Caching ---

            if receipt.processing_step != "ocr_completed":
                diag_logger.error(f"Receipt {receipt_id} not ready for parsing. Current step: {receipt.processing_step}")
                raise ParsingError(f"Receipt {receipt_id} not ready for parsing", details={'current_step': receipt.processing_step})

            ocr_text = receipt.raw_text.get("text", "")
            if not ocr_text.strip():
                diag_logger.error(f"Empty OCR text for receipt {receipt_id}. Cannot parse.")
                raise ParsingError("Empty OCR text", receipt_id=receipt_id)
            diag_logger.debug(f"OCR text available for receipt {receipt_id}. Length: {len(ocr_text.strip())}")

            receipt.processing_step = "parsing_in_progress"
            receipt.save()
            diag_logger.debug(f"Receipt {receipt_id} status updated to 'parsing_in_progress'.")

            parser = get_receipt_parser()
            diag_logger.debug(f"Calling receipt parser for receipt {receipt_id}.")
            parsed_receipt = parser.parse(ocr_text)

            if not parsed_receipt or not parsed_receipt.products:
                diag_logger.warning(f"Parser returned no products for receipt {receipt_id}.")
                raise ParsingError("Parser returned no products", receipt_id=receipt_id)
            diag_logger.info(f"Parser successfully extracted {len(parsed_receipt.products)} products for receipt {receipt_id}.")
            diag_logger.debug(f"Parsed data for receipt {receipt_id}: {parsed_receipt.to_dict()}")

            parsed_data_dict = parsed_receipt.to_dict()
            receipt.parsed_data = parsed_data_dict
            receipt.processing_step = "parsing_completed"
            receipt.save()
            self.notifier.send_status_update(receipt_id, "processing", "Parsowanie zakończone", 80)
            diag_logger.debug(f"Sent status update for receipt {receipt_id}: 'Parsowanie zakończone'.")

            # --- Cache successful result ---
            diag_logger.debug(f"Caching successful parsed result for receipt {receipt_id}.")
            cache_manager.cache_parsed_receipt(receipt_id, parsed_data_dict)
            diag_logger.debug(f"Parsed result cached for receipt {receipt_id}.")

        except (Receipt.DoesNotExist, ParsingError, Exception) as e:
            error_message = getattr(e, 'message', str(e))
            receipt.mark_as_error(f"Parsing Error: {error_message}")
            self.notifier.send_error(receipt_id, f"Błąd parsowania: {error_message}")
            diag_logger.critical(f"CRITICAL ERROR during parsing processing for receipt {receipt_id}: {error_message}", exc_info=True)
            if isinstance(e, Receipt.DoesNotExist):
                 raise ReceiptNotFoundError(f"Receipt {receipt_id} not found for parsing") from e
            elif isinstance(e, ParsingError):
                raise
            else:
                raise ParsingError(f"Parsing critical error: {e}") from e

    def process_receipt_matching(self, receipt_id: int):
        """
        Process product matching, raising exceptions on failure.
        """
        diag_logger.debug(f"Starting product matching for receipt ID: {receipt_id}")
        receipt = Receipt.objects.get(id=receipt_id)
        self.notifier.send_status_update(receipt_id, "processing", "Dopasowywanie produktów...", 90)
        diag_logger.debug(f"Sent status update for receipt {receipt_id}: 'Dopasowywanie produktów...'.")

        try:
            if receipt.processing_step != "parsing_completed":
                diag_logger.error(f"Receipt {receipt_id} not ready for matching. Current step: {receipt.processing_step}")
                raise MatchingError(f"Receipt {receipt_id} not ready for matching", details={'current_step': receipt.processing_step})

            # 🔍 DEBUG - sprawdź gdzie są produkty
            diag_logger.info(f"🔍 MATCHING DEBUG for Receipt {receipt_id}:")
            diag_logger.info(f"extracted_data keys: {list(receipt.extracted_data.keys()) if receipt.extracted_data else 'None'}")
            diag_logger.info(f"parsed_data keys: {list(receipt.parsed_data.keys()) if receipt.parsed_data else 'None'}")

            # Spróbuj najpierw z parsed_data (standard)
            products_data = receipt.parsed_data.get("products", []) if receipt.parsed_data else []

            # Jeśli nie ma w parsed_data, sprawdź extracted_data
            if not products_data and receipt.extracted_data:
                products_data = receipt.extracted_data.get("products", [])
                diag_logger.info(f"🔄 Using products from extracted_data: {len(products_data)} products")

            # Jeśli nadal nie ma, sprawdź czy to bezpośrednia lista
            if not products_data and receipt.parsed_data and isinstance(receipt.parsed_data, list):
                products_data = receipt.parsed_data
                diag_logger.info(f"🔄 Using parsed_data as direct list: {len(products_data)} products")

            if not products_data:
                logger.info(f"Matching skipped for receipt {receipt_id}: no products.")
                diag_logger.info(f"Matching skipped for receipt {receipt_id}: no products found.")
                receipt.mark_as_ready_for_review()
                self.notifier.send_status_update(receipt_id, "review_pending", "Gotowy do weryfikacji (brak produktów)", 98)
                diag_logger.debug(f"Receipt {receipt_id} marked as ready for review (no products).")
                return

            receipt.processing_step = "matching_in_progress"
            receipt.save()
            diag_logger.debug(f"Receipt {receipt_id} status updated to 'matching_in_progress'. Number of products to match: {len(products_data)}")

            from decimal import Decimal

            from .product_matcher import get_product_matcher
            from .receipt_parser import ParsedProduct

            parsed_products = [ParsedProduct(name=p.get("product", ""), quantity=p.get("quantity"), price=Decimal(p.get("price", 0)), total_price=Decimal(p.get("price", 0)) * Decimal(p.get("quantity", 1))) for p in products_data]

            matcher = get_product_matcher()
            diag_logger.debug(f"Calling product matcher for receipt {receipt_id}.")
            match_results = matcher.batch_match_products(parsed_products)

            if not match_results:
                diag_logger.warning(f"Product matcher returned no results for receipt {receipt_id}.")
                raise MatchingError("Product matcher returned no results", receipt_id=receipt_id)
            diag_logger.info(f"Product matcher returned {len(match_results)} results for receipt {receipt_id}.")

            from inventory.models import ReceiptLineItem
            with transaction.atomic():
                for parsed_product, match_result in zip(parsed_products, match_results, strict=False):
                    ReceiptLineItem.objects.create(
                        receipt=receipt,
                        product_name=parsed_product.name,
                        quantity=Decimal(str(parsed_product.quantity or 1.0)),
                        unit_price=parsed_product.price or Decimal("0.00"),
                        line_total=parsed_product.total_price or Decimal("0.00"),
                        matched_product=match_result.product,
                        meta={'match_confidence': match_result.confidence, 'match_type': match_result.match_type}
                    )
                    diag_logger.debug(f"Created ReceiptLineItem for '{parsed_product.name}'. Matched product: {match_result.product.name if match_result.product else 'None'}, Confidence: {match_result.confidence}")
                    if match_result.product and match_result.confidence >= 0.8:
                        matcher.update_product_aliases(match_result.product, parsed_product.name)
                        diag_logger.debug(f"Updated product aliases for '{match_result.product.name}' with '{parsed_product.name}'.")

            receipt.mark_as_ready_for_review()
            self.notifier.send_status_update(receipt_id, "review_pending", "Gotowy do weryfikacji", 98)
            diag_logger.info(f"Receipt {receipt_id} processing completed. Marked as ready for review.")
            diag_logger.debug(f"Sent status update for receipt {receipt_id}: 'Gotowy do weryfikacji'.")

        except (Receipt.DoesNotExist, MatchingError, Exception) as e:
            error_message = getattr(e, 'message', str(e))
            receipt.mark_as_error(f"Matching Error: {error_message}")
            self.notifier.send_error(receipt_id, f"Błąd dopasowania: {error_message}")
            diag_logger.critical(f"CRITICAL ERROR during matching processing for receipt {receipt_id}: {error_message}", exc_info=True)
            if isinstance(e, Receipt.DoesNotExist):
                 raise ReceiptNotFoundError(f"Receipt {receipt_id} not found for matching") from e
            elif isinstance(e, MatchingError):
                raise
            else:
                raise MatchingError(f"Matching critical error: {e}") from e
