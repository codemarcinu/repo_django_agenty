"""
PaddleOCR service for text extraction from receipt images.
Optimized for Polish receipts with GPU acceleration.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    """OCR extraction result with confidence score"""
    text: str
    confidence: float
    bbox: list[float] | None = None  # Bounding box coordinates [x1, y1, x2, y2]


class PaddleOCRService:
    """
    Service for text extraction using PaddleOCR.
    Provides hybrid OCR + confidence-based filtering.
    """

    def __init__(self):
        self.ocr_engine = None
        self.is_available = False
        self.use_gpu = True
        self.confidence_threshold = 0.6
        self.languages = ['pl', 'en']  # Polish + English

        self._initialize_ocr()

    def _initialize_ocr(self) -> None:
        """Initialize PaddleOCR engine with error handling"""
        try:
            from paddleocr import PaddleOCR

            # Check GPU availability
            try:
                import paddle
                if paddle.device.cuda.device_count() > 0:
                    self.use_gpu = True
                    logger.info("✅ CUDA detected, using GPU for PaddleOCR")
                else:
                    self.use_gpu = False
                    logger.warning("⚠️ No CUDA detected, using CPU for PaddleOCR")
            except Exception as e:
                self.use_gpu = False
                logger.warning(f"GPU detection failed, using CPU: {e}")

            # Initialize OCR (use_gpu argument removed in newer versions)
            ocr_params = {
                'use_angle_cls': True,  # Enable text angle detection
                'lang': 'pl',  # Primary language: Polish
                'show_log': False,  # Reduce noise in logs
                'det_limit_side_len': 1280,  # Detection resolution limit
                'rec_batch_num': 6,  # Recognition batch size
            }

            # Add GPU parameter only if supported
            try:
                self.ocr_engine = PaddleOCR(**ocr_params, use_gpu=self.use_gpu)
            except Exception:
                # Fallback without use_gpu parameter
                logger.info("Initializing PaddleOCR without use_gpu parameter")
                self.ocr_engine = PaddleOCR(**ocr_params)

            self.is_available = True
            logger.info(f"✅ PaddleOCR initialized successfully (GPU: {self.use_gpu})")

        except ImportError:
            logger.error("❌ PaddleOCR not installed. Install with: pip install paddlepaddle-gpu paddleocr")
            self.is_available = False
        except Exception as e:
            logger.error(f"❌ Failed to initialize PaddleOCR: {e}")
            self.is_available = False

    def is_service_available(self) -> bool:
        """Check if PaddleOCR service is available"""
        return self.is_available and self.ocr_engine is not None

    def extract_text_from_image(self, image_path: str) -> list[OCRResult]:
        """
        Extract text from image using PaddleOCR.
        
        Args:
            image_path: Path to image file
            
        Returns:
            List of OCRResult objects with text, confidence, and bounding box
        """
        if not self.is_service_available():
            logger.error("PaddleOCR service not available")
            return []

        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return []

        try:
            logger.info(f"🔍 Starting OCR extraction for: {image_path}")

            # Perform OCR
            results = self.ocr_engine.ocr(image_path, cls=True)

            if not results or not results[0]:
                logger.warning("No text detected in image")
                return []

            # Parse results
            ocr_results = []
            for line in results[0]:  # results[0] is the first page
                if len(line) >= 2:
                    bbox = line[0]  # Bounding box coordinates
                    text_info = line[1]  # (text, confidence)

                    if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                        text = text_info[0]
                        confidence = float(text_info[1])

                        # Filter by confidence threshold
                        if confidence >= self.confidence_threshold:
                            # Convert bbox to flat coordinates if needed
                            flat_bbox = None
                            if bbox and len(bbox) >= 4:
                                flat_bbox = [
                                    min(point[0] for point in bbox),  # x1
                                    min(point[1] for point in bbox),  # y1
                                    max(point[0] for point in bbox),  # x2
                                    max(point[1] for point in bbox),  # y2
                                ]

                            ocr_results.append(OCRResult(
                                text=text.strip(),
                                confidence=confidence,
                                bbox=flat_bbox
                            ))
                        else:
                            logger.debug(f"Filtered low confidence text: '{text}' (conf: {confidence:.2f})")

            logger.info(f"✅ OCR extracted {len(ocr_results)} text segments with confidence >= {self.confidence_threshold}")
            return ocr_results

        except Exception as e:
            logger.error(f"❌ OCR extraction failed: {e}", exc_info=True)
            return []

    def extract_text_simple(self, image_path: str) -> str:
        """
        Extract text as simple string (for backward compatibility).
        
        Args:
            image_path: Path to image file
            
        Returns:
            Extracted text as single string
        """
        ocr_results = self.extract_text_from_image(image_path)

        if not ocr_results:
            return ""

        # Sort by y-coordinate (top to bottom) then x-coordinate (left to right)
        sorted_results = sorted(ocr_results, key=lambda r: (
            r.bbox[1] if r.bbox else 0,  # y1
            r.bbox[0] if r.bbox else 0   # x1
        ))

        # Join texts with spaces
        full_text = " ".join(result.text for result in sorted_results)

        logger.info(f"✅ OCR full text extracted: {len(full_text)} characters")
        return full_text

    def get_high_confidence_lines(self, image_path: str, min_confidence: float = 0.8) -> list[str]:
        """
        Get only high-confidence text lines.
        
        Args:
            image_path: Path to image file
            min_confidence: Minimum confidence threshold
            
        Returns:
            List of high-confidence text lines
        """
        ocr_results = self.extract_text_from_image(image_path)

        high_conf_lines = [
            result.text for result in ocr_results
            if result.confidence >= min_confidence
        ]

        logger.info(f"✅ Found {len(high_conf_lines)} high-confidence lines (>= {min_confidence})")
        return high_conf_lines

    def analyze_receipt_structure(self, image_path: str) -> dict[str, Any]:
        """
        Analyze receipt structure and extract key information.
        
        Args:
            image_path: Path to receipt image
            
        Returns:
            Dictionary with receipt analysis
        """
        ocr_results = self.extract_text_from_image(image_path)

        if not ocr_results:
            return {"status": "failed", "reason": "no_text_detected"}

        # Analyze content
        all_text = " ".join(result.text for result in ocr_results)
        high_conf_text = " ".join(
            result.text for result in ocr_results
            if result.confidence >= 0.8
        )

        # Basic receipt patterns
        import re

        # Look for prices (Polish format: 12,34 PLN or 12.34 zł)
        price_patterns = [
            r'\d+[.,]\d{2}\s*(?:PLN|zł|ZŁ)',
            r'\d+[.,]\d{2}',
        ]

        prices_found = []
        for pattern in price_patterns:
            prices_found.extend(re.findall(pattern, all_text))

        # Look for dates
        date_patterns = [
            r'\d{2}[.-]\d{2}[.-]\d{4}',
            r'\d{4}[.-]\d{2}[.-]\d{2}',
        ]

        dates_found = []
        for pattern in date_patterns:
            dates_found.extend(re.findall(pattern, all_text))

        analysis = {
            "status": "success",
            "total_lines": len(ocr_results),
            "avg_confidence": sum(r.confidence for r in ocr_results) / len(ocr_results),
            "high_confidence_lines": len([r for r in ocr_results if r.confidence >= 0.8]),
            "text_length": len(all_text),
            "prices_detected": len(prices_found),
            "dates_detected": len(dates_found),
            "sample_prices": prices_found[:5],  # First 5 prices
            "sample_dates": dates_found[:3],    # First 3 dates
            "confidence_distribution": {
                "high": len([r for r in ocr_results if r.confidence >= 0.8]),
                "medium": len([r for r in ocr_results if 0.6 <= r.confidence < 0.8]),
                "low": len([r for r in ocr_results if r.confidence < 0.6]),
            }
        }

        logger.info(f"✅ Receipt analysis completed: {analysis['total_lines']} lines, "
                   f"avg confidence: {analysis['avg_confidence']:.2f}")

        return analysis

    def get_service_info(self) -> dict[str, Any]:
        """Get service configuration and status"""
        return {
            "service": "PaddleOCR",
            "available": self.is_available,
            "gpu_enabled": self.use_gpu,
            "languages": self.languages,
            "confidence_threshold": self.confidence_threshold,
            "version_info": self._get_version_info()
        }

    def _get_version_info(self) -> dict[str, str]:
        """Get version information for installed packages"""
        version_info = {}

        try:
            import paddleocr
            version_info["paddleocr"] = getattr(paddleocr, "__version__", "unknown")
        except ImportError:
            version_info["paddleocr"] = "not_installed"

        try:
            import paddle
            version_info["paddlepaddle"] = paddle.__version__
        except ImportError:
            version_info["paddlepaddle"] = "not_installed"

        return version_info


# Global service instance
paddleocr_service = PaddleOCRService()
