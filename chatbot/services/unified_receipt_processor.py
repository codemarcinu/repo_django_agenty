"""
Unified Receipt Processor implementing the new architecture from the improvement plan.
This implements the unified Receipt system from FAZA 1.
"""

import logging
from decimal import Decimal
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from django.db import transaction
from django.utils import timezone

from inventory.models import Receipt, ReceiptLineItem
from .receipt_parser import get_receipt_parser
from .product_matcher import ProductMatcher
from .inventory_service import get_inventory_service

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of receipt processing operation."""
    
    success: bool
    receipt_id: Optional[int] = None
    message: str = ""
    error_stage: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    @classmethod
    def success_result(cls, receipt_id: int, message: str = "Processing completed successfully", **metadata):
        return cls(
            success=True,
            receipt_id=receipt_id,
            message=message,
            metadata=metadata
        )
    
    @classmethod
    def error_result(cls, error_stage: str, message: str, receipt_id: Optional[int] = None, **metadata):
        return cls(
            success=False,
            receipt_id=receipt_id,
            message=message,
            error_stage=error_stage,
            metadata=metadata
        )


class ReceiptProcessingError(Exception):
    """Custom exception for receipt processing errors."""
    
    def __init__(self, stage: str, message: str, receipt_id: Optional[int] = None):
        self.stage = stage
        self.message = message
        self.receipt_id = receipt_id
        super().__init__(f"Receipt {receipt_id} failed at {stage}: {message}")


class UnifiedReceiptProcessor:
    """
    Unified receipt processor implementing the new architecture.
    Handles the complete pipeline: OCR → Parse → Match → Inventory
    """
    
    def __init__(self):
        self.parser = get_receipt_parser()
        self.matcher = ProductMatcher()
        self.inventory_service = get_inventory_service()
    
    def create_receipt_from_file(self, receipt_file, user_id: Optional[str] = None) -> ProcessingResult:
        """Create a new receipt record from uploaded file."""
        try:
            with transaction.atomic():
                receipt = Receipt.objects.create(
                    receipt_file=receipt_file,
                    status='uploaded',
                    source_file_path=receipt_file.name,
                    uploaded_at=timezone.now(),
                    processing_notes=f"Created by user: {user_id}" if user_id else ""
                )
                
                logger.info(f"Created receipt {receipt.id} from file {receipt_file.name}")
                
                return ProcessingResult.success_result(
                    receipt_id=receipt.id,
                    message="Receipt created successfully",
                    file_name=receipt_file.name
                )
                
        except Exception as e:
            logger.error(f"Error creating receipt from file {receipt_file.name}: {e}")
            return ProcessingResult.error_result(
                error_stage="file_upload",
                message=f"Failed to create receipt: {str(e)}"
            )
    
    async def process_receipt(self, receipt_id: int) -> ProcessingResult:
        """
        Process receipt through the complete pipeline.
        
        Args:
            receipt_id: ID of the receipt to process
            
        Returns:
            ProcessingResult with success/failure information
        """
        try:
            receipt = Receipt.objects.get(id=receipt_id)
            
            # 1. OCR Processing
            logger.info(f"Starting OCR processing for receipt {receipt_id}")
            receipt.mark_as_processing()
            
            ocr_result = await self._process_ocr(receipt)
            if not ocr_result.success:
                return ocr_result
            
            # 2. Parsing & Validation
            logger.info(f"Starting parsing for receipt {receipt_id}")
            receipt.status = "processing_parsing"
            receipt.save()
            
            parse_result = await self._process_parsing(receipt)
            if not parse_result.success:
                return parse_result
            
            # 3. Product Matching
            logger.info(f"Starting product matching for receipt {receipt_id}")
            receipt.status = "matching"
            receipt.save()
            
            match_result = await self._process_matching(receipt)
            if not match_result.success:
                return match_result
            
            # 4. Inventory Update
            logger.info(f"Starting inventory update for receipt {receipt_id}")
            inventory_result = await self._update_inventory(receipt)
            if not inventory_result.success:
                return inventory_result
            
            # Mark as completed
            receipt.mark_as_completed()
            
            logger.info(f"Successfully processed receipt {receipt_id}")
            return ProcessingResult.success_result(
                receipt_id=receipt_id,
                message="Receipt processed successfully",
                products_found=len(receipt.line_items.all()),
                total_amount=str(receipt.total) if receipt.total else None
            )
            
        except Receipt.DoesNotExist:
            return ProcessingResult.error_result(
                error_stage="lookup",
                message=f"Receipt {receipt_id} not found"
            )
        except Exception as e:
            logger.error(f"Unexpected error processing receipt {receipt_id}: {e}", exc_info=True)
            
            # Mark receipt as error if it exists
            try:
                receipt = Receipt.objects.get(id=receipt_id)
                receipt.mark_as_error(f"Unexpected error: {str(e)}")
            except:
                pass
            
            return ProcessingResult.error_result(
                error_stage="processing",
                message=f"Unexpected error: {str(e)}",
                receipt_id=receipt_id
            )
    
    async def _process_ocr(self, receipt: Receipt) -> ProcessingResult:
        """Process OCR for receipt."""
        try:
            # Import OCR service
            from .async_ocr_service import AsyncOCRService
            
            ocr_service = AsyncOCRService()
            
            if not receipt.receipt_file:
                raise ReceiptProcessingError("ocr", "No receipt file to process", receipt.id)
            
            # Process OCR
            ocr_text = await ocr_service.extract_text_from_file(receipt.receipt_file.path)
            
            # Save OCR result
            receipt.mark_ocr_done(ocr_text)
            receipt.raw_text = {
                'text': ocr_text,
                'processed_at': timezone.now().isoformat(),
                'method': 'async_ocr_service'
            }
            receipt.save()
            
            return ProcessingResult.success_result(
                receipt_id=receipt.id,
                message="OCR completed successfully"
            )
            
        except Exception as e:
            receipt.mark_as_error(f"OCR failed: {str(e)}")
            return ProcessingResult.error_result(
                error_stage="ocr",
                message=str(e),
                receipt_id=receipt.id
            )
    
    async def _process_parsing(self, receipt: Receipt) -> ProcessingResult:
        """Process parsing for receipt."""
        try:
            if not receipt.raw_ocr_text:
                raise ReceiptProcessingError("parsing", "No OCR text to parse", receipt.id)
            
            # Parse receipt text
            parsed_receipt = self.parser.parse(receipt.raw_ocr_text)
            
            # Extract structured data
            extracted_data = {
                'store_name': parsed_receipt.store_name or '',
                'total_amount': str(parsed_receipt.total_amount) if parsed_receipt.total_amount else None,
                'transaction_date': parsed_receipt.transaction_date.isoformat() if parsed_receipt.transaction_date else None,
                'products': [
                    {
                        'name': p.name,
                        'quantity': float(p.quantity) if p.quantity else 1.0,
                        'unit_price': str(p.unit_price) if p.unit_price else None,
                        'total_price': str(p.total_price) if p.total_price else None,
                        'confidence': p.confidence
                    }
                    for p in parsed_receipt.products
                ],
                'parser_metadata': parsed_receipt.meta or {}
            }
            
            # Update receipt with parsed data
            receipt.extracted_data = extracted_data
            receipt.parsed_data = extracted_data  # Compatibility
            receipt.store_name = parsed_receipt.store_name or receipt.store_name
            receipt.total = parsed_receipt.total_amount or receipt.total
            receipt.purchased_at = parsed_receipt.transaction_date or receipt.uploaded_at
            receipt.status = "parsing_completed"
            receipt.save()
            
            return ProcessingResult.success_result(
                receipt_id=receipt.id,
                message="Parsing completed successfully",
                products_found=len(parsed_receipt.products)
            )
            
        except Exception as e:
            receipt.mark_as_error(f"Parsing failed: {str(e)}")
            return ProcessingResult.error_result(
                error_stage="parsing",
                message=str(e),
                receipt_id=receipt.id
            )
    
    async def _process_matching(self, receipt: Receipt) -> ProcessingResult:
        """Process product matching for receipt."""
        try:
            if not receipt.extracted_data or 'products' not in receipt.extracted_data:
                raise ReceiptProcessingError("matching", "No products to match", receipt.id)
            
            products = receipt.extracted_data['products']
            matched_count = 0
            
            # Create receipt line items
            for product_data in products:
                line_item = ReceiptLineItem.objects.create(
                    receipt=receipt,
                    product_name=product_data['name'],
                    quantity=Decimal(str(product_data['quantity'])),
                    unit_price=Decimal(str(product_data['unit_price'])) if product_data['unit_price'] else Decimal('0'),
                    line_total=Decimal(str(product_data['total_price'])) if product_data['total_price'] else Decimal('0'),
                    meta={
                        'confidence': product_data.get('confidence', 0.0),
                        'original_text': product_data.get('raw_line', '')
                    }
                )
                
                # Attempt to match with existing product
                matched_product = await self.matcher.match_product_async(product_data['name'])
                if matched_product:
                    line_item.matched_product = matched_product
                    line_item.save()
                    matched_count += 1
            
            receipt.status = "completed"
            receipt.save()
            
            return ProcessingResult.success_result(
                receipt_id=receipt.id,
                message="Product matching completed",
                total_products=len(products),
                matched_products=matched_count
            )
            
        except Exception as e:
            receipt.mark_as_error(f"Product matching failed: {str(e)}")
            return ProcessingResult.error_result(
                error_stage="matching",
                message=str(e),
                receipt_id=receipt.id
            )
    
    async def _update_inventory(self, receipt: Receipt) -> ProcessingResult:
        """Update inventory with receipt data."""
        try:
            # For now, this is a placeholder - the inventory update will be handled
            # by a separate process or manual review
            
            # Mark receipt as ready for review instead of auto-updating inventory
            receipt.mark_as_ready_for_review()
            
            return ProcessingResult.success_result(
                receipt_id=receipt.id,
                message="Receipt ready for inventory review"
            )
            
        except Exception as e:
            receipt.mark_as_error(f"Inventory update failed: {str(e)}")
            return ProcessingResult.error_result(
                error_stage="inventory_update",
                message=str(e),
                receipt_id=receipt.id
            )
    
    def get_receipt_status(self, receipt_id: int) -> Dict[str, Any]:
        """Get current status of receipt processing."""
        try:
            receipt = Receipt.objects.get(id=receipt_id)
            
            return {
                'receipt_id': receipt_id,
                'status': receipt.status,
                'status_display': receipt.get_status_display(),
                'message': receipt.get_status_display_with_message(),
                'progress': self._calculate_progress(receipt.status),
                'error': receipt.has_error(),
                'error_message': receipt.error_message if receipt.has_error() else None,
                'created_at': receipt.uploaded_at.isoformat(),
                'updated_at': receipt.updated_at.isoformat(),
            }
            
        except Receipt.DoesNotExist:
            return {
                'receipt_id': receipt_id,
                'status': 'not_found',
                'error': True,
                'error_message': 'Receipt not found'
            }
    
    def _calculate_progress(self, status: str) -> int:
        """Calculate progress percentage based on status."""
        progress_map = {
            'uploaded': 10,
            'ocr_in_progress': 25,
            'ocr_done': 40,
            'processing_parsing': 50,
            'parsing_completed': 65,
            'matching': 80,
            'ready_for_review': 90,
            'completed': 100,
            'error': 0
        }
        return progress_map.get(status, 0)


# Factory function for dependency injection
def get_unified_receipt_processor() -> UnifiedReceiptProcessor:
    """Get unified receipt processor instance."""
    return UnifiedReceiptProcessor()