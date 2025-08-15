# Receipt Processing Pipeline - Roadmap

## Cel: Implementacja kompletnego systemu OCR→parse→match→inventory dla paragonów

### Checklist zadań do wykonania:

#### Prompt 1: Izolowana gałąź i planowanie
- [x] Utwórz nową gałąź git o nazwie feature/receipt-pipeline
- [x] Zapisz plan zadań w pliku docs/roadmap_receipts.md w formie checklisty

#### Prompt 2: Modele bazy danych (PostgreSQL + JSONB)
- [x] Dodaj nową aplikację Django o nazwie inventory
- [x] Utwórz modele w aplikacji inventory:
  - [x] Receipt(id, store_name, purchased_at, total, currency, raw_text JSONB, source_file_path)
  - [x] ReceiptLineItem(id, receipt FK, product_name, quantity Decimal, unit_price Decimal, line_total Decimal, vat_code, meta JSONB, matched_product FK null=True)
  - [x] Product(id, name, brand, barcode, category FK, nutrition JSONB, aliases JSONB, is_active bool)
  - [x] Category(id, name, parent FK null=True)
  - [x] InventoryItem(id, product FK, purchase_date, expiry_date null=True, quantity_remaining Decimal, unit, storage_location, batch_id)
  - [x] ConsumptionEvent(id, inventory_item FK, consumed_qty Decimal, consumed_at, notes)
- [x] Dodaj indeksy GIN dla pól JSONB (raw_text, meta, nutrition, aliases)
- [x] Dodaj standardowe indeksy na polach barcode, product_name oraz matched_product
- [x] Wygeneruj i zastosuj migracje bazy danych
- [x] Napisz testy jednostkowe dla nowo utworzonych modeli

#### Prompt 3: Import plików paragonów (PDF/JPG/PNG)
- [x] Utwórz endpoint POST /api/receipts/upload z autoryzacją
- [x] Zaimplementuj walidację plików (.pdf, .jpg, .jpeg, .png)
- [x] Zapisz pliki w ścieżce storage/receipts/{yyyy}/{mm}/{uuid}.{ext}
- [x] Utwórz rekord Receipt ze statusem pending_ocr
- [x] Wywołaj asynchroniczne zadanie process_receipt(receipt_id)
- [x] Test end-to-end uploadu plików

#### Prompt 4: Moduł OCR z fallbackiem
- [x] Utwórz interfejs (klasę abstrakcyjną) OcrBackend
- [x] Zaimplementuj EasyOCRBackend i TesseractBackend
- [x] Utwórz logikę selektora OCR z fallbackiem
- [x] Zapisz surowy wynik JSON do Receipt.raw_text
- [x] Testy jednostkowe dla backendów OCR

#### Prompt 5: Parser pozycji z paragonu (regex + heurystyki)
- [x] Utwórz klasę ReceiptParser z metodą parse(raw_json)
- [x] Zaimplementuj heurystyki parsowania:
  - [x] Wyodrębnienie cen (regex: r"([0-9]+[,.][0-9]{2})$")
  - [x] Rozpoznanie ilości (format "2 * 3,59" lub "2 x 3,59")
  - [x] Rozpoznanie kodu VAT (A, B, C, D)
  - [x] Normalizacja separatora dziesiętnego
- [x] Tworzenie rekordów ReceiptLineItem
- [x] Porównanie sumy z Receipt.total (różnica max 0,05 PLN)
- [x] Testy parsera na paragonach polskich sklepów

#### Prompt 6: Normalizacja nazw i fuzzy matching do Product
- [x] Utwórz narzędzie NameNormalizer
- [x] Usuń skróty miar, znaki interpunkcyjne, wielokrotne spacje
- [x] Konfigurowalny słownik zastępstw
- [x] Fuzzy matching (thefuzz.token_set_ratio, próg 85)
- [x] Priorytet dopasowania po kodzie EAN/barcode
- [x] Tworzenie "ghost" produktów (is_active=False)
- [x] Aktualizacja ReceiptLineItem.matched_product
- [x] Testy skuteczności i fuzzy matching

#### Prompt 7: Automatyczne zarządzanie magazynem
- [x] Zadanie asynchroniczne finalize_receipt(receipt_id)
- [x] Tworzenie InventoryItem dla każdego ReceiptLineItem z dopasowanym produktem
- [x] Wyliczenie wstępnej daty ważności na podstawie kategorii
- [x] Konfiguracja w Category.meta (JSONB)
- [x] Test: każdy wiersz paragonu → InventoryItem
- [x] Integracja z pełnym pipeline'em OCR→parsing→matching→inventory

#### Prompt 8: Dashboard i widoki użytkownika
- [x] Widok dashboardu z:
  - [x] Lista ostatnich paragonów
  - [x] Podsumowanie magazynu
  - [x] Produkty kończące się/tracące ważność
  - [x] Produkty o niskim stanie
- [x] Strony szczegółowe produktów i paragonów
- [x] Filtrowanie i paginacja
- [x] Template'y HTML i URL routing
- [x] Optymalizacja zapytań SQL

#### Prompt 9: Zdarzenia zużycia i alerty
- [x] Endpoint POST /api/inventory/{id}/consume
- [x] Zadanie okresowe (24h) sprawdzające stany magazynowe
- [x] Identyfikacja pozycji poniżej reorder_point lub wygasających w 2 dni
- [x] Wysyłka powiadomień (e-mail/push) z szablonami
- [x] Testy endpointu i zadania okresowego

#### Prompt 10: Panel przeglądu (dashboard) - rozszerzenie
- [ ] Wizualizacja "Consumption heatmap"
- [ ] Top 5 kategorii wydatków (30 dni)
- [ ] Wykresy i statystyki
- [ ] Czas odpowiedzi <150ms

#### Prompt 11: Aplikacja mobilna – skan kodów (opcjonalnie)
- [ ] Ekran ze skanerem kodów kreskowych (tryb batch)
- [ ] Logika po skanie (produkt istnieje/nie istnieje)
- [ ] Tryb offline-first z synchronizacją
- [ ] Płynne działanie i synchronizacja z serwerem

#### Prompt 12: Jakość kodu i testy
- [ ] Konfiguracja linterów w CI (ruff, mypy)
- [ ] Automatyczne formatowanie (black)
- [ ] Rozbudowa testów:
  - [ ] Testy jednostkowe (parser, matcher, enricher)
  - [ ] Testy end-to-end (upload → InventoryItem)
  - [ ] Testy property-based dla parsera
- [ ] Próg pokrycia testami >85%
- [ ] Pipeline CI "zielony"

#### Prompt 13: Wydajność i profilowanie
- [ ] Narzędzia profilowania (django-debug-toolbar)
- [ ] Eliminacja problemów N+1 (select_related, prefetch_related)
- [ ] Cache'owanie ciężkich zapytań (5-15 min)
- [ ] Raport czasów odpowiedzi przed/po optymalizacjach

#### Prompt 14: Observability i błędy
- [ ] Centralny system logowania (ELK/Grafana Loki)
- [ ] Korelacja logów (request_id/task_id)
- [ ] Monitoring metryk kolejek asynchronicznych
- [ ] Alerty przy wzroście błędów
- [ ] Dashboard z logami i metrykami

#### Prompt 15: Migracja danych historycznych
- [ ] Skrypt manage.py import_receipts
- [ ] Iteracja po plikach z OCR i parsowaniem
- [ ] Przetwarzanie wsadowe z limitem równoległości
- [ ] Raport CSV (pliki, statusy, duplikaty)

### Dodatkowe wskazówki:
- [ ] Decision Records (ADR) w docs/adr/ dla każdego PR
- [ ] Wizualizacja funkcjonalności (nagrania/GIF) dla PR
- [ ] Test Fixtures z przykładami paragonów (Lidl, Biedronka, Kaufland)

---
**Status:** W trakcie realizacji
**Gałąź:** feature/receipt-pipeline
**Data rozpoczęcia:** 2025-08-15