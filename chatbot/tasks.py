import asyncio  # Potrzebne do wywołania asynchronicznego VisionService
import logging

from celery import shared_task
from django.conf import settings

from inventory.models import Receipt

from .models import Document
from .rag_processor import rag_processor
from .services.exceptions_receipt import (
    DatabaseError,
    MatchingError,
    OCRError,
    ParsingError,
)

logger = logging.getLogger(__name__)


@shared_task
def process_document_task(document_id):
    try:
        rag_processor.process_document(document_id)
        logger.info(f"Document {document_id} processed successfully by Celery task.")
    except Exception as e:
        logger.error(
            f"Error processing document {document_id} by Celery task: {e}",
            exc_info=True,
        )
        Document.objects.filter(id=document_id).update(status="error")


@shared_task(
    bind=True,
    autoretry_for=(OCRError, ParsingError, MatchingError, DatabaseError),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    retry_backoff=True,
    retry_backoff_max=600,
    task_time_limit=1200,
)
def orchestrate_receipt_processing(self, receipt_id: int):
    """
    Orchestrates the full, multi-step receipt processing pipeline.
    1. OCR -> 2. Quality Gate -> 3. Parsing (LLM or Vision) -> 4. Matching
    """
    # Importy wewnątrz funkcji, aby rozwiązać problem kolistego importu
    from .services.ocr_backends import OCRResult
    from .services.ocr_service import ocr_service
    from .services.quality_gate_service import QualityGateService
    from .services.receipt_parser import (
        get_receipt_parser,  # ZMIANA: Import funkcji zamiast instancji
    )
    from .services.receipt_service import get_receipt_service
    from .services.vision_service import VisionService

    logger.info(f"▶️ STARTING ORCHESTRATION for Receipt ID: {receipt_id} (Attempt: {self.request.retries + 1})")

    try:
        receipt = Receipt.objects.get(id=receipt_id)

        # --- KROK 1: OCR ---
        logger.info(f"  [1/4] OCR | Receipt ID: {receipt_id}")
        receipt.mark_as_processing(step="ocr_in_progress")
        ocr_result = ocr_service.process_file(receipt.receipt_file.path)

        if not ocr_result.success:
            receipt.mark_as_error(f"OCR failed: {ocr_result.error_message}")
            raise OCRError(f"OCR failed for receipt {receipt_id}")

        receipt.raw_ocr_text = ocr_result.text
        receipt.raw_text = ocr_result.to_dict() # Zapisz pełny wynik jako JSON
        receipt.save()

        # --- KROK 2: BRAMKA JAKOŚCI ---
        logger.info(f"  [2/4] QUALITY GATE | Receipt ID: {receipt_id}")
        receipt.mark_as_processing(step="quality_gate")

        # WAŻNE: Upewnij się, że ocr_result to instancja OCRResult
        # (OCRResult is imported from .services.ocr_service or .services.ocr_backends)
        if not isinstance(ocr_result, OCRResult):
            raise TypeError(
                f"OCRService.process_document() must return OCRResult instance, "
                f"got {type(ocr_result).__name__}"
            )

        # Krok 2: Quality Gate
        logger.info(f"  [2/4] QUALITY GATE | Receipt ID: {receipt_id}")
        receipt.mark_as_processing(step="quality_gate")

        quality_gate = QualityGateService(ocr_result)
        quality_score = quality_gate.calculate_quality_score()
        logger.info(f"Paragon {receipt_id}: Wynik jakości OCR to {quality_score}")

        # --- KROK 3: GŁÓWNY PRZEŁĄCZNIK ---
        parsed_data = None
        receipt_parser = get_receipt_parser() # ZMIANA: Pobranie instancji przez funkcję

        if quality_score >= settings.OCR_QUALITY_THRESHOLD:
            logger.info(f"Paragon {receipt_id}: Jakość wysoka. Uruchamiam standardowy parser.")
            receipt.mark_as_processing(step="parsing_in_progress")
            raw_text = ocr_result.text
            parsed_data = receipt_parser.parse(raw_text)
        else:
            logger.warning(f"Paragon {receipt_id}: Jakość niska. Przełączam na VisionService.")
            receipt.mark_as_processing(step="vision_parsing")
            vision_service_instance = VisionService()
            parsed_data = asyncio.run(vision_service_instance.extract_data_from_image(receipt.receipt_file.path))

        if parsed_data:
            # Upewnij się, że parsed_data jest słownikiem, a nie obiektem Pydantic
            extracted_dict = parsed_data if isinstance(parsed_data, dict) else parsed_data.dict()
            receipt.extracted_data = extracted_dict
            receipt.mark_llm_done(extracted_dict)
        else:
            receipt.mark_as_error("Parsing failed: No data extracted from OCR or Vision.")
            raise ParsingError(f"No data extracted for receipt {receipt_id}")

        # --- KROK 4: Product Matching ---
        logger.info(f"  [4/4] MATCHING | Receipt ID: {receipt_id}")
        receipt_service = get_receipt_service()
        receipt_service.process_receipt_matching(receipt_id)

        logger.info(f"✅ ORCHESTRATION COMPLETED for Receipt ID: {receipt_id}.")

    except (OCRError, ParsingError, MatchingError, DatabaseError) as e:
        logger.warning(f"Retrying task for Receipt ID {receipt_id} due to {type(e).__name__}: {str(e)}")
        raise self.retry(exc=e)
    except Exception as e:
        logger.error(
            f"❌ CRITICAL ORCHESTRATION ERROR for Receipt ID: {receipt_id}: {e}",
            exc_info=True,
        )
        try:
            receipt_to_update = Receipt.objects.get(id=receipt_id)
            receipt_to_update.mark_as_error(f"Critical error: {e}")
        except Receipt.DoesNotExist:
            logger.error(f"Could not find receipt {receipt_id} to mark as error after critical failure.")
        raise

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    task_time_limit=600,
)
def finalize_receipt_inventory(self, receipt_id: int):
    """
    Finalizes a receipt by processing its line items into the inventory.
    """
    logger.info(f"▶️ FINALIZING INVENTORY for Receipt ID: {receipt_id}")
    from .services.inventory_service import get_inventory_service
    inventory_service = get_inventory_service()
    success, message = inventory_service.process_receipt_for_inventory(receipt_id)
    if not success:
        logger.error(f"Inventory finalization failed for receipt {receipt_id}: {message}")
    return success
