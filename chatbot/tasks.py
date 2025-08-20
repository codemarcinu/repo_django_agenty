import logging

from celery import shared_task
from django.db import transaction
from django.conf import settings
from asgiref.sync import sync_to_async # Import sync_to_async

from inventory.models import Receipt # Import Receipt model
from .models import Document
from .rag_processor import rag_processor
from .services.exceptions_receipt import (
    DatabaseError,
    MatchingError,
    OCRError,
    ParsingError,
)
from .services.receipt_service import get_receipt_service
from .services.quality_gate_service import QualityGateService # Import QualityGateService
from .services.vision_service import VisionService # Import VisionService
from .services.ocr_service import ocr_service # Import ocr_service
from .services.receipt_parser import receipt_parser # Import receipt_parser

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
        # Optionally update document status to error
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
        
        # Update receipt with raw OCR data
        receipt.raw_ocr_text = ocr_result.text # Use .text as per ocr_service.py
        receipt.raw_text = ocr_result.metadata # Store metadata if available
        receipt.save()
        
        # --- KROK 2: BRAMKA JAKOŚCI ---
        logger.info(f"  [2/4] QUALITY GATE | Receipt ID: {receipt_id}")
        receipt.mark_as_processing(step="quality_gate")
        
        # Create a compatible OCRResult for QualityGateService
        from chatbot.schemas import OCRResult as SchemaOCRResult # Alias to avoid conflict
        
        # Assuming ocr_result.text contains the full text and ocr_result.metadata might contain line-level data
        # If ocr_result.metadata doesn't contain lines/confidences, these will be empty lists.
        quality_ocr_result = SchemaOCRResult(
            full_text=ocr_result.text,
            lines=ocr_result.metadata.get('lines', []) if ocr_result.metadata else [],
            confidences=ocr_result.metadata.get('confidences', []) if ocr_result.metadata else []
        )
        
        quality_gate = QualityGateService(quality_ocr_result)
        quality_score = quality_gate.calculate_quality_score()
        logger.info(f"Paragon {receipt_id}: Wynik jakości OCR to {quality_score}%")

        # --- KROK 3: GŁÓWNY PRZEŁĄCZNIK ---
        parsed_data = None
        if quality_score >= settings.OCR_QUALITY_THRESHOLD:
            logger.info(f"Paragon {receipt_id}: Jakość wysoka. Uruchamiam standardowy parser LLM.")
            receipt.mark_as_processing(step="parsing_in_progress")
            raw_text = ocr_result.text
            parsed_data = receipt_parser.parse(raw_text)
        else:
            logger.warning(f"Paragon {receipt_id}: Jakość niska. Przełączam na VisionService.")
            receipt.mark_as_processing(step="vision_parsing")
            vision_service_instance = VisionService()
            # Call async method using sync_to_async
            parsed_data = sync_to_async(vision_service_instance.extract_data_from_image)(receipt.receipt_file.path)
            # Await the result of sync_to_async
            parsed_data = parsed_data.result() # This will block until the async operation is done.
            
        # Update receipt with parsed data
        if parsed_data:
            receipt.extracted_data = parsed_data.to_dict()
            receipt.mark_llm_done(receipt.extracted_data)
        else:
            receipt.mark_as_error("Parsing failed: No data extracted from OCR or Vision.")
            raise ParsingError(f"No data extracted for receipt {receipt_id}")

        # --- KROK 4: Product Matching (using existing receipt_service method) ---
        logger.info(f"  [4/4] MATCHING | Receipt ID: {receipt_id}")
        # The existing process_receipt_matching expects the data to be in receipt.extracted_data
        # which is now handled by the above logic.
        receipt_service = get_receipt_service() # Get the service instance
        receipt_service.process_receipt_matching(receipt_id)

        logger.info(f"✅ ORCHESTRATION COMPLETED for Receipt ID: {receipt_id}.")

    except (OCRError, ParsingError, MatchingError, DatabaseError) as e:
        logger.warning(f"Retrying task for Receipt ID {receipt_id} due to {type(e).__name__}: {e.message}")
        raise self.retry(exc=e)
    except Exception as e:
        logger.error(
            f"❌ CRITICAL ORCHESTRATION ERROR for Receipt ID: {receipt_id}: {e}",
            exc_info=True,
        )
        # The service methods already mark the receipt as failed.
        # This is a final catch-all.
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
    This task is called AFTER the user has reviewed and approved the items.
    """
    logger.info(f"▶️ FINALIZING INVENTORY for Receipt ID: {receipt_id}")
    # TODO: Implement the logic to call inventory_service.process_receipt_for_inventory
    # For now, this is a placeholder.
    logger.warning(f"Placeholder task: Finalization for receipt {receipt_id} not yet implemented.")
    return True