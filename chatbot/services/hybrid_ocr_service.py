"""
Hybrid OCR Backend implementing Phase 2.2 of the receipt pipeline improvement plan.
Combines multiple OCR engines with confidence scoring and automatic fallback.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod
import time
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    """Result from OCR processing."""
    text: str
    confidence: float
    method: str
    processing_time: float
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class OCRBackend(ABC):
    """Abstract base class for OCR backends."""
    
    @abstractmethod
    async def extract_text(self, image_path: str) -> OCRResult:
        """Extract text from image."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if backend is available."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get backend name."""
        pass


class EasyOCRBackend(OCRBackend):
    """EasyOCR backend implementation."""
    
    def __init__(self):
        self._reader = None
        self._available = None
    
    @property
    def name(self) -> str:
        return "EasyOCR"
    
    def is_available(self) -> bool:
        """Check if EasyOCR is available."""
        if self._available is not None:
            return self._available
        
        try:
            import easyocr
            self._available = True
            logger.info("EasyOCR is available")
        except ImportError:
            self._available = False
            logger.warning("EasyOCR is not available")
        
        return self._available
    
    async def extract_text(self, image_path: str) -> OCRResult:
        """Extract text using EasyOCR."""
        if not self.is_available():
            raise RuntimeError("EasyOCR is not available")
        
        start_time = time.time()
        
        try:
            import easyocr
            
            # Initialize reader if not already done
            if self._reader is None:
                self._reader = easyocr.Reader(['en', 'pl'])  # English and Polish
            
            # Process image
            results = self._reader.readtext(image_path)
            
            # Extract text and calculate confidence
            text_parts = []
            confidences = []
            
            for (bbox, text, confidence) in results:
                if confidence > 0.3:  # Filter low-confidence results
                    text_parts.append(text)
                    confidences.append(confidence)
            
            final_text = '\n'.join(text_parts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            processing_time = time.time() - start_time
            
            logger.debug(f"EasyOCR processed image in {processing_time:.2f}s with confidence {avg_confidence:.2f}")
            
            return OCRResult(
                text=final_text,
                confidence=avg_confidence,
                method="EasyOCR",
                processing_time=processing_time,
                metadata={
                    'raw_results': results,
                    'num_detections': len(results),
                    'filtered_detections': len(text_parts)
                }
            )
            
        except Exception as e:
            logger.error(f"EasyOCR processing failed: {e}")
            raise


class TesseractBackend(OCRBackend):
    """Tesseract OCR backend implementation."""
    
    def __init__(self):
        self._available = None
    
    @property
    def name(self) -> str:
        return "Tesseract"
    
    def is_available(self) -> bool:
        """Check if Tesseract is available."""
        if self._available is not None:
            return self._available
        
        try:
            import pytesseract
            # Test if tesseract is installed
            pytesseract.get_tesseract_version()
            self._available = True
            logger.info("Tesseract is available")
        except Exception:
            self._available = False
            logger.warning("Tesseract is not available")
        
        return self._available
    
    async def extract_text(self, image_path: str) -> OCRResult:
        """Extract text using Tesseract."""
        if not self.is_available():
            raise RuntimeError("Tesseract is not available")
        
        start_time = time.time()
        
        try:
            import pytesseract
            from PIL import Image
            
            # Load image
            image = Image.open(image_path)
            
            # Configure Tesseract for receipt processing
            config = '--psm 6 -l eng+pol'  # Page segmentation mode 6, English and Polish
            
            # Extract text
            text = pytesseract.image_to_string(image, config=config)
            
            # Get confidence data
            data = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DICT)
            confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) / 100 if confidences else 0.0
            
            processing_time = time.time() - start_time
            
            logger.debug(f"Tesseract processed image in {processing_time:.2f}s with confidence {avg_confidence:.2f}")
            
            return OCRResult(
                text=text.strip(),
                confidence=avg_confidence,
                method="Tesseract",
                processing_time=processing_time,
                metadata={
                    'num_words': len([w for w in data['text'] if w.strip()]),
                    'avg_word_confidence': avg_confidence * 100
                }
            )
            
        except Exception as e:
            logger.error(f"Tesseract processing failed: {e}")
            raise


class PaddleOCRBackend(OCRBackend):
    """PaddleOCR backend implementation."""
    
    def __init__(self):
        self._ocr = None
        self._available = None
    
    @property
    def name(self) -> str:
        return "PaddleOCR"
    
    def is_available(self) -> bool:
        """Check if PaddleOCR is available."""
        if self._available is not None:
            return self._available
        
        try:
            from paddleocr import PaddleOCR
            self._available = True
            logger.info("PaddleOCR is available")
        except ImportError:
            self._available = False
            logger.warning("PaddleOCR is not available")
        
        return self._available
    
    async def extract_text(self, image_path: str) -> OCRResult:
        """Extract text using PaddleOCR."""
        if not self.is_available():
            raise RuntimeError("PaddleOCR is not available")
        
        start_time = time.time()
        
        try:
            from paddleocr import PaddleOCR
            
            # Initialize PaddleOCR if not already done
            if self._ocr is None:
                self._ocr = PaddleOCR(use_angle_cls=True, lang='en')
            
            # Process image
            results = self._ocr.ocr(image_path, cls=True)
            
            # Extract text and calculate confidence
            text_parts = []
            confidences = []
            
            for line in results[0] if results and results[0] else []:
                if len(line) >= 2:
                    text_info = line[1]
                    if len(text_info) >= 2:
                        text, confidence = text_info[0], text_info[1]
                        if confidence > 0.3:  # Filter low-confidence results
                            text_parts.append(text)
                            confidences.append(confidence)
            
            final_text = '\n'.join(text_parts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            processing_time = time.time() - start_time
            
            logger.debug(f"PaddleOCR processed image in {processing_time:.2f}s with confidence {avg_confidence:.2f}")
            
            return OCRResult(
                text=final_text,
                confidence=avg_confidence,
                method="PaddleOCR",
                processing_time=processing_time,
                metadata={
                    'num_lines': len(results[0]) if results and results[0] else 0,
                    'filtered_lines': len(text_parts)
                }
            )
            
        except Exception as e:
            logger.error(f"PaddleOCR processing failed: {e}")
            raise


class HybridOCRService:
    """
    Hybrid OCR service that combines multiple OCR backends.
    Implements intelligent backend selection and fallback mechanisms.
    """
    
    def __init__(self, 
                 confidence_threshold: float = 0.7,
                 max_backends: int = 2,
                 timeout: float = 30.0):
        """
        Initialize hybrid OCR service.
        
        Args:
            confidence_threshold: Minimum confidence to accept result
            max_backends: Maximum number of backends to try
            timeout: Timeout for each backend in seconds
        """
        self.confidence_threshold = confidence_threshold
        self.max_backends = max_backends
        self.timeout = timeout
        
        # Initialize backends
        self.backends = [
            EasyOCRBackend(),
            TesseractBackend(),
            PaddleOCRBackend()
        ]
        
        # Filter available backends
        self.available_backends = [b for b in self.backends if b.is_available()]
        
        if not self.available_backends:
            logger.warning("No OCR backends are available!")
        else:
            backend_names = [b.name for b in self.available_backends]
            logger.info(f"Available OCR backends: {backend_names}")
    
    async def extract_text_from_file(self, image_path: str) -> str:
        """
        Extract text from image file using the best available method.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Extracted text
        """
        if not self.available_backends:
            raise RuntimeError("No OCR backends are available")
        
        # Preprocess image first
        from .image_processor import get_image_processor
        
        processor = get_image_processor()
        processing_result = processor.preprocess_image(image_path)
        
        # Use processed image if available, otherwise use original
        ocr_image_path = processing_result.processed_path if processing_result.success else image_path
        
        # Try multiple backends
        results = []
        backends_tried = 0
        
        for backend in self.available_backends:
            if backends_tried >= self.max_backends:
                break
            
            try:
                logger.info(f"Trying OCR with {backend.name}")
                
                # Run OCR with timeout
                result = await asyncio.wait_for(
                    backend.extract_text(ocr_image_path),
                    timeout=self.timeout
                )
                
                results.append(result)
                backends_tried += 1
                
                # If we get high confidence result, we can stop
                if result.confidence >= self.confidence_threshold:
                    logger.info(f"High confidence result from {backend.name}: {result.confidence:.2f}")
                    break
                    
            except Exception as e:
                logger.warning(f"OCR backend {backend.name} failed: {e}")
                continue
        
        if not results:
            raise RuntimeError("All OCR backends failed")
        
        # Select best result
        best_result = self._select_best_result(results)
        
        logger.info(f"Selected result from {best_result.method} with confidence {best_result.confidence:.2f}")
        
        return best_result.text
    
    def _select_best_result(self, results: List[OCRResult]) -> OCRResult:
        """
        Select the best OCR result from multiple backends.
        
        Args:
            results: List of OCR results
            
        Returns:
            Best OCR result
        """
        if not results:
            raise ValueError("No results to select from")
        
        if len(results) == 1:
            return results[0]
        
        # Score results based on multiple factors
        scored_results = []
        
        for result in results:
            score = 0.0
            
            # Primary factor: confidence
            score += result.confidence * 0.6
            
            # Secondary factor: text length (longer is often better for receipts)
            text_length_factor = min(len(result.text) / 1000, 1.0)  # Normalize to 0-1
            score += text_length_factor * 0.2
            
            # Tertiary factor: processing speed (faster is better)
            speed_factor = max(0, 1.0 - (result.processing_time / 30.0))  # Normalize to 0-1
            score += speed_factor * 0.1
            
            # Bonus for specific backends known to work well with receipts
            if result.method == "EasyOCR":
                score += 0.05
            elif result.method == "PaddleOCR":
                score += 0.03
            
            # Penalty for very short text (likely poor OCR)
            if len(result.text.strip()) < 50:
                score -= 0.2
            
            scored_results.append((score, result))
        
        # Return result with highest score
        best_score, best_result = max(scored_results, key=lambda x: x[0])
        
        logger.debug(f"Best result score: {best_score:.3f} from {best_result.method}")
        
        return best_result
    
    async def get_confidence_scores(self, image_path: str) -> Dict[str, float]:
        """
        Get confidence scores from all available backends.
        Useful for diagnostics and quality assessment.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Dictionary mapping backend names to confidence scores
        """
        scores = {}
        
        for backend in self.available_backends:
            try:
                result = await asyncio.wait_for(
                    backend.extract_text(image_path),
                    timeout=self.timeout
                )
                scores[backend.name] = result.confidence
            except Exception as e:
                logger.warning(f"Could not get confidence from {backend.name}: {e}")
                scores[backend.name] = 0.0
        
        return scores
    
    def get_backend_status(self) -> Dict[str, bool]:
        """Get status of all OCR backends."""
        return {backend.name: backend.is_available() for backend in self.backends}


# Factory function for dependency injection
def get_hybrid_ocr_service() -> HybridOCRService:
    """Get hybrid OCR service instance."""
    return HybridOCRService()