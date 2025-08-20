"""
Receipt processing service implementing business logic for receipt operations.
Part of the fat model, thin view pattern implementation.
"""

import hashlib
import logging

from django.db import transaction
from django.utils import timezone

from inventory.models import Receipt

from .exceptions_receipt import (
    DatabaseError,
    ReceiptError,
    ReceiptNotFoundError,
)
from .ocr_service import get_ocr_service
from .pantry_service_v2 import PantryServiceV2
from .receipt_cache import get_cache_manager
from .receipt_parser import get_receipt_parser

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

    def create_receipt_record(self, receipt_file) -> Receipt:
        """
        Create new receipt processing record.

        Args:
            receipt_file: Uploaded file

        Returns:
            Receipt instance
        """
        try:
            receipt = Receipt.objects.create(
                receipt_file=receipt_file, status="pending"
            )
            logger.info(f"Created receipt processing record: {receipt.id}")
            return receipt

        except Exception as e:
            logger.error(f"Error creating receipt record: {e}")
            raise

    def start_processing(self, receipt_id: int) -> bool:
        """
        Start receipt processing by triggering Celery task.

        Args:
            receipt_id: ID of receipt to process

        Returns:
            True if processing was successfully queued.
        
        Raises:
            ReceiptNotFoundError: If the receipt does not exist.
            ReceiptProcessingError: If the task could not be queued (e.g., broker down).
        """
        logger.info(f"🔄 Attempting to queue processing for receipt ID: {receipt_id}")

        try:
            receipt = Receipt.objects.get(id=receipt_id)
            logger.debug(f"Found receipt: {receipt}, current status: {receipt.status}")

            receipt.status = "processing"
            receipt.processing_step = "ocr_in_progress"
            receipt.error_message = ""
            receipt.save()

            # Trigger Celery task
            from ..tasks import orchestrate_receipt_processing

            task_result = orchestrate_receipt_processing.delay(receipt_id)
            logger.info(
                f"✅ Celery task queued successfully for receipt {receipt_id}, task ID: {task_result.id}"
            )
            return True

        except Receipt.DoesNotExist as e:
            error_msg = f"Receipt {receipt_id} not found in database"
            logger.error(f"❌ {error_msg}")
            raise ReceiptNotFoundError(error_msg) from e
        except Exception as e:
            # This will catch errors during .delay() if the broker is down
            error_msg = f"Failed to queue Celery task for receipt {receipt_id}: {e}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            
            # Revert status and save error
            try:
                receipt = Receipt.objects.get(id=receipt_id)
                receipt.mark_as_error("Nie można było zakolejkować zadania. Sprawdź połączenie z Redis/Valkey.")
            except Receipt.DoesNotExist:
                pass # Nothing to revert if it wasn't found in the first place

            raise ReceiptError(error_msg) from e

    def update_processing_status(
        self,
        receipt_id: int,
        status: str,
        raw_text: str | None = None,
        extracted_data: dict | None = None,
        error_message: str | None = None,
    ) -> bool:
        """
        Update receipt processing status.

        Args:
            receipt_id: Receipt ID
            status: New status
            raw_text: OCR raw text (optional)
            extracted_data: Extracted product data (optional)
            error_message: Error message if status is error

        Returns:
            True if updated successfully, False otherwise
        """
        try:
            receipt = Receipt.objects.get(id=receipt_id)

            if status == "ocr_done" and raw_text:
                receipt.mark_ocr_done(raw_text)
            elif status == "llm_in_progress":
                receipt.mark_llm_processing()
            elif status == "llm_done" and extracted_data:
                receipt.mark_llm_done(extracted_data)
            elif status == "ready_for_review":
                receipt.mark_as_ready_for_review()
            elif status == "completed":
                receipt.mark_as_completed()
            elif status == "error" and error_message:
                receipt.mark_as_error(error_message)
            else:
                # Generic status update
                receipt.status = status
                receipt.save()

            logger.info(f"Updated receipt {receipt_id} status to {status}")
            return True

        except Receipt.DoesNotExist:
            error_msg = f"Receipt {receipt_id} not found for status update"
            logger.error(error_msg)
            raise ReceiptNotFoundError(error_msg)
        except Exception as e:
            error_msg = f"Error updating receipt {receipt_id} status: {e}"
            logger.error(error_msg)
            raise DatabaseError(error_msg) from e

    def get_receipt_status(self, receipt_id: int) -> dict | None:
        """
        Get receipt processing status and details.

        Args:
            receipt_id: Receipt ID

        Returns:
            Dictionary with receipt status information
        """
        try:
            receipt = Receipt.objects.get(id=receipt_id)

            return {
                "id": receipt.id,
                "status": receipt.status,
                "status_display": receipt.get_status_display(),
                "status_with_message": receipt.get_status_display_with_message(),
                "is_ready_for_review": receipt.is_ready_for_review(),
                "is_completed": receipt.is_completed(),
                "has_error": receipt.has_error(),
                "is_processing": receipt.is_processing(),
                "error_message": receipt.error_message,
                "raw_ocr_text": receipt.raw_ocr_text,
                "extracted_data": receipt.extracted_data,
                "redirect_url": receipt.get_redirect_url(),
                "uploaded_at": receipt.uploaded_at.isoformat(),
                "processed_at": (
                    receipt.processed_at.isoformat() if receipt.processed_at else None
                ),
            }

        except Receipt.DoesNotExist:
            logger.warning(f"Receipt {receipt_id} not found")
            return None
        except Exception as e:
            logger.error(f"Error getting receipt {receipt_id} status: {e}")
            return None

    def get_extracted_products(self, receipt_id: int) -> list[dict]:
        """
        Get extracted products from receipt.

        Args:
            receipt_id: Receipt ID

        Returns:
            List of extracted product dictionaries
        """
        try:
            receipt = Receipt.objects.get(id=receipt_id)
            return receipt.get_extracted_products()

        except Receipt.DoesNotExist:
            logger.warning(f"Receipt {receipt_id} not found")
            return []
        except Exception as e:
            logger.error(f"Error getting products from receipt {receipt_id}: {e}")
            return []

    def finalize_receipt_processing(
        self,
        receipt_id: int,
        reviewed_products: list[dict]
    ) -> tuple[bool, str | None]:
        """
        Finalize receipt processing by updating pantry with reviewed products.

        Args:
            receipt_id: Receipt ID
            reviewed_products: List of reviewed/corrected product data

        Returns:
            Tuple of (success, error_message)
        """
        try:
            with transaction.atomic():
                receipt = Receipt.objects.get(id=receipt_id)

                if not receipt.is_ready_for_review():
                    return False, "Paragon nie jest gotowy do finalizacji"

                # TODO: Update pantry with reviewed products using new inventory system
                # For now, skip pantry update until migration is complete
                added, updated, errors = 0, 0, []
                logger.info("Skipping pantry update - migration to InventoryItem in progress")

                # Mark receipt as completed
                receipt.mark_as_completed()

                success_msg = f"Zaktualizowano spiżarnię: {added} nowych produktów, {updated} zaktualizowanych"
                if errors:
                    success_msg += f". Błędy: {len(errors)}"

                logger.info(f"Finalized receipt {receipt_id}: {success_msg}")
                return True, success_msg

        except Receipt.DoesNotExist:
            error_msg = f"Paragon {receipt_id} nie został znaleziony"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Błąd podczas finalizacji paragonu: {str(e)}"
            logger.error(f"Error finalizing receipt {receipt_id}: {e}")

            # Mark receipt as error
            try:
                receipt = Receipt.objects.get(id=receipt_id)
                receipt.mark_as_error(error_msg)
            except (Receipt.DoesNotExist, Exception) as mark_error_ex:
                logger.error(f"Failed to mark receipt {receipt_id} as error: {mark_error_ex}")

            return False, error_msg

    def process_receipt_ocr(self, receipt_id: int, use_fallback: bool = True) -> bool:
        """
        Process receipt with OCR using the new inventory Receipt model.
        """
        cache_manager = get_cache_manager()
        try:
            receipt = Receipt.objects.get(id=receipt_id)

            if not receipt.receipt_file:
                receipt.mark_as_error("No file uploaded for receipt")
                return False

            # --- Caching Logic: Check for existing OCR result ---
            try:
                with receipt.receipt_file.open('rb') as f:
                    file_content = f.read()
                file_hash = hashlib.sha256(file_content).hexdigest()
                
                cached_ocr = cache_manager.get_cached_ocr_result(file_hash)
                if cached_ocr:
                    logger.info(f"CACHE HIT: Found cached OCR result for receipt {receipt_id}")
                    receipt.raw_text = cached_ocr
                    receipt.status = "processing"
                    receipt.processing_step = "ocr_completed"
                    receipt.processing_notes = f"OCR completed from cache (hash: {file_hash[:8]})
                    receipt.save()
                    return True
            except Exception as e:
                logger.warning(f"Could not read receipt file for caching: {e}")
            # --- End Caching Logic ---

            receipt.status = "processing"
            receipt.processing_step = "ocr_in_progress"
            receipt.save()

            logger.info(f"Starting OCR processing for receipt {receipt_id}")

            ocr_service = get_ocr_service()
            if not ocr_service.is_available():
                receipt.mark_as_error("No OCR backends available")
                return False

            ocr_result = ocr_service.process_file(
                receipt.receipt_file.path, use_fallback=use_fallback
            )

            if ocr_result.success and ocr_result.text.strip():
                receipt.raw_text = ocr_result.to_dict()
                receipt.processing_step = "ocr_completed"
                receipt.processing_notes = f"OCR completed with {ocr_result.backend} (confidence: {ocr_result.confidence:.2f})"
                receipt.save()
                
                # --- Cache the successful result ---
                try:
                    with receipt.receipt_file.open('rb') as f:
                        file_content_for_hash = f.read()
                    file_hash_for_cache = hashlib.sha256(file_content_for_hash).hexdigest()
                    cache_manager.cache_ocr_result(file_hash_for_cache, ocr_result.to_dict())
                except Exception as e:
                    logger.warning(f"Failed to cache OCR result for receipt {receipt_id}: {e}")
                # --- End Caching ---

                logger.info(f"OCR completed for receipt {receipt_id}: {len(ocr_result.text)} chars extracted")
                return True
            else:
                error_msg = ocr_result.error_message or "OCR failed to extract text"
                receipt.mark_as_error(f"OCR failed: {error_msg}")
                receipt.raw_text = ocr_result.to_dict()
                receipt.save()
                logger.error(f"OCR failed for receipt {receipt_id}: {error_msg}")
                return False

        except Receipt.DoesNotExist:
            logger.error(f"Receipt {receipt_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error in OCR process for receipt {receipt_id}: {e}", exc_info=True)
            try:
                Receipt.objects.get(id=receipt_id).mark_as_error(f"OCR processing error: {str(e)}")
            except (Receipt.DoesNotExist, Exception) as update_error:
                logger.error(f"Failed to update receipt {receipt_id} status after OCR error: {update_error}")
            return False

    def process_receipt_parsing(self, receipt_id: int) -> bool:
        """
        Process receipt parsing from OCR text to structured data.
        """
        cache_manager = get_cache_manager()
        try:
            receipt = Receipt.objects.get(id=receipt_id)

            # --- Caching Logic: Check for existing parsed data ---
            cached_parsing = cache_manager.get_cached_parsed_receipt(receipt_id)
            if cached_parsing:
                logger.info(f"CACHE HIT: Found cached parsed data for receipt {receipt_id}")
                receipt.parsed_data = cached_parsing
                receipt.status = "processing"
                receipt.processing_step = "parsing_completed"
                receipt.processing_notes = "Parsing completed from cache"
                receipt.save()
                return True
            # --- End Caching Logic ---

            if receipt.processing_step != "ocr_completed":
                logger.warning(f"Receipt {receipt_id} not ready for parsing: {receipt.processing_step}")
                return receipt.processing_step == "parsing_completed"

            if not receipt.raw_text or not isinstance(receipt.raw_text, dict):
                receipt.mark_as_error("Parsing failed: No valid OCR text data")
                return False

            ocr_text = receipt.raw_text.get("text", "")
            if not ocr_text.strip():
                receipt.mark_as_error("Parsing failed: Empty OCR text")
                return False

            receipt.processing_step = "parsing_in_progress"
            receipt.save()

            logger.info(f"Starting parsing for receipt {receipt_id}: {len(ocr_text)} chars")

            parser = get_receipt_parser()
            parsed_receipt = parser.parse(ocr_text)

            if not parsed_receipt or not parsed_receipt.products:
                receipt.mark_as_error("Parsing failed: Parser returned empty or no-product result")
                return False

            parsed_data_dict = parsed_receipt.to_dict()
            receipt.parsed_data = parsed_data_dict
            receipt.processing_step = "parsing_completed"

            products_count = len(parsed_receipt.products)
            store_info = f"Store: {parsed_receipt.store_name or 'Unknown'}"
            total_info = f"Total: {parsed_receipt.total_amount or 'Unknown'}"
            receipt.processing_notes = f"Parsing completed: {products_count} products found. {store_info}, {total_info}"
            receipt.save()

            # --- Cache the successful result ---
            cache_manager.cache_parsed_receipt(receipt_id, parsed_data_dict)
            # --- End Caching ---

            logger.info(f"Parsing completed for receipt {receipt_id}: {products_count} products extracted")
            return True

        except Receipt.DoesNotExist:
            logger.error(f"Receipt {receipt_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error in parsing process for receipt {receipt_id}: {e}", exc_info=True)
            try:
                Receipt.objects.get(id=receipt_id).mark_as_error(f"Parsing error: {str(e)}")
            except (Receipt.DoesNotExist, Exception) as update_error:
                logger.error(f"Failed to update receipt {receipt_id} status after parsing error: {update_error}")
            return False

    def process_receipt_matching(self, receipt_id: int) -> bool:
        """
        Process product matching from parsed data to catalog products.

        Args:
            receipt_id: ID of the Receipt to match products

        Returns:
            True if matching succeeded, False otherwise
        """
        try:
            receipt = Receipt.objects.get(id=receipt_id)

            if receipt.processing_step != "parsing_completed":
                logger.warning(f"Receipt {receipt_id} not ready for matching: {receipt.processing_step}")
                return receipt.processing_step == "matching_completed"

            if not receipt.parsed_data or not isinstance(receipt.parsed_data, dict):
                receipt.mark_as_error("Matching failed: No valid parsed data")
                return False

            products_data = receipt.parsed_data.get("products", [])
            if not products_data:
                receipt.mark_as_completed() # No products to match, consider it done
                receipt.processing_notes += "\nMatching skipped: No products found in parsed data."
                receipt.save()
                logger.info(f"Matching skipped for receipt {receipt_id}: no products to match.")
                return True

            receipt.processing_step = "matching_in_progress"
            receipt.save()

            logger.info(f"Starting product matching for receipt {receipt_id}: {len(products_data)} products")

            from decimal import Decimal
            from .product_matcher import get_product_matcher
            from .receipt_parser import ParsedProduct

            parsed_products = [
                ParsedProduct(
                    name=p.get("name", ""),
                    quantity=p.get("quantity"),
                    unit_price=Decimal(p["unit_price"]) if p.get("unit_price") else None,
                    total_price=Decimal(p["total_price"]) if p.get("total_price") else None,
                    unit=p.get("unit"),
                    category=p.get("category"),
                    confidence=p.get("confidence", 0.0),
                    raw_line=p.get("raw_line"),
                ) for p in products_data
            ]

            matcher = get_product_matcher()
            match_results = matcher.batch_match_products(parsed_products)

            if not match_results:
                receipt.mark_as_error("Matching failed: Product matching returned no results")
                return False

            from inventory.models import ReceiptLineItem
            
            line_items_created = 0
            total_calculated = Decimal("0.00")

            for i, (parsed_product, match_result) in enumerate(zip(parsed_products, match_results)):
                try:
                    line_item = ReceiptLineItem.objects.create(
                        receipt=receipt,
                        product_name=parsed_product.name,
                        quantity=Decimal(str(parsed_product.quantity or 1.0)),
                        unit_price=parsed_product.unit_price or Decimal("0.00"),
                        line_total=parsed_product.total_price or Decimal("0.00"),
                        matched_product=match_result.product,
                        meta={
                            "match_confidence": match_result.confidence,
                            "match_type": match_result.match_type,
                            "normalized_name": match_result.normalized_name,
                            "similarity_score": match_result.similarity_score,
                            "original_line": parsed_product.raw_line,
                            "line_number": i + 1,
                        },
                    )
                    line_items_created += 1
                    total_calculated += line_item.line_total

                    if match_result.product and match_result.confidence >= 0.8:
                        matcher.update_product_aliases(match_result.product, parsed_product.name)
                except Exception as e:
                    logger.error(f"Error creating line item for '{parsed_product.name}': {e}")
                    continue

            exact_matches = sum(1 for r in match_results if r.match_type == "exact")
            fuzzy_matches = sum(1 for r in match_results if r.match_type == "fuzzy")
            alias_matches = sum(1 for r in match_results if r.match_type == "alias")
            ghost_created = sum(1 for r in match_results if r.match_type == "created")

            receipt.processing_step = "matching_completed"
            receipt.processing_notes += f"\nMatching completed: {line_items_created} items. Exact: {exact_matches}, Fuzzy: {fuzzy_matches}, Alias: {alias_matches}, New: {ghost_created}."
            
            if not receipt.total and total_calculated > 0:
                receipt.total = total_calculated
            
            receipt.mark_as_ready_for_review() # Now ready for user review
            
            logger.info(f"Matching completed for receipt {receipt_id}: {line_items_created} line items created")
            return True

        except Receipt.DoesNotExist:
            logger.error(f"Receipt {receipt_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error in matching process for receipt {receipt_id}: {e}", exc_info=True)
            try:
                Receipt.objects.get(id=receipt_id).mark_as_error(f"Matching error: {str(e)}")
            except (Receipt.DoesNotExist, Exception) as update_error:
                logger.error(f"Failed to update receipt {receipt_id} status after matching error: {update_error}")
            return False

    def get_recent_receipts(self, limit: int = 10) -> list[Receipt]:
        """
        Get recent receipt processing records.

        Args:
            limit: Maximum number of receipts to return

        Returns:
            List of Receipt instances
        """
        return Receipt.get_recent_receipts(limit)

    def get_processing_statistics(self) -> dict:
        """
        Get receipt processing statistics.

        Returns:
            Dictionary with processing statistics
        """
        return Receipt.get_statistics()

    def retry_failed_receipt(self, receipt_id: int) -> bool:
        """
        Retry processing for a failed receipt.

        Args:
            receipt_id: Receipt ID

        Returns:
            True if retry started successfully, False otherwise
        """
        try:
            receipt = Receipt.objects.get(id=receipt_id)

            if not receipt.has_error():
                logger.warning(
                    f"Receipt {receipt_id} is not in error state, cannot retry"
                )
                return False

            # Reset status and clear error message
            receipt.status = "pending"
            receipt.processing_step = "uploaded"
            receipt.error_message = ""
            receipt.parsed_data = {{}}
            receipt.raw_text = {{}}
            receipt.line_items.all().delete() # Clear old items
            receipt.save()

            # Start processing again
            return self.start_processing(receipt_id)

        except Receipt.DoesNotExist:
            logger.error(f"Receipt {receipt_id} not found for retry")
            return False
        except Exception as e:
            logger.error(f"Error retrying receipt {receipt_id}: {e}")
            return False

    def delete_receipt(self, receipt_id: int) -> bool:
        """
        Delete receipt processing record and associated file.

        Args:
            receipt_id: Receipt ID

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            receipt = Receipt.objects.get(id=receipt_id)

            # Delete file if exists
            if receipt.receipt_file:
                try:
                    receipt.receipt_file.delete()
                except Exception as e:
                    logger.warning(
                        f"Could not delete file for receipt {receipt_id}: {e}"
                    )

            receipt.delete()
            logger.info(f"Deleted receipt {receipt_id}")
            return True

        except Receipt.DoesNotExist:
            logger.warning(f"Receipt {receipt_id} not found for deletion")
            return False
        except Exception as e:
            logger.error(f"Error deleting receipt {receipt_id}: {e}")
            return False

    def cleanup_old_receipts(self, days: int = 90) -> tuple[int, int]:
        """
        Clean up old completed receipts.

        Args:
            days: Age in days for receipts to be considered old

        Returns:
            Tuple of (count_deleted, count_errors)
        """
        cutoff_date = timezone.now() - timezone.timedelta(days=days)

        old_receipts = Receipt.objects.filter(
            status="completed", processed_at__lt=cutoff_date
        )

        deleted_count = 0
        error_count = 0

        for receipt in old_receipts:
            try:
                if self.delete_receipt(receipt.id):
                    deleted_count += 1
                else:
                    error_count += 1
            except Exception as e:
                logger.error(f"Error deleting old receipt {receipt.id}: {e}")
                error_count += 1

        logger.info(
            f"Cleanup completed: {deleted_count} receipts deleted, {error_count} errors"
        )
        return deleted_count, error_count
