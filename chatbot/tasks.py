import logging

from celery import shared_task
from django.db import transaction

from .models import Document
from .rag_processor import rag_processor
from .services.exceptions_receipt import (
    DatabaseError,
    MatchingError,
    OCRError,
    ParsingError,
)
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
    autoretry_for=(OCRError, ParsingError, MatchingError, DatabaseError),
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
    logger.info(f"▶️ STARTING ORCHESTRATION for Receipt ID: {receipt_id} (Attempt: {self.request.retries + 1})")
    receipt_service = get_receipt_service()

    try:
        # The service methods now raise exceptions on failure, which Celery will catch
        # and use for retrying based on the `autoretry_for` configuration.
        
        # Step 1: OCR Processing
        logger.info(f"  [1/3] OCR | Receipt ID: {receipt_id}")
        receipt_service.process_receipt_ocr(receipt_id)

        # Step 2: Parsing
        logger.info(f"  [2/3] PARSING | Receipt ID: {receipt_id}")
        receipt_service.process_receipt_parsing(receipt_id)

        # Step 3: Product Matching
        logger.info(f"  [3/3] MATCHING | Receipt ID: {receipt_id}")
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
