# Plan Implementacji Samodoskonalącego się Systemu OCR

## Etap 1: Fundamenty w Bazie Danych – Tworzenie Pamięci Systemu
- [ ] 1.1: Dodanie modelu `OcrTrainingSample` do `inventory/models.py`.
- [ ] 1.2: Dodanie modelu `OcrCorrectionPattern` do `inventory/models.py`.
- [ ] 1.3: Wygenerowanie migracji dla nowych modeli (`python manage.py makemigrations inventory`).
- [ ] 1.4: Weryfikacja zawartości wygenerowanej migracji.
- [ ] 1.5: (Opcjonalnie, do potwierdzenia) Zastosowanie migracji (`python manage.py migrate`).

## Etap 2: Integracja "Nauczyciela" – Podłączenie do Mistral OCR
- [ ] 2.1: Dodanie `MISTRAL_API_KEY` do `core/settings_dev.py`.
- [ ] 2.2: Stworzenie nowej klasy `MistralOCRBackend` w `chatbot/services/ocr_backends.py`, dziedziczącej po `OCRBackendInterface`.
- [ ] 2.3: Implementacja metody `perform_ocr` w `MistralOCRBackend`.

## Etap 3: Logika "Inteligentnego Przełącznika" – Oszczędność i Efektywność
- [ ] 3.1: Stworzenie nowego zadania Celery `run_mistral_ocr_and_save_sample_task` w `inventory/tasks.py`.
- [ ] 3.2: Modyfikacja zadania `process_receipt_task` w `inventory/tasks.py` w celu wywołania `run_mistral_ocr_and_save_sample_task` na podstawie wyniku `QualityGateService`.

## Etap 4: Mechanizm Uczenia się – Budowanie Wiedzy z Danych
- [ ] 4.1: Stworzenie nowego pliku `inventory/services/learning_service.py` z klasą `LearningService`.
- [ ] 4.2: Implementacja metody `generate_correction_patterns` w `LearningService` używającej `difflib`.
- [ ] 4.3: Modyfikacja zadania `run_mistral_ocr_and_save_sample_task` w `inventory/tasks.py` w celu użycia `MistralOCRBackend` i `LearningService`.

## Etap 5: Aplikowanie Korekt – Wykorzystanie Nabytej Wiedzy
- [ ] 5.1: Stworzenie pliku `inventory/services/correction_service.py` z klasą `OcrCorrectionService`.
- [ ] 5.2: Implementacja metody `apply` w `OcrCorrectionService`, która stosuje wzorce `OcrCorrectionPattern`.
- [ ] 5.3: Modyfikacja `HybridOCRService` w `chatbot/services/hybrid_ocr_service.py` w celu wstrzyknięcia i użycia `OcrCorrectionService`.

## Etap 6: Monitoring i Zarządzanie – Panel Kontrolny dla Człowieka
- [ ] 6.1: Rejestracja modelu `OcrTrainingSample` w `inventory/admin.py`.
- [ ] 6.2: Rejestracja modelu `OcrCorrectionPattern` w `inventory/admin.py` z odpowiednią konfiguracją `list_display`, `list_filter`, `search_fields`.
- [ ] 6.3: Dodanie akcji administracyjnej `deactivate_patterns` dla `OcrCorrectionPatternAdmin`.
