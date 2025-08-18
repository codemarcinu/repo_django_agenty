import logging

from celery import shared_task
from django.db import transaction

from .models import Document
from .rag_processor import rag_processor
from .services.receipt_service import get_receipt_service

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
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    retry_backoff=True,
    retry_backoff_max=600,
    task_time_limit=1200,
)
def orchestrate_receipt_processing(self, receipt_id: int):
    """
    Orchestrates the full, multi-step receipt processing pipeline.
    1. OCR -> 2. Parsing -> 3. Matching
    """
    logger.info(f"▶️ STARTING NEW PROCESSING ORCHESTRATION for Receipt ID: {receipt_id}")
    receipt_service = get_receipt_service()

    try:
        with transaction.atomic():
            # Step 1: OCR Processing
            logger.info(f"  [1/3] OCR | Receipt ID: {receipt_id}")
            ocr_success = receipt_service.process_receipt_ocr(receipt_id)
            if not ocr_success:
                logger.error(f"  [1/3] OCR FAILED | Receipt ID: {receipt_id}")
                # The service method handles setting the error state
                return

            # Step 2: Parsing (LLM Extraction)
            logger.info(f"  [2/3] PARSING | Receipt ID: {receipt_id}")
            parsing_success = receipt_service.process_receipt_parsing(receipt_id)
            if not parsing_success:
                logger.error(f"  [2/3] PARSING FAILED | Receipt ID: {receipt_id}")
                return

            # Step 3: Product Matching
            logger.info(f"  [3/3] MATCHING | Receipt ID: {receipt_id}")
            matching_success = receipt_service.process_receipt_matching(receipt_id)
            if not matching_success:
                logger.error(f"  [3/3] MATCHING FAILED | Receipt ID: {receipt_id}")
                return

        logger.info(f"✅ PROCESSING ORCHESTRATION COMPLETED for Receipt ID: {receipt_id}. Ready for review.")

    except Exception as e:
        logger.error(
            f"❌ CRITICAL ORCHESTRATION ERROR for Receipt ID: {receipt_id}: {e}",
            exc_info=True,
        )
        # The service methods should handle their own error states,
        # but we can add a final catch-all here.
        from inventory.models import Receipt
        Receipt.objects.filter(id=receipt_id).update(
            status="error",
            processing_notes=f"Orchestration failed: {e}"
        )
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
