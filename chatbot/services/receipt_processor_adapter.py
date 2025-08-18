"""
Adapter to integrate new ReceiptProcessorV2 with existing codebase.
This allows gradual migration from old to new architecture.
"""

import logging
from typing import Optional, List, Dict, Any

from django.conf import settings

from .receipt_processor_v2 import ReceiptProcessorV2, create_receipt_processor
from ..config.receipt_config import get_config

logger = logging.getLogger(__name__)


class ReceiptProcessorAdapter:
    """
    Adapter that provides backward compatibility while allowing
    gradual migration to the new architecture.
    """
    
    def __init__(self):
        self.use_v2 = getattr(settings, 'USE_RECEIPT_PROCESSOR_V2', True)
        self.processor_v2 = None
        
        if self.use_v2:
            try:
                self.processor_v2 = create_receipt_processor()
                logger.info("ReceiptProcessorV2 adapter initialized")
            except Exception as e:
                logger.error(f"Failed to initialize ReceiptProcessorV2, falling back to v1: {e}")
                self.use_v2 = False
        
        if not self.use_v2:
            # Import old processor only if needed to avoid circular imports
            from ..receipt_processor import receipt_processor
            self.processor_v1 = receipt_processor
            logger.info("Using legacy ReceiptProcessor (v1)")
    
    async def process_receipt(self, receipt_id: int) -> bool:
        """Process receipt using appropriate processor version."""
        logger.info(f"Processing receipt {receipt_id} with processor v{'2' if self.use_v2 else '1'}")
        
        if self.use_v2 and self.processor_v2:
            try:
                return await self.processor_v2.process_receipt(receipt_id)
            except Exception as e:
                logger.error(f"ReceiptProcessorV2 failed, attempting fallback to v1: {e}")
                # Fallback to v1 if v2 fails
                return await self._fallback_to_v1(receipt_id)
        else:
            return await self._process_with_v1(receipt_id)
    
    async def _process_with_v1(self, receipt_id: int) -> bool:
        """Process with legacy processor."""
        try:
            return await self.processor_v1.process_receipt(receipt_id)
        except Exception as e:
            logger.error(f"Legacy processor failed: {e}")
            return False
    
    async def _fallback_to_v1(self, receipt_id: int) -> bool:
        """Fallback to v1 processor when v2 fails."""
        logger.warning(f"Falling back to legacy processor for receipt {receipt_id}")
        if not hasattr(self, 'processor_v1'):
            from ..receipt_processor import receipt_processor
            self.processor_v1 = receipt_processor
        
        return await self._process_with_v1(receipt_id)
    
    async def batch_process_receipts(self, receipt_ids: List[int]) -> Dict[int, bool]:
        """Batch process receipts."""
        if self.use_v2 and self.processor_v2:
            try:
                return await self.processor_v2.batch_process_receipts(receipt_ids)
            except Exception as e:
                logger.error(f"Batch processing with v2 failed: {e}")
                # Fall back to sequential processing with v1
                return await self._batch_process_with_v1(receipt_ids)
        else:
            return await self._batch_process_with_v1(receipt_ids)
    
    async def _batch_process_with_v1(self, receipt_ids: List[int]) -> Dict[int, bool]:
        """Batch process with v1 (sequential)."""
        results = {}
        for receipt_id in receipt_ids:
            results[receipt_id] = await self._process_with_v1(receipt_id)
        return results
    
    def update_pantry(self, products_data: List[Dict[str, Any]]) -> bool:
        """Update pantry with extracted products."""
        # This functionality is shared between v1 and v2
        if hasattr(self, 'processor_v1'):
            return self.processor_v1.update_pantry(products_data)
        else:
            from ..receipt_processor import receipt_processor
            return receipt_processor.update_pantry(products_data)
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.use_v2 and self.processor_v2:
            await self.processor_v2.cleanup()
    
    def get_processor_info(self) -> Dict[str, Any]:
        """Get information about current processor."""
        info = {
            "version": "v2" if self.use_v2 else "v1",
            "use_v2_enabled": self.use_v2,
            "v2_available": self.processor_v2 is not None
        }
        
        if self.use_v2 and self.processor_v2:
            info.update(self.processor_v2.get_status_info())
        
        return info


# Global adapter instance
receipt_processor_adapter = ReceiptProcessorAdapter()


def get_receipt_processor() -> ReceiptProcessorAdapter:
    """Get the global receipt processor adapter."""
    return receipt_processor_adapter


# Convenience functions that maintain backward compatibility
async def process_receipt(receipt_id: int) -> bool:
    """Process receipt using the adapter."""
    return await receipt_processor_adapter.process_receipt(receipt_id)


def update_pantry(products_data: List[Dict[str, Any]]) -> bool:
    """Update pantry with extracted products."""
    return receipt_processor_adapter.update_pantry(products_data)