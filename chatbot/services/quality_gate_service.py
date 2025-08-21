import logging

from .ocr_service import OCRResult

logger = logging.getLogger(__name__)


class QualityGateService:
    """
    Ocenia jakość wyniku OCR na podstawie zdefiniowanych kryteriów.
    """
    MIN_LINE_COUNT = 3  # Minimalna wymagana liczba linii
    MIN_CONFIDENCE_SCORE = 0.6  # Minimalny próg pewności OCR

    def __init__(self, result: OCRResult):
        """
        Inicjalizuje QualityGateService z wynikiem OCR.
        """
        if not isinstance(result, OCRResult):
            # Dodaj więcej informacji diagnostycznych
            result_type = type(result).__name__
            result_value = str(result)[:100] if result else "None"

            raise TypeError(
                f"result must be an instance of OCRResult, "
                f"but received {result_type}: {result_value}"
            )

        self.ocr_result = result
        self.score = 0
        self.reasons = []

    def calculate_quality_score(self) -> int:
        """
        Oblicza ogólny wynik jakości na podstawie różnych kontroli.
        """
        self._check_line_count()
        self._check_confidence()
        logger.info(f"Quality Gate for OCR completed with score: {self.score}. Reasons: {self.reasons}")
        return self.score

    def _check_line_count(self):
        """
        Sprawdza, czy liczba linii w tekście OCR jest wystarczająca.
        """
        # Poprawka: Dzielimy `self.ocr_result.text` na linie, aby policzyć ich liczbę.
        lines = self.ocr_result.text.strip().split('\n')
        line_count = len(lines)

        if line_count >= self.MIN_LINE_COUNT:
            self.score += 50
        else:
            self.reasons.append(f"Insufficient line count: {line_count} < {self.MIN_LINE_COUNT}")

    def _check_confidence(self):
        """
        Sprawdza, czy pewność wyniku OCR jest powyżej progu.
        """
        confidence = self.ocr_result.confidence or 0.0
        if confidence >= self.MIN_CONFIDENCE_SCORE:
            self.score += 50
        else:
            self.reasons.append(f"Low confidence score: {confidence:.2f} < {self.MIN_CONFIDENCE_SCORE}")
