import logging

from celery import shared_task

from .models import Document, ReceiptProcessing
from .rag_processor import rag_processor
from .receipt_processor import receipt_processor

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


@shared_task
def process_receipt_task(receipt_id):
    try:
        import asyncio

        asyncio.run(receipt_processor.process_receipt(receipt_id))
        logger.info(f"Receipt {receipt_id} processed successfully by Celery task.")
    except Exception as e:
        logger.error(
            f"Error processing receipt {receipt_id} by Celery task: {e}", exc_info=True
        )
        # Optionally update receipt status to error
        ReceiptProcessing.objects.filter(id=receipt_id).update(
            status="error", error_message=str(e)
        )
