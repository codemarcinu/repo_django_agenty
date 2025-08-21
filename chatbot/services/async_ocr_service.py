"""
Async OCR service with proper resource management and caching.
"""

import asyncio
import logging
import os
import tempfile
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import easyocr
import fitz  # PyMuPDF
from django.conf import settings

from .cache_service import cache_service
from .exceptions_receipt import FileValidationError, OCRError

logger = logging.getLogger(__name__)


class AsyncOCRService:
    """Async OCR service with resource management and caching."""

    def __init__(self):
        self._reader = None
        self.gpu_enabled = getattr(settings, 'OCR_GPU_ENABLED', True)
        self.languages = getattr(settings, 'OCR_LANGUAGES', ['pl', 'en'])
        self.max_file_size = getattr(settings, 'MAX_RECEIPT_FILE_SIZE', 10 * 1024 * 1024)  # 10MB

    async def _get_reader(self) -> easyocr.Reader:
        """Get EasyOCR reader instance, initializing if needed."""
        if self._reader is None:
            logger.info("Initializing EasyOCR reader...")
            loop = asyncio.get_event_loop()
            try:
                self._reader = await loop.run_in_executor(
                    None,
                    lambda: easyocr.Reader(self.languages, gpu=self.gpu_enabled)
                )
                logger.info("EasyOCR reader initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize EasyOCR reader: {e}")
                raise OCRError(f"Failed to initialize OCR reader: {str(e)}")

        return self._reader

    def _validate_file(self, file_path: str) -> None:
        """Validate file existence and size."""
        if not os.path.exists(file_path):
            raise FileValidationError(f"File does not exist: {file_path}", file_path=file_path)

        file_size = os.path.getsize(file_path)
        if file_size > self.max_file_size:
            raise FileValidationError(
                f"File size {file_size} exceeds maximum allowed size {self.max_file_size}",
                file_path=file_path,
                details={"file_size": file_size, "max_size": self.max_file_size}
            )

        if file_size == 0:
            raise FileValidationError(f"File is empty: {file_path}", file_path=file_path)

    @asynccontextmanager
    async def _open_pdf_async(self, pdf_path: str) -> AsyncGenerator[fitz.Document, None]:
        """Async context manager for PDF documents."""
        doc = None
        try:
            loop = asyncio.get_event_loop()
            doc = await loop.run_in_executor(None, fitz.open, pdf_path)
            yield doc
        except Exception as e:
            logger.error(f"Failed to open PDF {pdf_path}: {e}")
            raise OCRError(f"Failed to open PDF: {str(e)}", file_path=pdf_path)
        finally:
            if doc:
                try:
                    await loop.run_in_executor(None, doc.close)
                except Exception as e:
                    logger.warning(f"Error closing PDF document: {e}")

    @asynccontextmanager
    async def _temp_file_async(self, suffix: str = ".png") -> AsyncGenerator[str, None]:
        """Async context manager for temporary files."""
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
                temp_path = temp_file.name
            yield temp_path
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    await asyncio.get_event_loop().run_in_executor(None, os.unlink, temp_path)
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file {temp_path}: {e}")

    async def _extract_text_from_image_async(self, image_path: str) -> str | None:
        """Extract text from image using EasyOCR with async execution."""
        logger.info(f"📷 Starting OCR text extraction from image: {image_path}")

        try:
            reader = await self._get_reader()
            loop = asyncio.get_event_loop()

            # Run OCR in executor to avoid blocking
            result = await loop.run_in_executor(None, reader.readtext, image_path)

            logger.info(f"EasyOCR detected {len(result)} text regions")

            # Log detected text regions for debugging
            for i, (bbox, text, prob) in enumerate(result):
                logger.debug(f"Region {i+1}: '{text}' (confidence: {prob:.2f})")

            # Concatenate all detected text
            extracted_text = " ".join([text for (bbox, text, prob) in result])

            logger.info(f"✅ OCR extraction completed. Total text length: {len(extracted_text)} characters")
            logger.debug(f"OCR extracted text preview: {extracted_text[:200]}...")

            return extracted_text if extracted_text.strip() else None

        except Exception as e:
            logger.error(f"❌ Error during OCR text extraction from {image_path}: {e}", exc_info=True)
            raise OCRError(f"OCR extraction failed: {str(e)}", file_path=image_path)

    async def _extract_text_from_pdf_async(self, pdf_path: str) -> str | None:
        """Extract text from PDF file using PyMuPDF with async execution."""
        logger.info(f"📄 Starting text extraction from PDF: {pdf_path}")

        try:
            text_parts = []

            async with self._open_pdf_async(pdf_path) as doc:
                loop = asyncio.get_event_loop()
                page_count = await loop.run_in_executor(None, len, doc)

                for page_num in range(page_count):
                    logger.debug(f"Processing PDF page {page_num + 1}/{page_count}")
                    page = await loop.run_in_executor(None, doc.__getitem__, page_num)

                    # Try to extract text directly
                    page_text = await loop.run_in_executor(None, page.get_text)

                    if page_text.strip():
                        text_parts.append(page_text)
                        logger.debug(f"Page {page_num + 1}: Extracted {len(page_text)} chars directly")
                    else:
                        # If no text, convert page to image and use OCR
                        logger.info(f"PDF page {page_num + 1} has no text, using OCR")

                        try:
                            # Create pixmap with 2x scale for better OCR
                            matrix = fitz.Matrix(2.0, 2.0)
                            pix = await loop.run_in_executor(None, page.get_pixmap, matrix)

                            async with self._temp_file_async(".png") as temp_path:
                                # Save pixmap to temp file
                                await loop.run_in_executor(None, pix.save, temp_path)

                                # Extract text using OCR
                                ocr_text = await self._extract_text_from_image_async(temp_path)
                                if ocr_text:
                                    text_parts.append(ocr_text)
                                    logger.debug(f"Page {page_num + 1}: OCR extracted {len(ocr_text)} chars")

                        except Exception as e:
                            logger.warning(f"OCR failed for PDF page {page_num + 1}: {e}")
                            continue

            full_text = "\n".join(text_parts)
            logger.info(f"✅ PDF text extraction completed. Total text length: {len(full_text)} characters")

            return full_text.strip() if full_text.strip() else None

        except Exception as e:
            logger.error(f"❌ Error during PDF text extraction from {pdf_path}: {e}", exc_info=True)
            raise OCRError(f"PDF text extraction failed: {str(e)}", file_path=pdf_path)

    async def extract_text_from_file(self, file_path: str) -> str | None:
        """Extract text from either image or PDF file with caching."""
        logger.info(f"🔍 Starting text extraction from file: {file_path}")

        # Validate file
        self._validate_file(file_path)

        # Check cache first
        try:
            cached_result = await cache_service.get_cached_ocr_result(file_path)
            if cached_result:
                logger.info(f"✅ Using cached OCR result for {file_path}")
                return cached_result
        except Exception as e:
            logger.warning(f"Cache retrieval failed for {file_path}: {e}")

        # Determine file type and extract text
        file_extension = os.path.splitext(file_path)[1].lower()

        try:
            if file_extension == ".pdf":
                extracted_text = await self._extract_text_from_pdf_async(file_path)
            else:
                extracted_text = await self._extract_text_from_image_async(file_path)

            # Cache the result if extraction was successful
            if extracted_text:
                try:
                    await cache_service.cache_ocr_result(file_path, extracted_text)
                except Exception as e:
                    logger.warning(f"Failed to cache OCR result for {file_path}: {e}")

            logger.info(f"✅ Text extraction completed for {file_path}")
            return extracted_text

        except OCRError:
            # Re-raise OCR errors as-is
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error during text extraction from {file_path}: {e}", exc_info=True)
            raise OCRError(f"Text extraction failed: {str(e)}", file_path=file_path)

    async def cleanup(self):
        """Cleanup resources."""
        # EasyOCR reader doesn't need explicit cleanup
        # But we can clear the reference
        self._reader = None
        logger.debug("OCR service cleaned up")


# Global async OCR service instance
async_ocr_service = AsyncOCRService()
