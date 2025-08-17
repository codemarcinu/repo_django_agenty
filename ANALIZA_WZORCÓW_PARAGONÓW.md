# Analiza wzorców paragonów - Plan dostrojenia algorytmów parsowania

## Problemy zidentyfikowane w obecnym systemie

### 1. **KRYTYCZNY PROBLEM**: Parser błędnie klasyfikuje linie podatkowe jako produkty
- `PTU A 25,39` jest klasyfikowany jako produkt zamiast informacji podatkowej
- `Kwota A 23,00% 4,75` również jest parsowany jako produkt
- To powoduje **fałszywie zawyżoną liczbę produktów** i **błędne sumy**

### 2. Format Lidl nie jest w pełni obsługiwany
**Rzeczywisty format Lidl:**
```
NAZWA_PRODUKTU ILOŚĆ * CENA_JEDNOSTKOWA CENA_CAŁKOWITA KOD_PODATKOWY
Baton Protein Nuts 2 * 1,79 3,58 B
Tortilla Chipsy 1 * 3,89 3,89 C
```

**Obecny parser nie obsługuje:**
- Separatora `*` między ilością a ceną jednostkową
- Kodów podatkowych (A, B, C) na końcu linii
- Poprawnego wyodrębniania ceny jednostkowej i całkowitej

### 3. Nieprawidłowe wykrywanie sekcji produktów
- Parser błędnie włącza linie podatkowe (PTU, Kwota) do sekcji produktów
- Nie rozpoznaje końca listy produktów przed sekcją podatkową
- `_find_products_end()` nie wykrywa słów kluczowych "PTU", "Kwota"

## Wzorce sklepów zidentyfikowane

### LIDL (format standardowy)
```
Format: NAZWA ILOŚĆ * CENA_JEDN CENA_CAŁK KOD_PODATKU
Przykład: Baton Protein Nuts 2 * 1,79 3,58 B

Charakterystyka:
- Zawsze kod podatkowy na końcu (A, B, C)  
- Separator * między ilością a ceną jednostkową
- Polska notacja dziesiętna (przecinek)
- Sekcja PTU/Kwota oddzielnie
```

### Inne sklepy (do dalszej analizy)
- Biedronka: format może się różnić
- Kaufland: prawdopodobnie inny układ  
- Żabka: kompaktowy format
- Tesco, Carrefour: standardy międzynarodowe

## Plan ulepszenia algorytmów

### FAZA 1: Naprawienie krytycznych błędów 🔴
1. **Dodanie wykluczeń linii podatkowych**
   - PTU [A-C] + kwota
   - Kwota [A-C] + procent + kwota
   - Suma, Razem (już obsługiwane częściowo)

2. **Poprawienie wzorców produktów dla Lidl**
   - Nowy pattern: `^(.+?)\s+(\d+(?:[,.]?\d+)?)\s*\*\s*(\d+[,.]?\d{2})\s+(\d+[,.]?\d{2})\s+[ABC]\s*$`
   - Wyższa pewność (confidence) dla tego wzorca

3. **Ulepszona detekcja końca produktów**
   - Dodanie "PTU", "Kwota" do keywords końcowych
   - Lepsze rozpoznawanie sekcji podsumowania

### FAZA 2: Adaptacyjne parsery 🟡
4. **System rozpoznawania sklepu**
   - Identyfikacja sklepu na podstawie nagłówka
   - Wybór odpowiedniego parsera specjalistycznego  

5. **Parsery specjalistyczne**
   - `LidlReceiptParser` - dla formatu Lidl
   - `BiedronkaReceiptParser` - dla Biedronki
   - `GenericReceiptParser` - fallback

### FAZA 3: Zaawansowana inteligencja 🟢  
6. **Inteligentne wyodrębnianie nazw**
   - Analiza kontekstu dla nazw produktów
   - Rozpoznawanie typowych słów (szt, kg, ml)
   - Normalizacja nazw produktów

7. **Obsługa błędów OCR**
   - Korekta typowych błędów rozpoznawania
   - Alternatywne wzorce dla zniekształconego tekstu

8. **Walidacja logiczna**
   - Sprawdzanie sum (ilość × cena_jedn = cena_całk)
   - Weryfikacja kodów podatkowych
   - Wykrywanie duplikatów

## Metryki success

### Obecne wyniki (baseline):
- Liczba produktów: 8-10 na paragon (z błędami PTU/Kwota)
- Dokładność nazw: ~70% 
- Poprawność sum: niedokładna (błędne klasyfikowanie)

### Docelowe wyniki po ulepszeniu:
- Liczba produktów: dokładna (4-5 rzeczywistych produktów na paragon)
- Dokładność nazw: >90%
- Poprawność sum: >95%
- Obsługa formatów: 100% dla Lidl, 80%+ dla innych

## Priorytet implementacji

**WYSOKI** (natychmiastowe):
- Wykluczenie linii PTU/Kwota z produktów
- Nowy pattern dla formatu Lidl  
- Poprawiona detekcja końca produktów

**ŚREDNI** (2-3 dni):
- System rozpoznawania sklepów
- Parsery specjalistyczne

**NISKI** (optymalizacja):
- Zaawansowana inteligencja  
- Machine learning

## Następne kroki
1. ✅ Identyfikacja problemów
2. ✅ Analiza wzorców
3. 🔄 Implementacja ulepszeń Fazy 1
4. ⏳ Testy na rzeczywistych paragonach
5. ⏳ Iteracja i optymalizacja