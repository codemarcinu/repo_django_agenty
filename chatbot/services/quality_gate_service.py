from chatbot.schemas import OCRResult

class QualityGateService:
    MIN_LINE_COUNT = 5 # Minimalna sensowna liczba linii na paragonie
    REQUIRED_KEYWORDS = ["SUMA", "PLN", "PARAGON"]

    def __init__(self, ocr_result: OCRResult):
        self.result = ocr_result
        self.score = 0
        self.reasons = []

    def calculate_quality_score(self) -> int:
        self._check_line_count()
        self._check_average_confidence()
        self._check_keyword_presence()
        # ... inne metryki ...
        return self.score

    def _check_line_count(self):
        # Logika oceny liczby linii
        # Example logic:
        if len(self.result.lines) >= self.MIN_LINE_COUNT:
            self.score += 30 # Arbitrary score for meeting minimum lines
        else:
            self.reasons.append("Niewystarczająca liczba linii.")

    def _check_average_confidence(self):
        # Logika oceny średniej pewności
        # Example logic:
        if self.result.confidences:
            avg_confidence = sum(self.result.confidences) / len(self.result.confidences)
            if avg_confidence > 0.8:
                self.score += 40
            elif avg_confidence > 0.6:
                self.score += 20
            else:
                self.reasons.append(f"Niska średnia pewność OCR: {avg_confidence:.2f}")
        else:
            self.reasons.append("Brak danych o pewności OCR.")

    def _check_keyword_presence(self):
        # Logika sprawdzania obecności słów kluczowych
        # Example logic:
        found_keywords = 0
        for keyword in self.REQUIRED_KEYWORDS:
            if keyword in self.result.full_text.upper():
                found_keywords += 1
        if found_keywords == len(self.REQUIRED_KEYWORDS):
            self.score += 30
        elif found_keywords > 0:
            self.score += 15
        else:
            self.reasons.append("Brak wymaganych słów kluczowych.")