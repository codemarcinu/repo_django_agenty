claude

Cel: Utworzyć izolowaną gałąź do wdrożenia pipeline’u OCR→parse→match→inventory.

Kroki:

    Utwórz nową gałąź git o nazwie feature/receipt-pipeline.

    Zapisz plan zadań (poniższą listę 15 kroków) w pliku docs/roadmap_receipts.md w formie checklisty.

Definicja ukończenia: Istnieje gałąź feature/receipt-pipeline i plik docs/roadmap_receipts.md z checklistą zadań.
Prompt 2: Modele bazy danych (PostgreSQL + JSONB)

Cel: Wprowadzić docelowy model danych dla nowej funkcjonalności.

Kroki:

    Dodaj nową aplikację Django o nazwie inventory.

    W aplikacji inventory utwórz następujące modele z polami zgodnymi z ERD:

        Receipt(id, store_name, purchased_at, total, currency, raw_text JSONB, source_file_path)

        ReceiptLineItem(id, receipt FK, product_name, quantity Decimal, unit_price Decimal, line_total Decimal, vat_code, meta JSONB, matched_product FK null=True)

        Product(id, name, brand, barcode, category FK, nutrition JSONB, aliases JSONB, is_active bool)

        Category(id, name, parent FK null=True)

        InventoryItem(id, product FK, purchase_date, expiry_date null=True, quantity_remaining Decimal, unit, storage_location, batch_id)

        ConsumptionEvent(id, inventory_item FK, consumed_qty Decimal, consumed_at, notes)

    Dodaj indeksy GIN dla pól JSONB (raw_text, meta, nutrition, aliases).

    Dodaj standardowe indeksy na polach barcode, product_name oraz matched_product.

    Wygeneruj i zastosuj migracje bazy danych.

Definicja ukończenia: Migracje zostały pomyślnie zastosowane, a testy jednostkowe dla nowo utworzonych modeli przechodzą poprawnie.
Prompt 3: Import plików paragonów (PDF/JPG/PNG)

Cel: Dodać endpoint API oraz zadanie asynchroniczne do importu plików z paragonami.

Kroki:

    Utwórz endpoint POST /api/receipts/upload, który wymaga autoryzacji.

    Zaimplementuj walidację przyjmowanych plików, dopuszczając tylko rozszerzenia: .pdf, .jpg, .jpeg, .png.

    Zapisz przesłany plik w ścieżce storage/receipts/{yyyy}/{mm}/{uuid}.{ext}.

    Po zapisaniu pliku, utwórz w bazie danych rekord Receipt ze statusem pending_ocr.

    Wywołaj asynchroniczne zadanie process_receipt(receipt_id) przekazując ID nowo utworzonego rekordu.

Definicja ukończenia: Test end-to-end potwierdza, że wysłanie pliku na endpoint skutkuje jego zapisaniem na dysku i utworzeniem rekordu Receipt w bazie danych.
Prompt 4: Moduł OCR z fallbackiem

Cel: Zbudować elastyczną warstwę OCR z automatycznym wyborem silnika w zależności od jakości pliku.

Kroki:

    Utwórz interfejs (klasę abstrakcyjną) OcrBackend z metodą extract_text(file_path) -> dict. Oczekiwany format zwrotny: {lines:[{text, conf}], blocks:[…], meta:{dpi,…}}.

    Zaimplementuj dwa adaptery do tego interfejsu: LocalPaddleOcrBackend i ExternalOcrApiBackend. Konfiguracja obu backendów (np. adresy URL, klucze API) powinna odbywać się za pomocą zmiennych środowiskowych.

    Utwórz logikę selektora:

        Jeśli typ pliku to PDF lub jego DPI wynosi co najmniej 300, użyj LocalPaddleOcrBackend.

        Jeśli średnia pewność rozpoznania tekstu (conf) przez LocalPaddleOcrBackend jest niższa niż 0.8, wykonaj ponowną próbę przy użyciu ExternalOcrApiBackend.

    Zapisz surowy wynik (JSON) z wybranego silnika OCR do pola Receipt.raw_text.

Definicja ukończenia: Testy jednostkowe dla obu backendów oraz dla logiki selektora przechodzą pomyślnie. Proces OCR poprawnie zapisuje wynik w polu JSONB rekordu Receipt.
Prompt 5: Parser pozycji z paragonu (regex + heurystyki)

Cel: Przetworzyć surowy tekst z OCR na ustrukturyzowane pozycje paragonu.

Kroki:

    Utwórz klasę ReceiptParser z metodą parse(raw_json) -> list[ParsedLine].

    Zaimplementuj heurystyki do parsowania linii:

        Wyodrębnij cenę za pomocą wyrażenia regularnego, np. r"([0-9]+[,.][0-9]{2})$".

        Rozpoznaj ilość (np. w formacie "2 * 3,59" lub "2 x 3,59").

        Rozpoznaj kod VAT (zwykle pojedyncza litera A, B, C, D).

        Znormalizuj separator dziesiętny (zawsze zamieniaj przecinek na kropkę).

    Dla każdej sparsowanej pozycji utwórz rekord ReceiptLineItem, uzupełniając line_total i unit_price.

    Oblicz sumę wartości line_total ze wszystkich pozycji. Porównaj ją z wartością Receipt.total i zapisz ewentualną różnicę w polu meta obiektu Receipt.

Definicja ukończenia: Testy parsera na dostarczonych przykładach paragonów (Lidl, Biedronka, Kaufland) przechodzą, a obliczona odchyłka sumy nie przekracza 0,05 PLN.
Prompt 6: Normalizacja nazw i fuzzy matching do Product

Cel: Zmapować sparsowane pozycje z paragonu do istniejącego katalogu produktów.

Kroki:

    Utwórz narzędzie NameNormalizer, które:

        Usuwa skróty miar (np. kg, g, szt, %, l, ml).

        Usuwa znaki interpunkcyjne.

        Redukuje wielokrotne spacje do pojedynczej.

        Konwertuje tekst na małe litery.

    Wprowadź konfigurowalny słownik zastępstw (np. “Soczew.” → “Soczewica”, “HummusChipsy” → “Chipsy hummus”).

    Zaimplementuj logikę dopasowania fuzzy match (np. używając thefuzz.token_set_ratio) z progiem dopasowania ustawionym na 85. Dopasowanie po kodzie EAN/barcode ma zawsze najwyższy priorytet.

    Jeśli nie znaleziono dopasowania, utwórz tymczasowy produkt ("ghost" Product) z is_active=False i dodaj oryginalną nazwę z paragonu do jego aliasów.

    Zaktualizuj pole ReceiptLineItem.matched_product o znaleziony lub nowo utworzony produkt.

Definicja ukończenia: Testy dopasowywania osiągają skuteczność powyżej 90% dla dostarczonych danych przykładowych.
Prompt 7: Integracja z OpenFoodFacts (wzbogacanie danych)

Cel: Automatycznie pobierać dodatkowe dane o produktach na podstawie ich kodów kreskowych.

Kroki:

    Dla produktów posiadających barcode, zaimplementuj funkcję pobierającą dane z API OpenFoodFacts (nazwa, marka, kategoria, składniki odżywcze - nutriments).

    Zapisz pobrane dane odżywcze do pola Product.nutrition (JSONB).

    Powiąż produkt z odpowiednią kategorią, tworząc brakujące kategorie w systemie na podstawie danych z API.

    Zaimplementuj mechanizm cache'owania wyników z API w bazie danych (np. zapisując timestamp i ETag) z czasem życia (TTL) ustawionym na 30 dni, aby unikać zbędnych zapytań.

Definicja ukończenia: Funkcja enrich_product(product_id) działa poprawnie, a testy jednostkowe z przykładowymi danymi (mockując API) przechodzą.
Prompt 8: Aktualizacja stanów magazynowych po zakupie

Cel: Automatycznie tworzyć pozycje w magazynie (InventoryItem) po przetworzeniu paragonu.

Kroki:

    Utwórz zadanie asynchroniczne finalize_receipt(receipt_id).

    W zadaniu, dla każdego ReceiptLineItem z dopasowanym produktem, utwórz nowy InventoryItem z:

        purchase_date = Receipt.purchased_at

        quantity_remaining = ReceiptLineItem.quantity

        unit wyznaczonym heurystycznie (np. szt, opak, kg).

    Wylicz wstępną datę ważności (expiry_date) na podstawie kategorii produktu (np. nabiał: +14 dni; pieczywo: +3 dni). Konfiguracja tych wartości powinna być przechowywana w polu meta (JSONB) modelu Category.

Definicja ukończenia: Po pomyślnym przetworzeniu paragonu, każdy jego wiersz z dopasowanym produktem ma odpowiadający mu rekord InventoryItem w bazie danych.
Prompt 9: Zdarzenia zużycia i alerty niskich stanów

Cel: Umożliwić śledzenie konsumpcji i automatycznie powiadamiać o kończących się produktach.

Kroki:

    Utwórz endpoint POST /api/inventory/{id}/consume z polami consumed_qty i notes.

    Utwórz zadanie okresowe (uruchamiane co 24h), które sprawdza stany magazynowe i wyszukuje pozycje, gdzie quantity_remaining jest poniżej progu reorder_point (dodanego do modelu Product) lub expiry_date jest w ciągu najbliższych 2 dni.

    Zaimplementuj wysyłkę powiadomienia (e-mail lub push) z informacją o niskim stanie lub zbliżającej się dacie ważności. Użyj szablonów (HTML + tekst).

Definicja ukończenia: Testy dla endpointu konsumpcji działają, a zadanie okresowe poprawnie identyfikuje pozycje do alertowania i symuluje wysyłkę powiadomienia.
Prompt 10: Panel przeglądu (dashboard)

Cel: Stworzyć interfejs użytkownika do szybkiego wglądu w zakupy, stany magazynowe i statystyki.

Kroki:

    Zaprojektuj i zaimplementuj widok dashboardu, który wyświetla:

        Listę ostatnich paragonów.

        Top 5 kategorii wydatków z ostatnich 30 dni.

        Listę produktów, które wkrótce się skończą lub stracą ważność.

    Dodaj wizualizację "Consumption heatmap" (mapa cieplna) pokazującą zużycie w podziale na dzień tygodnia i kategorię produktu.

    Zoptymalizuj zapytania do bazy danych poprzez użycie agregacji SQL, a w razie potrzeby zaimplementuj widoki zmaterializowane, odświeżane przez zadanie cykliczne.

Definicja ukończenia: Strony dashboardu ładują się i działają poprawnie, a czas odpowiedzi zapytań do bazy jest poniżej 150ms dzięki indeksom i optymalizacjom.
Prompt 11: Aplikacja mobilna – skan kodów kreskowych (opcjonalnie)

Cel: Uprościć dodawanie i zużywanie produktów za pomocą skanera w aplikacji mobilnej.

Kroki:

    Zaimplementuj ekran ze skanerem kodów kreskowych, który obsługuje tryb "batch" (skanowanie wielu kodów jeden po drugim).

    Logika po skanie:

        Jeśli produkt istnieje w bazie: otwórz ekran "zużyj" (consume).

        Jeśli produkt nie istnieje: utwórz jego szkic i zaproponuj użytkownikowi dopasowanie lub uzupełnienie danych.

    Zapewnij działanie w trybie offline-first, z synchronizacją danych po odzyskaniu połączenia z siecią.

Definicja ukończenia: Skanowanie i operacje na produktach działają płynnie, a dane poprawnie synchronizują się z serwerem.
Prompt 12: Jakość kodu i testy

Cel: Utrzymać wysoką jakość kodu, czytelność i niezawodność aplikacji.

Kroki:

    Skonfiguruj i włącz lintery w procesie CI: ruff oraz mypy do statycznego typowania.

    Użyj black do automatycznego formatowania kodu.

    Rozbuduj zestaw testów o:

        Testy jednostkowe (parser, matcher, enricher).

        Testy end-to-end (od uploadu pliku do utworzenia InventoryItem).

        Testy oparte na właściwościach (property-based) dla parsera, generujące losowe linie paragonów.

    Ustaw próg pokrycia kodu testami na >85%.

Definicja ukończenia: Pipeline CI jest "zielony", a wszystkie skonfigurowane progi jakościowe są spełnione.
Prompt 13: Wydajność i profilowanie

Cel: Zapewnić szybkie odpowiedzi API i uniknąć problemów wydajnościowych.

Kroki:

    Dodaj narzędzia do profilowania żądań w środowisku deweloperskim (np. django-debug-toolbar).

    Zidentyfikuj i wyeliminuj problemy N+1 zapytań, stosując select_related oraz prefetch_related.

    Zaimplementuj cache'owanie dla najcięższych zapytań (np. agregacje na dashboardzie) na 5–15 minut.

Definicja ukończenia: Przedstawiony jest raport z czasami odpowiedzi API przed i po optymalizacjach.
Prompt 14: Observability i błędy

Cel: Umożliwić szybką diagnozę problemów na środowisku produkcyjnym.

Kroki:

    Skonfiguruj centralny system logowania (np. ELK, Grafana Loki), który koreluje logi na podstawie request_id lub task_id.

    Dodaj monitoring kluczowych metryk dla kolejek zadań asynchronicznych (np. czas oczekiwania, czas przetwarzania OCR, liczba błędów dopasowania).

    Skonfiguruj alerty, które będą uruchamiane w przypadku nagłego wzrostu liczby błędów.

Definicja ukończenia: Dostępny jest dashboard z logami i metrykami, a system alertowania jest skonfigurowany i przetestowany.
Prompt 15: Migracja danych historycznych (one-shot)

Cel: Zaimportować istniejące, stare paragony do nowego systemu.

Kroki:

    Utwórz skrypt w formie komendy manage.py (np. import_receipts), który przyjmuje ścieżkę do katalogu z plikami.

    Skrypt powinien iterować po plikach i dla każdego z nich uruchamiać proces OCR i parsowania.

    Zaimplementuj przetwarzanie wsadowe (batching) oraz limit równoległości, aby nie przeciążyć systemu.

Definicja ukończenia: Skrypt działa poprawnie i generuje raport w formacie CSV z listą przetworzonych plików, statusami (sukces/błąd) oraz informacją o ewentualnych duplikatach.
Dodatkowe wskazówki dla agenta

    Decision Records: Każde zadanie kończ pull requestem. W opisie PR umieść krótki "Architecture Decision Record" (ADR) w formacie markdown, opisując: problem, podjętą decyzję, rozważane alternatywy i konsekwencje. Możesz zapisywać je w docs/adr/.

    Wizualizacja: Do każdego PR załącz krótkie nagranie ekranu lub GIF prezentujący "happy path" zaimplementowanej funkcjonalności (np. upload pliku → pojawienie się InventoryItem → wygenerowanie alertu).

    Test Fixtures: Przy każdym kroku rozbudowuj dane testowe (fixtures). Użyj dostarczonych przykładów paragonów (Lidl, Biedronka, Kaufland) i twórz snapshoty oczekiwanych rekordów w bazie danych po przetworzeniu.