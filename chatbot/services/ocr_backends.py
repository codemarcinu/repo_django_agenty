"""
OCR backends with fallback system.
Abstract interface for different OCR implementations.
"""

import logging
import os
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    """Result from OCR processing."""

    text: str
    confidence: float
    backend: str
    processing_time: float
    metadata: dict[str, Any]
    success: bool = True
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        import json
        
        def make_json_serializable(obj):
            """Convert numpy types and other non-serializable objects to JSON serializable types."""
            if hasattr(obj, 'item'):  # numpy scalars
                return obj.item()
            elif hasattr(obj, 'tolist'):  # numpy arrays
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: make_json_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [make_json_serializable(v) for v in obj]
            else:
                return obj
        
        return {
            "text": self.text,
            "confidence": float(self.confidence),
            "backend": self.backend,
            "processing_time": float(self.processing_time),
            "metadata": make_json_serializable(self.metadata),
            "success": bool(self.success),
            "error_message": self.error_message,
        }


class OCRBackend(ABC):
    """Abstract base class for OCR backends."""

    def __init__(self, name: str):
        self.name = name
        self.is_available = self._check_availability()

    @abstractmethod
    def _check_availability(self) -> bool:
        """Check if this OCR backend is available."""
        pass

    @abstractmethod
    def extract_text_from_image(self, image_path: str) -> OCRResult:
        """Extract text from image file."""
        pass

    @abstractmethod
    def extract_text_from_pdf(self, pdf_path: str) -> OCRResult:
        """Extract text from PDF file."""
        pass

    def process_file(self, file_path: str) -> OCRResult:
        """Process file based on its extension."""
        import time

        start_time = time.time()

        try:
            file_ext = Path(file_path).suffix.lower()

            if file_ext == ".pdf":
                result = self.extract_text_from_pdf(file_path)
            elif file_ext in [".jpg", ".jpeg", ".png"]:
                result = self.extract_text_from_image(file_path)
            else:
                return OCRResult(
                    text="",
                    confidence=0.0,
                    backend=self.name,
                    processing_time=time.time() - start_time,
                    metadata={"error": f"Unsupported file type: {file_ext}"},
                    success=False,
                    error_message=f"Unsupported file type: {file_ext}",
                )

            result.processing_time = time.time() - start_time
            return result

        except Exception as e:
            logger.error(f"Error processing file with {self.name}: {str(e)}")
            return OCRResult(
                text="",
                confidence=0.0,
                backend=self.name,
                processing_time=time.time() - start_time,
                metadata={"error": str(e)},
                success=False,
                error_message=str(e),
            )


class EasyOCRBackend(OCRBackend):
    """EasyOCR implementation."""

    def __init__(self, languages: list[str] = None):
        self.languages = languages or ["pl", "en"]
        self._reader = None
        super().__init__("easyocr")

    def _check_availability(self) -> bool:
        """Check if EasyOCR is available."""
        try:
            import easyocr

            return True
        except ImportError:
            logger.warning("EasyOCR not available. Install with: pip install easyocr")
            return False

    def _get_reader(self):
        """Lazy load EasyOCR reader."""
        if self._reader is None and self.is_available:
            try:
                import easyocr

                self._reader = easyocr.Reader(self.languages, gpu=False)
            except Exception as e:
                logger.error(f"Failed to initialize EasyOCR: {str(e)}")
                self.is_available = False
        return self._reader

    def extract_text_from_image(self, image_path: str) -> OCRResult:
        """Extract text from image using EasyOCR."""
        reader = self._get_reader()
        if not reader:
            return OCRResult(
                text="",
                confidence=0.0,
                backend=self.name,
                processing_time=0.0,
                metadata={"error": "EasyOCR not available"},
                success=False,
                error_message="EasyOCR not available",
            )

        try:
            results = reader.readtext(image_path)

            # Combine all detected text
            text_parts = []
            total_confidence = 0.0

            for bbox, text, confidence in results:
                text_parts.append(text)
                total_confidence += confidence

            combined_text = "\n".join(text_parts)
            avg_confidence = total_confidence / len(results) if results else 0.0

            return OCRResult(
                text=combined_text,
                confidence=avg_confidence,
                backend=self.name,
                processing_time=0.0,  # Will be set by parent
                metadata={
                    "num_detections": len(results),
                    "languages": self.languages,
                    "raw_results": results,
                },
                success=True,
            )

        except Exception as e:
            return OCRResult(
                text="",
                confidence=0.0,
                backend=self.name,
                processing_time=0.0,
                metadata={"error": str(e)},
                success=False,
                error_message=str(e),
            )

    def extract_text_from_pdf(self, pdf_path: str) -> OCRResult:
        """Extract text from PDF by converting to images first."""
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(pdf_path)
            all_text = []
            total_confidence = 0.0
            page_count = 0

            for page_num in range(len(doc)):
                page = doc.load_page(page_num)

                # First try to extract text directly
                text = page.get_text()
                if text.strip():
                    all_text.append(text)
                    total_confidence += (
                        0.95  # High confidence for direct text extraction
                    )
                    page_count += 1
                else:
                    # Convert page to image and use OCR
                    pix = page.get_pixmap()

                    # Save as temporary image
                    with tempfile.NamedTemporaryFile(
                        suffix=".png", delete=False
                    ) as temp_img:
                        pix.save(temp_img.name)
                        temp_img_path = temp_img.name

                    try:
                        ocr_result = self.extract_text_from_image(temp_img_path)
                        if ocr_result.success and ocr_result.text.strip():
                            all_text.append(ocr_result.text)
                            total_confidence += ocr_result.confidence
                            page_count += 1
                    finally:
                        os.unlink(temp_img_path)

            combined_text = "\n\n".join(all_text)
            avg_confidence = total_confidence / page_count if page_count > 0 else 0.0

            total_pages = len(doc) if hasattr(doc, '__len__') else 0
            doc.close()

            return OCRResult(
                text=combined_text,
                confidence=avg_confidence,
                backend=self.name,
                processing_time=0.0,  # Will be set by parent
                metadata={
                    "pages_processed": page_count,
                    "total_pages": total_pages,
                    "languages": self.languages,
                },
                success=True,
            )

        except Exception as e:
            return OCRResult(
                text="",
                confidence=0.0,
                backend=self.name,
                processing_time=0.0,
                metadata={"error": str(e)},
                success=False,
                error_message=str(e),
            )


class TesseractBackend(OCRBackend):
    """Tesseract OCR implementation."""

    def __init__(self, language: str = "pol+eng"):
        self.language = language
        super().__init__("tesseract")

    def _check_availability(self) -> bool:
        """Check if Tesseract is available."""
        try:
            import pytesseract

            # Test if tesseract binary is available
            pytesseract.get_tesseract_version()
            return True
        except ImportError:
            logger.warning(
                "pytesseract not available. Install with: pip install pytesseract"
            )
            return False
        except Exception:
            logger.warning(
                "Tesseract not available. Install with: apt-get install tesseract-ocr"
            )
            return False

    def extract_text_from_image(self, image_path: str) -> OCRResult:
        """Extract text from image using Tesseract."""
        if not self.is_available:
            return OCRResult(
                text="",
                confidence=0.0,
                backend=self.name,
                processing_time=0.0,
                metadata={"error": "Tesseract not available"},
                success=False,
                error_message="Tesseract not available",
            )

        try:
            import pytesseract
            from PIL import Image

            # Open image
            image = Image.open(image_path)

            # Extract text with confidence data
            data = pytesseract.image_to_data(
                image, lang=self.language, output_type=pytesseract.Output.DICT
            )

            # Filter out low-confidence detections and combine text
            text_parts = []
            confidences = []

            for i, conf in enumerate(data["conf"]):
                if int(conf) > 0:  # Only include text with some confidence
                    text = data["text"][i].strip()
                    if text:
                        text_parts.append(text)
                        confidences.append(int(conf))

            combined_text = " ".join(text_parts)
            avg_confidence = (
                sum(confidences) / len(confidences) / 100.0 if confidences else 0.0
            )

            return OCRResult(
                text=combined_text,
                confidence=avg_confidence,
                backend=self.name,
                processing_time=0.0,  # Will be set by parent
                metadata={
                    "language": self.language,
                    "num_words": len(text_parts),
                    "avg_word_confidence": avg_confidence * 100,
                },
                success=True,
            )

        except Exception as e:
            return OCRResult(
                text="",
                confidence=0.0,
                backend=self.name,
                processing_time=0.0,
                metadata={"error": str(e)},
                success=False,
                error_message=str(e),
            )

    def extract_text_from_pdf(self, pdf_path: str) -> OCRResult:
        """Extract text from PDF by converting to images first."""
        try:
            import io

            import fitz  # PyMuPDF
            import pytesseract
            from PIL import Image

            doc = fitz.open(pdf_path)
            all_text = []
            total_confidence = 0.0
            page_count = 0

            for page_num in range(len(doc)):
                page = doc.load_page(page_num)

                # First try to extract text directly
                text = page.get_text()
                if text.strip():
                    all_text.append(text)
                    total_confidence += (
                        0.95  # High confidence for direct text extraction
                    )
                    page_count += 1
                else:
                    # Convert page to image and use OCR
                    pix = page.get_pixmap()

                    # Convert to PIL Image
                    img_data = pix.tobytes("ppm")
                    img = Image.open(io.BytesIO(img_data))

                    # Extract text with Tesseract
                    data = pytesseract.image_to_data(
                        img, lang=self.language, output_type=pytesseract.Output.DICT
                    )

                    # Process results
                    text_parts = []
                    confidences = []

                    for i, conf in enumerate(data["conf"]):
                        if int(conf) > 0:
                            text = data["text"][i].strip()
                            if text:
                                text_parts.append(text)
                                confidences.append(int(conf))

                    if text_parts:
                        page_text = " ".join(text_parts)
                        page_confidence = sum(confidences) / len(confidences) / 100.0
                        all_text.append(page_text)
                        total_confidence += page_confidence
                        page_count += 1

            combined_text = "\n\n".join(all_text)
            avg_confidence = total_confidence / page_count if page_count > 0 else 0.0

            total_pages = len(doc) if hasattr(doc, '__len__') else 0
            doc.close()

            return OCRResult(
                text=combined_text,
                confidence=avg_confidence,
                backend=self.name,
                processing_time=0.0,  # Will be set by parent
                metadata={
                    "pages_processed": page_count,
                    "total_pages": total_pages,
                    "language": self.language,
                },
                success=True,
            )

        except Exception as e:
            return OCRResult(
                text="",
                confidence=0.0,
                backend=self.name,
                processing_time=0.0,
                metadata={"error": str(e)},
                success=False,
                error_message=str(e),
            )


class FallbackOCRBackend(OCRBackend):
    """Fallback OCR that tries multiple backends."""

    def __init__(self, backends: list[OCRBackend]):
        self.backends = [b for b in backends if b.is_available]
        super().__init__("fallback")

    def _check_availability(self) -> bool:
        """Fallback is available if at least one backend is available."""
        return len(self.backends) > 0

    def extract_text_from_image(self, image_path: str) -> OCRResult:
        """Try multiple backends until one succeeds."""
        return self._try_backends("extract_text_from_image", image_path)

    def extract_text_from_pdf(self, pdf_path: str) -> OCRResult:
        """Try multiple backends until one succeeds."""
        return self._try_backends("extract_text_from_pdf", pdf_path)

    def _try_backends(self, method_name: str, file_path: str) -> OCRResult:
        """Try multiple backends in order until one succeeds."""
        last_error = None
        attempted_backends = []

        for backend in self.backends:
            try:
                method = getattr(backend, method_name)
                result = method(file_path)

                if result.success and result.text.strip():
                    # Success! Update metadata to show it was from fallback
                    result.metadata["fallback_used"] = True
                    result.metadata["attempted_backends"] = attempted_backends + [
                        backend.name
                    ]
                    result.metadata["successful_backend"] = backend.name
                    result.backend = f"{self.name}({backend.name})"
                    return result
                else:
                    attempted_backends.append(backend.name)
                    if result.error_message:
                        last_error = result.error_message

            except Exception as e:
                attempted_backends.append(backend.name)
                last_error = str(e)
                logger.warning(f"Backend {backend.name} failed: {str(e)}")

        
        last_error = None
        attempted_backends = []

        for backend in self.backends:
            try:
                method = getattr(backend, method_name)
                result = method(file_path)

                if result.success and result.text.strip():
                    # Success! Update metadata to show it was from fallback
                    result.metadata["fallback_used"] = True
                    result.metadata["attempted_backends"] = attempted_backends + [
                        backend.name
                    ]
                    result.metadata["successful_backend"] = backend.name
                    result.backend = f"{self.name}({backend.name})"
                    return result
                else:
                    attempted_backends.append(backend.name)
                    if result.error_message:
                        last_error = result.error_message

            except Exception as e:
                attempted_backends.append(backend.name)
                last_error = str(e)
                logger.warning(f"Backend {backend.name} failed: {str(e)}")

        # All backends failed
        return OCRResult(
            text="",
            confidence=0.0,
            backend=self.name,
            processing_time=0.0,
            metadata={
                "attempted_backends": attempted_backends,
                "all_failed": True,
                "last_error": last_error,
            },
            success=False,
            error_message=f"All OCR backends failed. Last error: {last_error}",
        )


class GoogleVisionBackend(OCRBackend):
    """Google Cloud Vision API OCR implementation."""

    def __init__(self):
        super().__init__("google_vision")

    def _check_availability(self) -> bool:
        """Check if Google Cloud Vision API client is available."""
        try:
            from google.cloud import vision
            # Check if GOOGLE_APPLICATION_CREDENTIALS is set or other auth is configured
            # A simple client creation will raise an exception if credentials are not found
            vision.ImageAnnotatorClient()
            return True
        except ImportError:
            logger.warning("Google Cloud Vision client not available. Install with: pip install google-cloud-vision")
            return False
        except Exception as e:
            logger.warning(f"Google Cloud Vision API not configured or accessible: {e}")
            return False

    def extract_text_from_image(self, image_path: str) -> OCRResult:
        """Extract text from image using Google Cloud Vision API."""
        if not self.is_available:
            return OCRResult(
                text="",
                confidence=0.0,
                backend=self.name,
                processing_time=0.0,
                metadata={"error": "Google Vision API not available"},
                success=False,
                error_message="Google Vision API not available",
            )

        import time
        from google.cloud import vision
        from google.cloud.vision_v1 import types

        start_time = time.time()
        client = vision.ImageAnnotatorClient()

        try:
            with open(image_path, "rb") as image_file:
                content = image_file.read()
            image = types.Image(content=content)

            response = client.document_text_detection(image=image)
            full_text_annotation = response.full_text_annotation

            text = full_text_annotation.text
            # Google Vision API provides confidence at word/symbol level, not overall document.
            # We can approximate by averaging block confidences or use 1.0 if text is found.
            # For simplicity, if text is extracted, we'll assign a high confidence.
            confidence = 1.0 if text else 0.0

            processing_time = time.time() - start_time

            return OCRResult(
                text=text,
                confidence=confidence,
                backend=self.name,
                processing_time=processing_time,
                metadata={
                    "pages": len(full_text_annotation.pages),
                    "blocks": sum(len(page.blocks) for page in full_text_annotation.pages),
                    "raw_response": response.to_dict(), # Store full response for debugging
                },
                success=True,
            )
        except Exception as e:
            logger.error(f"Google Vision API image processing failed: {e}", exc_info=True)
            return OCRResult(
                text="",
                confidence=0.0,
                backend=self.name,
                processing_time=time.time() - start_time,
                metadata={"error": str(e)},
                success=False,
                error_message=str(e),
            )

    def extract_text_from_pdf(self, pdf_path: str) -> OCRResult:
        """Extract text from PDF using Google Cloud Vision API (async batch processing)."""
        if not self.is_available:
            return OCRResult(
                text="",
                confidence=0.0,
                backend=self.name,
                processing_time=0.0,
                metadata={"error": "Google Vision API not available"},
                success=False,
                error_message="Google Vision API not available",
            )

        import time
        from google.cloud import vision
        from google.cloud.vision_v1 import types
        from google.cloud import storage # Required for GCS operations

        start_time = time.time()
        client = vision.ImageAnnotatorClient()

        # Google Vision API requires PDF to be in Google Cloud Storage
        # This is a simplified example. In a real scenario, you'd upload the PDF
        # to GCS first, then process it. For local files, this is a placeholder.
        # For now, we'll return an error as direct local PDF processing is not supported.
        error_message = "Google Vision API requires PDF files to be in Google Cloud Storage for batch processing. Direct local PDF processing is not supported."
        logger.error(error_message)
        return OCRResult(
            text="",
            confidence=0.0,
            backend=self.name,
            processing_time=time.time() - start_time,
            metadata={"error": error_message},
            success=False,
            error_message=error_message,
        )
