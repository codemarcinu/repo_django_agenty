import logging

from inventory.models import OcrCorrectionPattern

logger = logging.getLogger(__name__)

class OcrCorrectionService:
    """Service responsible for applying learned OCR correction patterns."""

    def __init__(self):
        self.correction_patterns = self._load_active_patterns()
        logger.info(f"Loaded {len(self.correction_patterns)} active OCR correction patterns.")

    def _load_active_patterns(self) -> list[tuple[str, str]]:
        """
        Loads all active OcrCorrectionPattern objects from the database into memory.
        Returns a list of (error_pattern, correct_pattern) tuples.
        """
        patterns = []
        for pattern_obj in OcrCorrectionPattern.objects.filter(is_active=True):
            patterns.append((pattern_obj.error_pattern, pattern_obj.correct_pattern))
        return patterns

    def apply(self, text: str) -> str:
        """
        Applies all loaded correction patterns to the given text.
        """
        if text is None:
            return None

        corrected_text = text
        for error, correct in self.correction_patterns:
            corrected_text = corrected_text.replace(error, correct)
        return corrected_text
