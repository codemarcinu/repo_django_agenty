"""
Optimized receipt processor with dependency injection and async architecture.
"""

import asyncio
import logging
import os
import time
from typing import Optional, Protocol, List, Dict, Any

from django.utils import timezone
from django.db import transaction
from asgiref.sync import sync_to_async

from .async_ocr_service import AsyncOCRService
from .receipt_llm_service import ReceiptLLMService
from .receipt_repository import ReceiptRepository
from .cache_service import CacheService
from .exceptions_receipt import (
    ReceiptProcessingError, 
    OCRError, 
    LLMError, 
    DatabaseError,
    FileValidationError
)
from ..config.receipt_config import ReceiptProcessingConfig, get_config
from ..validators import get_file_type
import magic # For MIME type validation

logger = logging.getLogger(__name__)


# Protocol definitions for dependency injection
class OCRServiceProtocol(Protocol):
    """Protocol for OCR service implementations."""
    async def extract_text_from_file(self, file_path: str) -> Optional[str]: ...
    async def cleanup(self) -> None: ...


class LLMServiceProtocol(Protocol):
    """Protocol for LLM service implementations."""
    async def extract_products(self, receipt_text: str) -> List[Dict[str, Any]]: ...
    def get_service_info(self) -> Dict[str, Any]: ...


class RepositoryProtocol(Protocol):
    """Protocol for repository implementations."""
    async def get_by_id(self, receipt_id: int) -> Optional[Any]: ...
    async def update_status(self, receipt_id: int, status: str, error_message: Optional[str] = None) -> bool: ...
    async def update_ocr_result(self, receipt_id: int, raw_ocr_text: str) -> bool: ...
    async def update_extraction_result(self, receipt_id: int, extracted_data: List[Dict[str, Any]]) -> bool: ...
    async def mark_as_error(self, receipt_id: int, error_message: str) -> bool: ...


class CacheServiceProtocol(Protocol):
    """Protocol for cache service implementations."""
    async def get_cached_ocr_result(self, file_path: str) -> Optional[str]: ...
    async def cache_ocr_result(self, file_path: str, text: str) -> bool: ...
    async def close(self) -> None: ...


class PerformanceMonitor:
    """Performance monitoring for receipt processing."""
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.metrics = {}
    
    def start_timer(self, operation: str) -> str:
        """Start timing an operation."""
        if not self.enabled:
            return ""
        
        timer_id = f"{operation}_{int(time.time() * 1000)}"
        self.metrics[timer_id] = {
            "operation": operation,
            "start_time": time.time(),
            "end_time": None,
            "duration": None
        }
        return timer_id
    
    def end_timer(self, timer_id: str) -> Optional[float]:
        """End timing an operation and return duration."""
        if not self.enabled or timer_id not in self.metrics:
            return None
        
        self.metrics[timer_id]["end_time"] = time.time()
        duration = self.metrics[timer_id]["end_time"] - self.metrics[timer_id]["start_time"]
        self.metrics[timer_id]["duration"] = duration
        
        logger.info(f"⏱️ {self.metrics[timer_id]['operation']} completed in {duration:.2f}s")
        return duration
    
    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        if not self.enabled:
            return {"enabled": False}
        
        operations = {}
        for metric in self.metrics.values():
            if metric["duration"] is not None:
                op_name = metric["operation"]
                if op_name not in operations:
                    operations[op_name] = {
                        "count": 0,
                        "total_time": 0,
                        "avg_time": 0,
                        "min_time": float('inf'),
                        "max_time": 0
                    }
                
                operations[op_name]["count"] += 1
                operations[op_name]["total_time"] += metric["duration"]
                operations[op_name]["min_time"] = min(operations[op_name]["min_time"], metric["duration"])
                operations[op_name]["max_time"] = max(operations[op_name]["max_time"], metric["duration"])
                operations[op_name]["avg_time"] = operations[op_name]["total_time"] / operations[op_name]["count"]
        
        return {
            "enabled": True,
            "operations": operations,
            "total_operations": len(self.metrics)
        }


class ReceiptProcessorV2:
    """
    Optimized receipt processor with dependency injection, async patterns,
    and comprehensive error handling.
    """
    
    def __init__(
        self,
        ocr_service: Optional[OCRServiceProtocol] = None,
        llm_service: Optional[LLMServiceProtocol] = None,
        repository: Optional[RepositoryProtocol] = None,
        cache_service: Optional[CacheServiceProtocol] = None,
        config: Optional[ReceiptProcessingConfig] = None
    ):
        # Dependency injection with default implementations
        self.ocr_service = ocr_service or AsyncOCRService()
        self.llm_service = llm_service or ReceiptLLMService()
        self.repository = repository or ReceiptRepository()
        self.cache_service = cache_service or CacheService()
        self.config = config or get_config()
        
        # Initialize performance monitoring
        self.performance_monitor = PerformanceMonitor(
            enabled=self.config.processing.enable_performance_monitoring
        )
        
        # Configure logging
        self._configure_logging()
        
        logger.info("ReceiptProcessorV2 initialized with dependency injection")
    
    def _configure_logging(self):
        """Configure logging level based on configuration."""
        log_level = getattr(logging, self.config.processing.log_level.upper(), logging.INFO)
        logger.setLevel(log_level)
    
    async def _validate_file(self, file_path: str) -> None:
        """Validate file exists and meets requirements."""
        if not os.path.exists(file_path):
            raise FileValidationError(f"File does not exist: {file_path}", file_path=file_path)
        
        file_size = os.path.getsize(file_path)
        if file_size > self.config.file.max_file_size:
            raise FileValidationError(
                f"File size {file_size} exceeds maximum {self.config.file.max_file_size}",
                file_path=file_path,
                details={"file_size": file_size, "max_size": self.config.file.max_file_size}
            )
        
        if file_size == 0:
            raise FileValidationError(f"File is empty: {file_path}", file_path=file_path)
        
        # Check file extension
        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension not in self.config.file.allowed_extensions:
            raise FileValidationError(
                f"File extension {file_extension} not allowed",
                file_path=file_path,
                details={"allowed_extensions": self.config.file.allowed_extensions}
            )
        
        # Validate MIME type using python-magic
        try:
            detected_mime_type = magic.from_file(file_path, mime=True)
            allowed_mime_types = [
                "image/jpeg", "image/png", "application/pdf", "image/webp"
            ] # This should ideally come from config.file.allowed_mime_types
            
            if detected_mime_type not in allowed_mime_types:
                raise FileValidationError(
                    f"Detected MIME type {detected_mime_type} is not allowed",
                    file_path=file_path,
                    details={"detected_mime_type": detected_mime_type, "allowed_mime_types": allowed_mime_types}
                )
        except Exception as e:
            raise FileValidationError(f"Could not determine file MIME type: {e}", file_path=file_path)
    
    async def _extract_text_with_monitoring(self, file_path: str) -> str:
        """Extract text from file with performance monitoring."""
        timer_id = self.performance_monitor.start_timer("ocr_extraction")
        
        try:
            extracted_text = await self.ocr_service.extract_text_from_file(file_path)
            
            if not extracted_text or not extracted_text.strip():
                raise OCRError("No text could be extracted from file", file_path=file_path)
            
            logger.info(f"✅ OCR extraction completed: {len(extracted_text)} characters")
            return extracted_text
            
        except OCRError:
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error during OCR: {e}", exc_info=True)
            raise OCRError(f"OCR extraction failed: {str(e)}", file_path=file_path)
        finally:
            self.performance_monitor.end_timer(timer_id)
    
    async def _extract_products_with_monitoring(self, receipt_text: str) -> List[Dict[str, Any]]:
        """Extract products with performance monitoring."""
        timer_id = self.performance_monitor.start_timer("llm_extraction")
        
        try:
            products_data = await self.llm_service.extract_products(receipt_text)
            
            if not products_data:
                raise LLMError("No products could be extracted from receipt text")
            
            logger.info(f"✅ LLM extraction completed: {len(products_data)} products")
            return products_data
            
        except LLMError:
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error during LLM extraction: {e}", exc_info=True)
            raise LLMError(f"LLM extraction failed: {str(e)}")
        finally:
            self.performance_monitor.end_timer(timer_id)
    
    async def process_receipt(self, receipt_processing_id: int) -> bool:
        """
        Process receipt with optimized async workflow.
        
        Args:
            receipt_processing_id: ID of the receipt processing record
            
        Returns:
            bool: True if processing successful, False otherwise
        """
        logger.info(f"🔄 STARTING OPTIMIZED PROCESSING for receipt ID: {receipt_processing_id}")
        overall_timer = self.performance_monitor.start_timer("total_processing")
        
        receipt_record = None
        
        try:
            async with sync_to_async(transaction.atomic)():
                # Get receipt record
                receipt_record = await self.repository.get_by_id(receipt_processing_id)
                if not receipt_record:
                    logger.error(f"❌ Receipt {receipt_processing_id} not found in database")
                    return False
                
                logger.info(f"✅ Found receipt record: {receipt_record.id}, status: {receipt_record.status}")
                
                # Get file path and validate
                file_path = receipt_record.receipt_file.path
                logger.info(f"Processing file: {file_path}")
                
                await self._validate_file(file_path)
                
                # Detect file type
                file_type = get_file_type(file_path)
                logger.info(f"Detected file type: {file_type}")
                
                # Phase 1: OCR Processing
                logger.info("🔍 Starting OCR phase...")
                await self.repository.update_status(receipt_processing_id, "ocr_in_progress")
                
                receipt_text = await self._extract_text_with_monitoring(file_path)
                
                # Update database with OCR results
                await self.repository.update_ocr_result(receipt_processing_id, receipt_text)
                logger.info(f"Receipt {receipt_processing_id} OCR phase completed")
                
                # Phase 2: LLM Processing
                logger.info("🤖 Starting LLM phase...")
                await self.repository.update_status(receipt_processing_id, "llm_in_progress")
                
                products_data = await self._extract_products_with_monitoring(receipt_text)
                
                # Update database with extraction results
                await self.repository.update_extraction_result(receipt_processing_id, products_data)
                
                # Performance summary
                perf_summary = self.performance_monitor.get_summary()
                logger.info(f"🎉 Receipt {receipt_processing_id} processing COMPLETED!")
                logger.info(f"📊 Performance summary: {perf_summary}")
                
                return True
            
        except FileValidationError as e:
            error_msg = f"File validation error: {e.message}"
            logger.error(f"❌ {error_msg}")
            if receipt_record:
                await self.repository.mark_as_error(receipt_processing_id, error_msg)
            return False
            
        except OCRError as e:
            error_msg = f"OCR error: {e.message}"
            logger.error(f"❌ {error_msg}")
            if receipt_record:
                await self.repository.mark_as_error(receipt_processing_id, error_msg)
            return False
            
        except LLMError as e:
            error_msg = f"LLM error: {e.message}"
            logger.error(f"❌ {error_msg}")
            if receipt_record:
                await self.repository.mark_as_error(receipt_processing_id, error_msg)
            return False
            
        except DatabaseError as e:
            error_msg = f"Database error: {e.message}"
            logger.error(f"❌ {error_msg}")
            return False
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"❌ CRITICAL ERROR during receipt processing: {error_msg}", exc_info=True)
            if receipt_record:
                try:
                    await self.repository.mark_as_error(receipt_processing_id, error_msg)
                except Exception as save_error:
                    logger.error(f"Failed to save error status: {save_error}")
            return False
            
        finally:
            self.performance_monitor.end_timer(overall_timer)
    
    async def batch_process_receipts(self, receipt_ids: List[int]) -> Dict[int, bool]:
        """
        Process multiple receipts concurrently with controlled concurrency.
        
        Args:
            receipt_ids: List of receipt IDs to process
            
        Returns:
            Dict mapping receipt ID to success status
        """
        logger.info(f"🔄 Starting batch processing of {len(receipt_ids)} receipts")
        
        # Create semaphore to limit concurrent processing
        semaphore = asyncio.Semaphore(self.config.processing.max_concurrent_processes)
        
        async def process_with_semaphore(receipt_id: int) -> tuple[int, bool]:
            async with semaphore:
                result = await self.process_receipt(receipt_id)
                return receipt_id, result
        
        # Process receipts concurrently
        tasks = [process_with_semaphore(receipt_id) for receipt_id in receipt_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect results
        result_dict = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error in batch processing: {result}")
                continue
            receipt_id, success = result
            result_dict[receipt_id] = success
        
        successful = sum(1 for success in result_dict.values() if success)
        logger.info(f"✅ Batch processing completed: {successful}/{len(receipt_ids)} successful")
        
        return result_dict
    
    async def cleanup(self):
        """Cleanup resources."""
        try:
            await self.ocr_service.cleanup()
            await self.cache_service.close()
            logger.info("ReceiptProcessorV2 cleanup completed")
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
    
    def get_status_info(self) -> Dict[str, Any]:
        """Get processor status and configuration information."""
        return {
            "processor_version": "v2",
            "config": self.config.to_dict(),
            "performance_monitoring": self.performance_monitor.enabled,
            "services": {
                "ocr": type(self.ocr_service).__name__,
                "llm": type(self.llm_service).__name__,
                "repository": type(self.repository).__name__,
                "cache": type(self.cache_service).__name__
            }
        }


# Factory function for creating processor instances
def create_receipt_processor(
    config: Optional[ReceiptProcessingConfig] = None
) -> ReceiptProcessorV2:
    """Factory function to create ReceiptProcessorV2 with default dependencies."""
    return ReceiptProcessorV2(config=config)


# Global processor instance
receipt_processor_v2 = create_receipt_processor()