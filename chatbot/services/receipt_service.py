"""
Receipt processing service implementing business logic for receipt operations.
Part of the fat model, thin view pattern implementation.
"""
import json
import logging
from typing import Dict, List, Optional, Tuple
from django.db import transaction
from django.utils import timezone

from ..models import ReceiptProcessing
from .pantry_service import PantryService

logger = logging.getLogger(__name__)


class ReceiptService:
    """Service class for receipt processing operations"""
    
    def __init__(self):
        self.pantry_service = PantryService()
    
    def create_receipt_record(self, receipt_file) -> ReceiptProcessing:
        """
        Create new receipt processing record.
        
        Args:
            receipt_file: Uploaded file
            
        Returns:
            ReceiptProcessing instance
        """
        try:
            receipt = ReceiptProcessing.objects.create(
                receipt_file=receipt_file,
                status='uploaded'
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
            True if processing started successfully, False otherwise
        """
        logger.info(f"🔄 Starting processing for receipt ID: {receipt_id}")
        
        try:
            receipt = ReceiptProcessing.objects.get(id=receipt_id)
            logger.debug(f"Found receipt: {receipt}, current status: {receipt.status}")
            
            logger.info(f"Marking receipt {receipt_id} as processing...")
            receipt.mark_as_processing()
            logger.debug(f"Receipt {receipt_id} status updated to: {receipt.status}")
            
            # Try to trigger Celery task
            logger.info(f"Attempting to start Celery task for receipt {receipt_id}")
            try:
                from ..tasks import process_receipt_task
                logger.debug("Celery task imported successfully")
                
                task_result = process_receipt_task.delay(receipt_id)
                logger.info(f"✅ Celery task started successfully for receipt {receipt_id}, task ID: {task_result.id}")
                
            except Exception as celery_error:
                logger.warning(f"⚠️ Celery task failed for receipt {receipt_id}: {celery_error}")
                logger.info(f"Falling back to synchronous processing for receipt {receipt_id}")
                
                # Fallback to synchronous processing
                try:
                    from ..receipt_processor import receipt_processor
                    logger.debug("Receipt processor imported successfully")
                    
                    logger.info(f"Starting synchronous OCR processing for receipt {receipt_id}")
                    receipt_processor.process_receipt(receipt_id)
                    logger.info(f"✅ Completed synchronous processing for receipt {receipt_id}")
                    
                except Exception as sync_error:
                    logger.error(f"❌ Both Celery and synchronous processing failed for receipt {receipt_id}: {sync_error}", exc_info=True)
                    receipt.mark_as_error(f"Przetwarzanie nie powiodło się: {sync_error}")
                    return False
            
            logger.info(f"✅ Processing workflow completed for receipt {receipt_id}")
            return True
            
        except ReceiptProcessing.DoesNotExist:
            logger.error(f"❌ Receipt {receipt_id} not found in database")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error starting receipt processing {receipt_id}: {e}", exc_info=True)
            try:
                receipt = ReceiptProcessing.objects.get(id=receipt_id)
                receipt.mark_as_error(f"Nie udało się rozpocząć przetwarzania: {e}")
                logger.info(f"Marked receipt {receipt_id} as error due to processing failure")
            except Exception as mark_error_ex:
                logger.error(f"Failed to mark receipt {receipt_id} as error: {mark_error_ex}")
            return False
    
    def update_processing_status(
        self, 
        receipt_id: int, 
        status: str, 
        raw_text: Optional[str] = None,
        extracted_data: Optional[Dict] = None,
        error_message: Optional[str] = None
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
            receipt = ReceiptProcessing.objects.get(id=receipt_id)
            
            if status == 'ocr_done' and raw_text:
                receipt.mark_ocr_done(raw_text)
            elif status == 'llm_in_progress':
                receipt.mark_llm_processing()
            elif status == 'llm_done' and extracted_data:
                receipt.mark_llm_done(extracted_data)
            elif status == 'ready_for_review':
                receipt.mark_as_ready_for_review()
            elif status == 'completed':
                receipt.mark_as_completed()
            elif status == 'error' and error_message:
                receipt.mark_as_error(error_message)
            else:
                # Generic status update
                receipt.status = status
                receipt.save()
            
            logger.info(f"Updated receipt {receipt_id} status to {status}")
            return True
            
        except ReceiptProcessing.DoesNotExist:
            logger.error(f"Receipt {receipt_id} not found for status update")
            return False
        except Exception as e:
            logger.error(f"Error updating receipt {receipt_id} status: {e}")
            return False
    
    def get_receipt_status(self, receipt_id: int) -> Optional[Dict]:
        """
        Get receipt processing status and details.
        
        Args:
            receipt_id: Receipt ID
            
        Returns:
            Dictionary with receipt status information
        """
        try:
            receipt = ReceiptProcessing.objects.get(id=receipt_id)
            
            return {
                'id': receipt.id,
                'status': receipt.status,
                'status_display': receipt.get_status_display(),
                'status_with_message': receipt.get_status_display_with_message(),
                'is_ready_for_review': receipt.is_ready_for_review(),
                'is_completed': receipt.is_completed(),
                'has_error': receipt.has_error(),
                'is_processing': receipt.is_processing(),
                'error_message': receipt.error_message,
                'raw_ocr_text': receipt.raw_ocr_text,
                'extracted_data': receipt.extracted_data,
                'redirect_url': receipt.get_redirect_url(),
                'uploaded_at': receipt.uploaded_at.isoformat(),
                'processed_at': receipt.processed_at.isoformat() if receipt.processed_at else None
            }
            
        except ReceiptProcessing.DoesNotExist:
            logger.warning(f"Receipt {receipt_id} not found")
            return None
        except Exception as e:
            logger.error(f"Error getting receipt {receipt_id} status: {e}")
            return None
    
    def get_extracted_products(self, receipt_id: int) -> List[Dict]:
        """
        Get extracted products from receipt.
        
        Args:
            receipt_id: Receipt ID
            
        Returns:
            List of extracted product dictionaries
        """
        try:
            receipt = ReceiptProcessing.objects.get(id=receipt_id)
            return receipt.get_extracted_products()
            
        except ReceiptProcessing.DoesNotExist:
            logger.warning(f"Receipt {receipt_id} not found")
            return []
        except Exception as e:
            logger.error(f"Error getting products from receipt {receipt_id}: {e}")
            return []
    
    def finalize_receipt_processing(
        self, 
        receipt_id: int, 
        reviewed_products: List[Dict]
    ) -> Tuple[bool, Optional[str]]:
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
                receipt = ReceiptProcessing.objects.get(id=receipt_id)
                
                if not receipt.is_ready_for_review():
                    return False, "Paragon nie jest gotowy do finalizacji"
                
                # Update pantry with reviewed products
                added, updated, errors = self.pantry_service.bulk_update_from_receipt(
                    reviewed_products
                )
                
                # Mark receipt as completed
                receipt.mark_as_completed()
                
                success_msg = f"Zaktualizowano spiżarnię: {added} nowych produktów, {updated} zaktualizowanych"
                if errors:
                    success_msg += f". Błędy: {len(errors)}"
                
                logger.info(f"Finalized receipt {receipt_id}: {success_msg}")
                return True, success_msg
                
        except ReceiptProcessing.DoesNotExist:
            error_msg = f"Paragon {receipt_id} nie został znaleziony"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Błąd podczas finalizacji paragonu: {str(e)}"
            logger.error(f"Error finalizing receipt {receipt_id}: {e}")
            
            # Mark receipt as error
            try:
                receipt = ReceiptProcessing.objects.get(id=receipt_id)
                receipt.mark_as_error(error_msg)
            except:
                pass
                
            return False, error_msg
    
    def get_recent_receipts(self, limit: int = 10) -> List[ReceiptProcessing]:
        """
        Get recent receipt processing records.
        
        Args:
            limit: Maximum number of receipts to return
            
        Returns:
            List of ReceiptProcessing instances
        """
        return ReceiptProcessing.get_recent_receipts(limit)
    
    def get_processing_statistics(self) -> Dict:
        """
        Get receipt processing statistics.
        
        Returns:
            Dictionary with processing statistics
        """
        return ReceiptProcessing.get_statistics()
    
    def retry_failed_receipt(self, receipt_id: int) -> bool:
        """
        Retry processing for a failed receipt.
        
        Args:
            receipt_id: Receipt ID
            
        Returns:
            True if retry started successfully, False otherwise
        """
        try:
            receipt = ReceiptProcessing.objects.get(id=receipt_id)
            
            if not receipt.has_error():
                logger.warning(f"Receipt {receipt_id} is not in error state, cannot retry")
                return False
            
            # Reset status and clear error message
            receipt.status = 'uploaded'
            receipt.error_message = ''
            receipt.save()
            
            # Start processing again
            return self.start_processing(receipt_id)
            
        except ReceiptProcessing.DoesNotExist:
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
            receipt = ReceiptProcessing.objects.get(id=receipt_id)
            
            # Delete file if exists
            if receipt.receipt_file:
                try:
                    receipt.receipt_file.delete()
                except Exception as e:
                    logger.warning(f"Could not delete file for receipt {receipt_id}: {e}")
            
            receipt.delete()
            logger.info(f"Deleted receipt {receipt_id}")
            return True
            
        except ReceiptProcessing.DoesNotExist:
            logger.warning(f"Receipt {receipt_id} not found for deletion")
            return False
        except Exception as e:
            logger.error(f"Error deleting receipt {receipt_id}: {e}")
            return False
    
    def cleanup_old_receipts(self, days: int = 90) -> Tuple[int, int]:
        """
        Clean up old completed receipts.
        
        Args:
            days: Age in days for receipts to be considered old
            
        Returns:
            Tuple of (count_deleted, count_errors)
        """
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        
        old_receipts = ReceiptProcessing.objects.filter(
            status='completed',
            processed_at__lt=cutoff_date
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
        
        logger.info(f"Cleanup completed: {deleted_count} receipts deleted, {error_count} errors")
        return deleted_count, error_count