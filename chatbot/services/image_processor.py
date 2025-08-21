"""
Receipt Image Processor for intelligent preprocessing of receipt images.
Implements Phase 2.1 of the receipt pipeline improvement plan.
"""

import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageEnhance

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of image processing operation."""
    success: bool
    processed_path: str | None = None
    original_path: str | None = None
    operations_applied: list[str] = None
    confidence: float = 0.0
    message: str = ""

    def __post_init__(self):
        if self.operations_applied is None:
            self.operations_applied = []


class ReceiptImageProcessor:
    """
    Intelligent image processor for receipt images.
    Implements automatic cropping, perspective correction, and enhancement.
    """

    def __init__(self,
                 target_width: int = 800,
                 target_height: int = 1200,
                 enable_debug: bool = False):
        """
        Initialize the image processor.
        
        Args:
            target_width: Target width for resized images
            target_height: Target height for resized images  
            enable_debug: Whether to save debug images
        """
        self.target_width = target_width
        self.target_height = target_height
        self.enable_debug = enable_debug

        # Processing parameters
        self.min_receipt_area = 10000  # Minimum area for receipt detection
        self.max_receipt_area = 500000  # Maximum area for receipt detection
        self.contour_approximation_epsilon = 0.02  # For polygon approximation

    def preprocess_image(self, image_path: str) -> ProcessingResult:
        """
        Main preprocessing pipeline for receipt images.
        
        Args:
            image_path: Path to the input image
            
        Returns:
            ProcessingResult with processed image path and metadata
        """
        try:
            logger.info(f"Starting image preprocessing for: {image_path}")

            if not os.path.exists(image_path):
                return ProcessingResult(
                    success=False,
                    original_path=image_path,
                    message=f"Image file not found: {image_path}"
                )

            # Load image
            image = cv2.imread(image_path)
            if image is None:
                return ProcessingResult(
                    success=False,
                    original_path=image_path,
                    message="Failed to load image"
                )

            operations = []
            confidence = 0.5  # Base confidence

            # 1. Detect and crop receipt area
            cropped_image, crop_confidence = self.detect_receipt_area(image)
            if cropped_image is not None:
                image = cropped_image
                operations.append("receipt_area_detection")
                confidence += crop_confidence * 0.3

            # 2. Correct perspective
            corrected_image, perspective_confidence = self.correct_perspective(image)
            if corrected_image is not None:
                image = corrected_image
                operations.append("perspective_correction")
                confidence += perspective_confidence * 0.2

            # 3. Enhance contrast and reduce noise
            enhanced_image = self.enhance_contrast(image)
            if enhanced_image is not None:
                image = enhanced_image
                operations.append("contrast_enhancement")
                confidence += 0.1

            # 4. Reduce noise
            denoised_image = self.reduce_noise(image)
            if denoised_image is not None:
                image = denoised_image
                operations.append("noise_reduction")
                confidence += 0.1

            # 5. Resize to target dimensions
            resized_image = self.resize_image(image, self.target_width, self.target_height)
            if resized_image is not None:
                image = resized_image
                operations.append("resize")

            # Save processed image
            processed_path = self._save_processed_image(image, image_path)

            logger.info(f"Image preprocessing completed. Operations: {operations}")

            return ProcessingResult(
                success=True,
                processed_path=processed_path,
                original_path=image_path,
                operations_applied=operations,
                confidence=min(confidence, 1.0),
                message=f"Successfully processed with {len(operations)} operations"
            )

        except Exception as e:
            logger.error(f"Error preprocessing image {image_path}: {e}", exc_info=True)
            return ProcessingResult(
                success=False,
                original_path=image_path,
                message=f"Processing error: {str(e)}"
            )

    def detect_receipt_area(self, image: np.ndarray) -> tuple[np.ndarray | None, float]:
        """
        Detect and extract receipt area from image using edge detection.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            Tuple of (cropped_image, confidence)
        """
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Apply Gaussian blur
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)

            # Edge detection
            edges = cv2.Canny(blurred, 50, 150, apertureSize=3)

            # Find contours
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Filter contours by area
            valid_contours = [
                c for c in contours
                if self.min_receipt_area < cv2.contourArea(c) < self.max_receipt_area
            ]

            if not valid_contours:
                return None, 0.0

            # Find the largest contour (likely the receipt)
            largest_contour = max(valid_contours, key=cv2.contourArea)

            # Approximate contour to polygon
            epsilon = self.contour_approximation_epsilon * cv2.arcLength(largest_contour, True)
            approx = cv2.approxPolyDP(largest_contour, epsilon, True)

            # If we have 4 corners, we likely found a receipt
            if len(approx) == 4:
                # Extract bounding rectangle
                x, y, w, h = cv2.boundingRect(approx)

                # Add some padding
                padding = 10
                x = max(0, x - padding)
                y = max(0, y - padding)
                w = min(image.shape[1] - x, w + 2 * padding)
                h = min(image.shape[0] - y, h + 2 * padding)

                cropped = image[y:y+h, x:x+w]

                # Calculate confidence based on contour area ratio
                contour_area = cv2.contourArea(largest_contour)
                image_area = image.shape[0] * image.shape[1]
                confidence = min(contour_area / image_area, 1.0)

                logger.debug(f"Receipt area detected with confidence: {confidence:.2f}")
                return cropped, confidence

            return None, 0.0

        except Exception as e:
            logger.warning(f"Receipt area detection failed: {e}")
            return None, 0.0

    def correct_perspective(self, image: np.ndarray) -> tuple[np.ndarray | None, float]:
        """
        Correct perspective distortion in receipt image.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            Tuple of (corrected_image, confidence)
        """
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Apply adaptive threshold
            thresh = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )

            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if not contours:
                return None, 0.0

            # Find the largest contour
            largest_contour = max(contours, key=cv2.contourArea)

            # Approximate to polygon
            epsilon = 0.02 * cv2.arcLength(largest_contour, True)
            approx = cv2.approxPolyDP(largest_contour, epsilon, True)

            # Need 4 corners for perspective correction
            if len(approx) != 4:
                return None, 0.0

            # Order the corners (top-left, top-right, bottom-right, bottom-left)
            corners = self._order_corners(approx.reshape(4, 2))

            # Calculate dimensions of the corrected image
            width = max(
                np.linalg.norm(corners[1] - corners[0]),
                np.linalg.norm(corners[2] - corners[3])
            )
            height = max(
                np.linalg.norm(corners[3] - corners[0]),
                np.linalg.norm(corners[2] - corners[1])
            )

            # Define destination points
            dst_corners = np.array([
                [0, 0],
                [width - 1, 0],
                [width - 1, height - 1],
                [0, height - 1]
            ], dtype=np.float32)

            # Calculate perspective transform matrix
            transform_matrix = cv2.getPerspectiveTransform(
                corners.astype(np.float32), dst_corners
            )

            # Apply perspective correction
            corrected = cv2.warpPerspective(
                image, transform_matrix, (int(width), int(height))
            )

            # Calculate confidence based on aspect ratio
            aspect_ratio = width / height
            expected_ratio = 0.7  # Typical receipt aspect ratio
            confidence = 1.0 - abs(aspect_ratio - expected_ratio) / expected_ratio
            confidence = max(0.0, min(confidence, 1.0))

            logger.debug(f"Perspective correction applied with confidence: {confidence:.2f}")
            return corrected, confidence

        except Exception as e:
            logger.warning(f"Perspective correction failed: {e}")
            return None, 0.0

    def enhance_contrast(self, image: np.ndarray) -> np.ndarray | None:
        """
        Enhance contrast and brightness of receipt image.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            Enhanced image or None if failed
        """
        try:
            # Convert to PIL for easier manipulation
            pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

            # Enhance contrast
            contrast_enhancer = ImageEnhance.Contrast(pil_image)
            enhanced = contrast_enhancer.enhance(1.3)  # Increase contrast by 30%

            # Enhance brightness
            brightness_enhancer = ImageEnhance.Brightness(enhanced)
            enhanced = brightness_enhancer.enhance(1.1)  # Increase brightness by 10%

            # Enhance sharpness
            sharpness_enhancer = ImageEnhance.Sharpness(enhanced)
            enhanced = sharpness_enhancer.enhance(1.2)  # Increase sharpness by 20%

            # Convert back to OpenCV format
            return cv2.cvtColor(np.array(enhanced), cv2.COLOR_RGB2BGR)

        except Exception as e:
            logger.warning(f"Contrast enhancement failed: {e}")
            return None

    def reduce_noise(self, image: np.ndarray) -> np.ndarray | None:
        """
        Reduce noise in receipt image using filtering.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            Denoised image or None if failed
        """
        try:
            # Apply bilateral filter to reduce noise while preserving edges
            denoised = cv2.bilateralFilter(image, 9, 75, 75)

            # Apply median filter for additional noise reduction
            denoised = cv2.medianBlur(denoised, 3)

            return denoised

        except Exception as e:
            logger.warning(f"Noise reduction failed: {e}")
            return None

    def resize_image(self, image: np.ndarray, target_width: int, target_height: int) -> np.ndarray | None:
        """
        Resize image while maintaining aspect ratio.
        
        Args:
            image: Input image
            target_width: Target width
            target_height: Target height
            
        Returns:
            Resized image or None if failed
        """
        try:
            h, w = image.shape[:2]

            # Calculate scaling factor to fit within target dimensions
            scale = min(target_width / w, target_height / h)

            # Calculate new dimensions
            new_w = int(w * scale)
            new_h = int(h * scale)

            # Resize image
            resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

            # Create a new image with target dimensions and center the resized image
            result = np.zeros((target_height, target_width, 3), dtype=np.uint8)
            result.fill(255)  # White background

            # Calculate position to center the image
            y_offset = (target_height - new_h) // 2
            x_offset = (target_width - new_w) // 2

            # Place resized image in center
            result[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized

            return result

        except Exception as e:
            logger.warning(f"Image resize failed: {e}")
            return None

    def _order_corners(self, corners: np.ndarray) -> np.ndarray:
        """
        Order corners in the format: top-left, top-right, bottom-right, bottom-left.
        
        Args:
            corners: Array of 4 corners
            
        Returns:
            Ordered corners
        """
        # Calculate center point
        center = np.mean(corners, axis=0)

        # Sort by angle from center
        def angle_from_center(point):
            return np.arctan2(point[1] - center[1], point[0] - center[0])

        # Sort corners by angle
        sorted_corners = sorted(corners, key=angle_from_center)

        # Identify corners based on their position relative to center
        top_left = min(sorted_corners, key=lambda p: p[0] + p[1])
        bottom_right = max(sorted_corners, key=lambda p: p[0] + p[1])
        top_right = min(sorted_corners, key=lambda p: p[1] - p[0])
        bottom_left = max(sorted_corners, key=lambda p: p[1] - p[0])

        return np.array([top_left, top_right, bottom_right, bottom_left])

    def _save_processed_image(self, image: np.ndarray, original_path: str) -> str:
        """
        Save processed image to temporary location.
        
        Args:
            image: Processed image
            original_path: Path to original image
            
        Returns:
            Path to saved processed image
        """
        # Create temporary file
        original_name = Path(original_path).stem
        temp_dir = tempfile.gettempdir()
        processed_path = os.path.join(temp_dir, f"{original_name}_processed.jpg")

        # Save image
        cv2.imwrite(processed_path, image, [cv2.IMWRITE_JPEG_QUALITY, 95])

        return processed_path


def get_image_processor() -> ReceiptImageProcessor:
    """Factory function to get image processor instance."""
    return ReceiptImageProcessor()
