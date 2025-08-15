# Receipt Processing Pipeline - Roadmap

## Cel: Implementacja kompletnego systemu OCR→parse→match→inventory dla paragonów

### Checklist zadań do wykonania:

#### Prompt 1: Izolowana gałąź i planowanie
- [x] Utwórz nową gałąź git o nazwie feature/receipt-pipeline
- [x] Zapisz plan zadań w pliku docs/roadmap_receipts.md w formie checklisty

#### Prompt 2: Modele bazy danych (PostgreSQL + JSONB)
- [ ] Dodaj nową aplikację Django o nazwie inventory
- [ ] Utwórz modele w aplikacji inventory:
  - [ ] Receipt(id, store_name, purchased_at, total, currency, raw_text JSONB, source_file_path)
  - [ ] ReceiptLineItem(id, receipt FK, product_name, quantity Decimal, unit_price Decimal, line_total Decimal, vat_code, meta JSONB, matched_product FK null=True)
  - [ ] Product(id, name, brand, barcode, category FK, nutrition JSONB, aliases JSONB, is_active bool)
  - [ ] Category(id, name, parent FK null=True)
  - [ ] InventoryItem(id, product FK, purchase_date, expiry_date null=True, quantity_remaining Decimal, unit, storage_location, batch_id)
  - [ ] ConsumptionEvent(id, inventory_item FK, consumed_qty Decimal, consumed_at, notes)
- [ ] Dodaj indeksy GIN dla pól JSONB (raw_text, meta, nutrition, aliases)
- [ ] Dodaj standardowe indeksy na polach barcode, product_name oraz matched_product
- [ ] Wygeneruj i zastosuj migracje bazy danych
- [ ] Napisz testy jednostkowe dla nowo utworzonych modeli

#### Prompt 3: Import plików paragonów (PDF/JPG/PNG)
- [ ] Utwórz endpoint POST /api/receipts/upload z autoryzacją
- [ ] Zaimplementuj walidację plików (.pdf, .jpg, .jpeg, .png)
- [ ] Zapisz pliki w ścieżce storage/receipts/{yyyy}/{mm}/{uuid}.{ext}
- [ ] Utwórz rekord Receipt ze statusem pending_ocr
- [ ] Wywołaj asynchroniczne zadanie process_receipt(receipt_id)
- [ ] Test end-to-end uploadu plików

#### Prompt 4: Moduł OCR z fallbackiem
- [ ] Utwórz interfejs (klasę abstrakcyjną) OcrBackend
- [ ] Zaimplementuj LocalPaddleOcrBackend i ExternalOcrApiBackend
- [ ] Utwórz logikę selektora OCR (PDF/DPI ≥300 → LocalPaddle, conf<0.8 → External)
- [ ] Zapisz surowy wynik JSON do Receipt.raw_text
- [ ] Testy jednostkowe dla backendów OCR

#### Prompt 5: Parser pozycji z paragonu (regex + heurystyki)
- [ ] Utwórz klasę ReceiptParser z metodą parse(raw_json)
- [ ] Zaimplementuj heurystyki parsowania:
  - [ ] Wyodrębnienie cen (regex: r"([0-9]+[,.][0-9]{2})$")
  - [ ] Rozpoznanie ilości (format "2 * 3,59" lub "2 x 3,59")
  - [ ] Rozpoznanie kodu VAT (A, B, C, D)
  - [ ] Normalizacja separatora dziesiętnego
- [ ] Tworzenie rekordów ReceiptLineItem
- [ ] Porównanie sumy z Receipt.total (różnica max 0,05 PLN)
- [ ] Testy parsera na paragonach Lidl, Biedronka, Kaufland

#### Prompt 6: Normalizacja nazw i fuzzy matching do Product
- [ ] Utwórz narzędzie NameNormalizer
- [ ] Usuń skróty miar, znaki interpunkcyjne, wielokrotne spacje
- [ ] Konfigurowalny słownik zastępstw
- [ ] Fuzzy matching (thefuzz.token_set_ratio, próg 85)
- [ ] Priorytet dopasowania po kodzie EAN/barcode
- [ ] Tworzenie "ghost" produktów (is_active=False)
- [ ] Aktualizacja ReceiptLineItem.matched_product
- [ ] Testy skuteczności >90%

#### Prompt 7: Integracja z OpenFoodFacts
- [ ] Funkcja pobierania danych z API OpenFoodFacts po barcode
- [ ] Zapisanie danych odżywczych do Product.nutrition (JSONB)
- [ ] Powiązanie z kategorią, tworzenie brakujących kategorii
- [ ] Cache'owanie wyników (TTL 30 dni)
- [ ] Funkcja enrich_product(product_id)
- [ ] Testy z mockowanym API

#### Prompt 8: Aktualizacja stanów magazynowych
- [ ] Zadanie asynchroniczne finalize_receipt(receipt_id)
- [ ] Tworzenie InventoryItem dla każdego ReceiptLineItem z dopasowanym produktem
- [ ] Wyliczenie wstępnej daty ważności na podstawie kategorii
- [ ] Konfiguracja w Category.meta (JSONB)
- [ ] Test: każdy wiersz paragonu → InventoryItem

#### Prompt 9: Zdarzenia zużycia i alerty
- [ ] Endpoint POST /api/inventory/{id}/consume
- [ ] Zadanie okresowe (24h) sprawdzające stany magazynowe
- [ ] Identyfikacja pozycji poniżej reorder_point lub wygasających w 2 dni
- [ ] Wysyłka powiadomień (e-mail/push) z szablonami
- [ ] Testy endpointu i zadania okresowego

#### Prompt 10: Panel przeglądu (dashboard)
- [ ] Widok dashboardu z:
  - [ ] Lista ostatnich paragonów
  - [ ] Top 5 kategorii wydatków (30 dni)
  - [ ] Produkty kończące się/tracące ważność
- [ ] Wizualizacja "Consumption heatmap"
- [ ] Optymalizacja zapytań SQL, widoki zmaterializowane
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