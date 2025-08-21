"""
Repository pattern implementation for Receipt database operations.
"""

import logging
from typing import Any

from asgiref.sync import sync_to_async
from django.utils import timezone

from inventory.models import Receipt

from .exceptions_receipt import DatabaseError

logger = logging.getLogger(__name__)


class ReceiptRepository:
    """Repository for Receipt database operations with async support."""

    async def get_by_id(self, receipt_id: int) -> Receipt | None:
        """Get receipt record by ID."""
        try:
            return await sync_to_async(Receipt.objects.get)(id=receipt_id)
        except Receipt.DoesNotExist:
            logger.warning(f"Receipt record with ID {receipt_id} not found")
            return None
        except Exception as e:
            logger.error(f"Database error retrieving receipt {receipt_id}: {e}")
            raise DatabaseError(
                f"Failed to retrieve receipt: {str(e)}",
                model_name="Receipt",
                details={"receipt_id": receipt_id}
            )

    async def create(self, receipt_file, initial_status: str = "uploaded") -> Receipt:
        """Create new receipt record."""
        try:
            receipt = Receipt(
                receipt_file=receipt_file,
                status=initial_status,
                uploaded_at=timezone.now()
            )
            await sync_to_async(receipt.save)()
            logger.info(f"Created new receipt record with ID: {receipt.id}")
            return receipt
        except Exception as e:
            logger.error(f"Database error creating receipt: {e}")
            raise DatabaseError(
                f"Failed to create receipt: {str(e)}",
                model_name="Receipt"
            )

    async def update_status(self, receipt_id: int, status: str,
                          error_message: str | None = None) -> bool:
        """Update receipt status."""
        try:
            receipt = await self.get_by_id(receipt_id)
            if not receipt:
                return False

            receipt.status = status
            if error_message:
                receipt.error_message = error_message

            await sync_to_async(receipt.save)(update_fields=['status', 'error_message'])
            logger.info(f"Updated receipt {receipt_id} status to '{status}'")
            return True

        except Exception as e:
            logger.error(f"Database error updating receipt {receipt_id} status: {e}")
            raise DatabaseError(
                f"Failed to update receipt status: {str(e)}",
                model_name="Receipt",
                details={"receipt_id": receipt_id, "status": status}
            )

    async def update_ocr_result(self, receipt_id: int, raw_ocr_text: str) -> bool:
        """Update receipt with OCR results."""
        try:
            receipt = await self.get_by_id(receipt_id)
            if not receipt:
                return False

            receipt.raw_ocr_text = raw_ocr_text
            receipt.status = "ocr_done"

            await sync_to_async(receipt.save)(
                update_fields=['raw_ocr_text', 'status']
            )
            logger.info(f"Updated receipt {receipt_id} with OCR results")
            return True

        except Exception as e:
            logger.error(f"Database error updating receipt {receipt_id} OCR results: {e}")
            raise DatabaseError(
                f"Failed to update OCR results: {str(e)}",
                model_name="Receipt",
                details={"receipt_id": receipt_id}
            )

    async def update_extraction_result(self, receipt_id: int,
                                     extracted_data: list[dict[str, Any]]) -> bool:
        """Update receipt with LLM extraction results."""
        try:
            receipt = await self.get_by_id(receipt_id)
            if not receipt:
                return False

            receipt.extracted_data = extracted_data
            receipt.status = "ready_for_review"
            receipt.processed_at = timezone.now()

            await sync_to_async(receipt.save)(
                update_fields=['extracted_data', 'status', 'processed_at']
            )
            logger.info(f"Updated receipt {receipt_id} with extraction results")
            return True

        except Exception as e:
            logger.error(f"Database error updating receipt {receipt_id} extraction results: {e}")
            raise DatabaseError(
                f"Failed to update extraction results: {str(e)}",
                model_name="Receipt",
                details={"receipt_id": receipt_id}
            )

    async def mark_as_completed(self, receipt_id: int) -> bool:
        """Mark receipt as completed."""
        try:
            receipt = await self.get_by_id(receipt_id)
            if not receipt:
                return False

            receipt.status = "completed"
            receipt.completed_at = timezone.now()

            await sync_to_async(receipt.save)(
                update_fields=['status', 'completed_at']
            )
            logger.info(f"Marked receipt {receipt_id} as completed")
            return True

        except Exception as e:
            logger.error(f"Database error marking receipt {receipt_id} as completed: {e}")
            raise DatabaseError(
                f"Failed to mark receipt as completed: {str(e)}",
                model_name="Receipt",
                details={"receipt_id": receipt_id}
            )

    async def mark_as_error(self, receipt_id: int, error_message: str) -> bool:
        """Mark receipt as error with message."""
        try:
            receipt = await self.get_by_id(receipt_id)
            if not receipt:
                return False

            receipt.status = "error"
            receipt.error_message = error_message

            await sync_to_async(receipt.save)(
                update_fields=['status', 'error_message']
            )
            logger.info(f"Marked receipt {receipt_id} as error: {error_message}")
            return True

        except Exception as e:
            logger.error(f"Database error marking receipt {receipt_id} as error: {e}")
            raise DatabaseError(
                f"Failed to mark receipt as error: {str(e)}",
                model_name="Receipt",
                details={"receipt_id": receipt_id}
            )

    async def get_recent_receipts(self, limit: int = 10) -> list[Receipt]:
        """Get recently uploaded receipts."""
        try:
            receipts = await sync_to_async(list)(
                Receipt.objects.order_by('-uploaded_at')[:limit]
            )
            logger.debug(f"Retrieved {len(receipts)} recent receipts")
            return receipts

        except Exception as e:
            logger.error(f"Database error getting recent receipts: {e}")
            raise DatabaseError(
                f"Failed to get recent receipts: {str(e)}",
                model_name="Receipt"
            )

    async def get_processing_statistics(self) -> dict[str, Any]:
        """Get processing statistics."""
        try:
            async def get_counts():
                total = await sync_to_async(Receipt.objects.count)()
                pending = await sync_to_async(
                    Receipt.objects.filter(
                        status__in=['uploaded', 'ocr_in_progress', 'llm_in_progress']
                    ).count
                )()
                completed = await sync_to_async(
                    Receipt.objects.filter(status='completed').count
                )()
                errors = await sync_to_async(
                    Receipt.objects.filter(status='error').count
                )()
                ready_for_review = await sync_to_async(
                    Receipt.objects.filter(status='ready_for_review').count
                )()

                return {
                    "total": total,
                    "pending": pending,
                    "completed": completed,
                    "errors": errors,
                    "ready_for_review": ready_for_review,
                    "success_rate": (completed / total * 100) if total > 0 else 0
                }

            stats = await get_counts()
            logger.debug(f"Retrieved processing statistics: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Database error getting processing statistics: {e}")
            raise DatabaseError(
                f"Failed to get processing statistics: {str(e)}",
                model_name="Receipt"
            )

    async def delete_by_id(self, receipt_id: int) -> bool:
        """Delete receipt record by ID."""
        try:
            receipt = await self.get_by_id(receipt_id)
            if not receipt:
                return False

            await sync_to_async(receipt.delete)()
            logger.info(f"Deleted receipt record with ID: {receipt_id}")
            return True

        except Exception as e:
            logger.error(f"Database error deleting receipt {receipt_id}: {e}")
            raise DatabaseError(
                f"Failed to delete receipt: {str(e)}",
                model_name="Receipt",
                details={"receipt_id": receipt_id}
            )

    async def bulk_update_status(self, receipt_ids: list[int], status: str) -> int:
        """Bulk update status for multiple receipts."""
        try:
            @sync_to_async
            def update_bulk():
                return Receipt.objects.filter(
                    id__in=receipt_ids
                ).update(status=status)

            updated_count = await update_bulk()
            logger.info(f"Bulk updated {updated_count} receipts to status '{status}'")
            return updated_count

        except Exception as e:
            logger.error(f"Database error bulk updating receipts: {e}")
            raise DatabaseError(
                f"Failed to bulk update receipts: {str(e)}",
                model_name="Receipt",
                details={"receipt_ids": receipt_ids, "status": status}
            )

    async def get_by_status(self, status: str, limit: int | None = None) -> list[Receipt]:
        """Get receipts by status."""
        try:
            queryset = Receipt.objects.filter(status=status).order_by('-uploaded_at')
            if limit:
                queryset = queryset[:limit]

            receipts = await sync_to_async(list)(queryset)
            logger.debug(f"Retrieved {len(receipts)} receipts with status '{status}'")
            return receipts

        except Exception as e:
            logger.error(f"Database error getting receipts by status '{status}': {e}")
            raise DatabaseError(
                f"Failed to get receipts by status: {str(e)}",
                model_name="Receipt",
                details={"status": status}
            )


# Global repository instance
receipt_repository = ReceiptRepository()
