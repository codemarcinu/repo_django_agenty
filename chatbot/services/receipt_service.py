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
from inventory.models import Receipt
from .pantry_service import PantryService
from .ocr_service import get_ocr_service
from .receipt_parser import get_receipt_parser

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
    
    def process_receipt_ocr(self, receipt_id: int, use_fallback: bool = True) -> bool:
        """
        Process receipt with OCR using the new inventory Receipt model.
        
        Args:
            receipt_id: ID of the Receipt to process
            use_fallback: Whether to use fallback OCR backends
            
        Returns:
            True if OCR processing succeeded, False otherwise
        """
        try:
            receipt = Receipt.objects.get(id=receipt_id)
            
            if receipt.status != 'pending_ocr':
                logger.warning(f"Receipt {receipt_id} is not in pending_ocr status: {receipt.status}")
                return False
            
            # Update status to processing
            receipt.status = 'processing_ocr'
            receipt.save()
            
            logger.info(f"Starting OCR processing for receipt {receipt_id}: {receipt.source_file_path}")
            
            # Get OCR service
            ocr_service = get_ocr_service()
            
            if not ocr_service.is_available():
                error_msg = "No OCR backends available"
                logger.error(error_msg)
                receipt.status = 'error'
                receipt.processing_notes = error_msg
                receipt.save()
                return False
            
            # Process file with OCR
            ocr_result = ocr_service.process_file(
                receipt.source_file_path, 
                use_fallback=use_fallback
            )
            
            if ocr_result.success and ocr_result.text.strip():
                # OCR succeeded
                receipt.raw_text = ocr_result.to_dict()
                receipt.status = 'ocr_completed'
                receipt.processing_notes = f"OCR completed with {ocr_result.backend} (confidence: {ocr_result.confidence:.2f})"
                receipt.save()
                
                logger.info(f"OCR completed for receipt {receipt_id}: {len(ocr_result.text)} characters extracted")
                return True
            else:
                # OCR failed
                error_msg = ocr_result.error_message or "OCR failed to extract text"
                receipt.status = 'error'
                receipt.processing_notes = f"OCR failed: {error_msg}"
                receipt.raw_text = ocr_result.to_dict()  # Store result even if failed for debugging
                receipt.save()
                
                logger.error(f"OCR failed for receipt {receipt_id}: {error_msg}")
                return False
                
        except Receipt.DoesNotExist:
            logger.error(f"Receipt {receipt_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error during OCR processing for receipt {receipt_id}: {e}", exc_info=True)
            try:
                receipt = Receipt.objects.get(id=receipt_id)
                receipt.status = 'error'
                receipt.processing_notes = f"OCR processing error: {str(e)}"
                receipt.save()
            except:
                pass
            return False
    
    def process_receipt_parsing(self, receipt_id: int) -> bool:
        """
        Process receipt parsing from OCR text to structured data.
        
        Args:
            receipt_id: ID of the Receipt to parse
            
        Returns:
            True if parsing succeeded, False otherwise
        """
        try:
            receipt = Receipt.objects.get(id=receipt_id)
            
            if receipt.status != 'ocr_completed':
                logger.warning(f"Receipt {receipt_id} is not in ocr_completed status: {receipt.status}")
                return False
            
            # Check if we have OCR text
            if not receipt.raw_text or not isinstance(receipt.raw_text, dict):
                error_msg = "No valid OCR text data"
                logger.error(f"Receipt {receipt_id} has no valid OCR text data")
                receipt.status = 'error'
                receipt.processing_notes = f"Parsing failed: {error_msg}"
                receipt.save()
                return False
            
            ocr_text = receipt.raw_text.get('text', '')
            if not ocr_text.strip():
                error_msg = "Empty OCR text"
                logger.error(f"Receipt {receipt_id} has empty OCR text")
                receipt.status = 'error'
                receipt.processing_notes = f"Parsing failed: {error_msg}"
                receipt.save()
                return False
            
            # Update status to processing
            receipt.status = 'processing_parsing'
            receipt.save()
            
            logger.info(f"Starting parsing for receipt {receipt_id}: {len(ocr_text)} characters")
            
            # Get parser and parse the text
            parser = get_receipt_parser()
            parsed_receipt = parser.parse(ocr_text)
            
            if not parsed_receipt:
                error_msg = "Parser returned empty result"
                logger.error(f"Parsing failed for receipt {receipt_id}: {error_msg}")
                receipt.status = 'error'
                receipt.processing_notes = f"Parsing failed: {error_msg}"
                receipt.save()
                return False
            
            # Store parsed data
            receipt.parsed_data = parsed_receipt.to_dict()
            receipt.status = 'parsing_completed'
            
            # Add processing notes with parsing summary
            products_count = len(parsed_receipt.products)
            store_info = f"Store: {parsed_receipt.store_name}" if parsed_receipt.store_name else "Store: Unknown"
            total_info = f"Total: {parsed_receipt.total_amount}" if parsed_receipt.total_amount else "Total: Unknown"
            
            receipt.processing_notes = f"Parsing completed: {products_count} products found. {store_info}, {total_info}"
            receipt.save()
            
            logger.info(f"Parsing completed for receipt {receipt_id}: {products_count} products extracted")
            return True
            
        except Receipt.DoesNotExist:
            logger.error(f"Receipt {receipt_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error during parsing for receipt {receipt_id}: {e}", exc_info=True)
            try:
                receipt = Receipt.objects.get(id=receipt_id)
                receipt.status = 'error'
                receipt.processing_notes = f"Parsing error: {str(e)}"
                receipt.save()
            except:
                pass
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
            
            if receipt.status != 'parsing_completed':
                logger.warning(f"Receipt {receipt_id} is not in parsing_completed status: {receipt.status}")
                return False
            
            # Check if we have parsed data
            if not receipt.parsed_data or not isinstance(receipt.parsed_data, dict):
                error_msg = "No valid parsed data"
                logger.error(f"Receipt {receipt_id} has no valid parsed data")
                receipt.status = 'error'
                receipt.processing_notes = f"Matching failed: {error_msg}"
                receipt.save()
                return False
            
            products_data = receipt.parsed_data.get('products', [])
            if not products_data:
                error_msg = "No products in parsed data"
                logger.error(f"Receipt {receipt_id} has no products in parsed data")
                receipt.status = 'error'
                receipt.processing_notes = f"Matching failed: {error_msg}"
                receipt.save()
                return False
            
            # Update status to matching
            receipt.status = 'matching'
            receipt.save()
            
            logger.info(f"Starting product matching for receipt {receipt_id}: {len(products_data)} products")
            
            # Convert parsed data to ParsedProduct objects
            from .receipt_parser import ParsedProduct
            from .product_matcher import get_product_matcher
            from decimal import Decimal
            
            parsed_products = []
            for product_data in products_data:
                parsed_product = ParsedProduct(
                    name=product_data.get('name', ''),
                    quantity=product_data.get('quantity'),
                    unit_price=Decimal(product_data['unit_price']) if product_data.get('unit_price') else None,
                    total_price=Decimal(product_data['total_price']) if product_data.get('total_price') else None,
                    unit=product_data.get('unit'),
                    category=product_data.get('category'),
                    confidence=product_data.get('confidence', 0.0),
                    raw_line=product_data.get('raw_line')
                )
                parsed_products.append(parsed_product)
            
            # Get matcher and match products
            matcher = get_product_matcher()
            match_results = matcher.batch_match_products(parsed_products)
            
            if not match_results:
                error_msg = "Product matching returned no results"
                logger.error(f"Matching failed for receipt {receipt_id}: {error_msg}")
                receipt.status = 'error'
                receipt.processing_notes = f"Matching failed: {error_msg}"
                receipt.save()
                return False
            
            # Create ReceiptLineItem records for matched products
            from inventory.models import ReceiptLineItem
            from decimal import Decimal
            
            line_items_created = 0
            total_calculated = Decimal('0.00')
            
            for i, (parsed_product, match_result) in enumerate(zip(parsed_products, match_results)):
                try:
                    # Create line item
                    line_item = ReceiptLineItem.objects.create(
                        receipt=receipt,
                        product_name=parsed_product.name,
                        quantity=Decimal(str(parsed_product.quantity or 1.0)),
                        unit_price=parsed_product.unit_price or Decimal('0.00'),
                        line_total=parsed_product.total_price or Decimal('0.00'),
                        matched_product=match_result.product,
                        meta={
                            'match_confidence': match_result.confidence,
                            'match_type': match_result.match_type,
                            'normalized_name': match_result.normalized_name,
                            'similarity_score': match_result.similarity_score,
                            'original_line': parsed_product.raw_line,
                            'line_number': i + 1
                        }
                    )
                    
                    line_items_created += 1
                    total_calculated += line_item.line_total
                    
                    # Add alias to matched product if it's a good match
                    if match_result.product and match_result.confidence >= 0.8:
                        matcher.update_product_aliases(match_result.product, parsed_product.name)
                    
                except Exception as e:
                    logger.error(f"Error creating line item for product '{parsed_product.name}': {e}")
                    continue
            
            # Update receipt with matching results
            receipt.status = 'completed'
            
            # Calculate matching statistics
            exact_matches = sum(1 for r in match_results if r.match_type == 'exact')
            fuzzy_matches = sum(1 for r in match_results if r.match_type == 'fuzzy')
            alias_matches = sum(1 for r in match_results if r.match_type == 'alias')
            ghost_created = sum(1 for r in match_results if r.match_type == 'created')
            
            # Update processing notes
            receipt.processing_notes += f"\nMatching completed: {line_items_created} line items created. "
            receipt.processing_notes += f"Exact: {exact_matches}, Fuzzy: {fuzzy_matches}, Alias: {alias_matches}, New: {ghost_created}. "
            receipt.processing_notes += f"Calculated total: {total_calculated}"
            
            # Update total if we calculated one and original is missing
            if receipt.total == Decimal('0.00') and total_calculated > Decimal('0.00'):
                receipt.total = total_calculated
            
            receipt.save()
            
            logger.info(f"Matching completed for receipt {receipt_id}: {line_items_created} line items created")
            return True
            
        except Receipt.DoesNotExist:
            logger.error(f"Receipt {receipt_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error during matching for receipt {receipt_id}: {e}", exc_info=True)
            try:
                receipt = Receipt.objects.get(id=receipt_id)
                receipt.status = 'error'
                receipt.processing_notes = f"Matching error: {str(e)}"
                receipt.save()
            except:
                pass
            return False
    
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