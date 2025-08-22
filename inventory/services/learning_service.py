import difflib
import logging

from inventory.models import OcrCorrectionPattern

logger = logging.getLogger(__name__)

class LearningService:
    """Service responsible for learning correction patterns from OCR discrepancies."""

    def generate_correction_patterns(self, local_text: str, ground_truth_text: str):
        """
        Compares local OCR text with ground truth text to identify and save
        correction patterns.
        """
        s = difflib.SequenceMatcher(None, local_text, ground_truth_text)
        for opcode, a_start, a_end, b_start, b_end in s.get_opcodes():
            if opcode == 'replace':
                error_segment = local_text[a_start:a_end]
                correct_segment = ground_truth_text[b_start:b_end]

                if error_segment and correct_segment: # Ensure segments are not empty
                    # For simplicity, assign a default confidence score and increment times_applied
                    # In a more advanced system, confidence could be derived from context or frequency
                    pattern, created = OcrCorrectionPattern.objects.update_or_create(
                        error_pattern=error_segment,
                        defaults={
                            'correct_pattern': correct_segment,
                            'confidence_score': 0.9, # Default confidence
                            'times_applied': 1,  # Initialize times_applied
                            'is_active': True,
                        }
                    )
                    if not created:
                        pattern.times_applied += 1
                        pattern.save(update_fields=['times_applied'])
                        logger.info(f"Updated correction pattern: '{error_segment}' -> '{correct_segment}'. Times applied: {pattern.times_applied}")
                    else:
                        logger.info(f"Created new correction pattern: '{error_segment}' -> '{correct_segment}'")

            elif opcode == 'delete':
                # Handle deletions if necessary, e.g., if a common OCR error is adding extra chars
                pass
            elif opcode == 'insert':
                # Handle insertions if necessary, e.g., if a common OCR error is missing chars
                pass
