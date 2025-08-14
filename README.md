# Witaj w Świecie Twojego Osobistego Asystenta AI

Ten plik to instrukcja obsługi Twojej osobistej aplikacji z inteligentnym asystentem. Przeczytaj go, aby dowiedzieć się, czym jest ten program, co potrafi i jak z niego korzystać.

---

## Czym jest ta aplikacja?

Wyobraź sobie, że masz na swoim komputerze prywatnego, inteligentnego pomocnika. To właśnie jest ta aplikacja. To nie jest kolejny chatbot na stronie internetowej, ale Twój własny, lokalny system sztucznej inteligencji. Działa on w całości na Twoim sprzęcie, co zapewnia pełną prywatność i bezpieczeństwo Twoich danych.

Możesz z nim rozmawiać, zadawać mu pytania, a nawet uczyć go nowych rzeczy na podstawie własnych dokumentów.

---

## Co potrafi Twój Asystent?

Twój asystent AI został wyposażony w kilka "supermocy", które sprawiają, że jest niezwykle użyteczny:

### 🧠 Inteligentna Rozmowa
Możesz z nim po prostu rozmawiać na dowolne tematy. Asystent rozumie kontekst rozmowy i stara się odpowiadać w sposób sensowny i spójny. Idealnie nadaje się do burzy mózgów, pisania tekstów czy po prostu jako towarzysz do rozmowy.

### 🌐 Wiedza z Internetu
Asystent potrafi samodzielnie zdecydować, że potrzebuje poszukać informacji w internecie, aby odpowiedzieć na Twoje pytanie. Dzięki temu jego wiedza jest zawsze aktualna i może odpowiadać na pytania dotyczące bieżących wydarzeń, znanych osób czy specyficznych faktów, unikając przy tym "halucynacji" (zmyślania odpowiedzi).

### 📄 Ekspert od Twoich Dokumentów
To jedna z potężnych funkcji. Możesz "nauczyć" asystenta treści swoich własnych dokumentów (np. plików PDF, notatek w formacie .txt). Po przesłaniu plików, agent automatycznie się z nimi zapozna i będzie gotowy do odpowiadania na pytania dotyczące informacji zawartych w tych dokumentach. Działa to jak Twoja osobista, inteligentna wyszukiwarka do własnych materiałów.

### 🛒 Zarządzanie Spiżarnią i Analiza Paragonów (NOWOŚĆ!)
Ta funkcja pozwala Ci na inteligentne zarządzanie zawartością Twojej spiżarni lub lodówki. Możesz:

1.  **Przesłać zdjęcie paragonu:** System automatycznie odczyta tekst z paragonu (OCR) i wyodrębni produkty, ich ilości i jednostki.
2.  **Monitorować przetwarzanie:** Zobaczysz status przetwarzania (np. "OCR w toku", "Ekstrakcja AI w toku").
3.  **Recenzować i edytować:** Przed zapisaniem do spiżarni, możesz sprawdzić i poprawić wyodrębnione dane. Masz pełną kontrolę nad nazwami produktów, ilościami, jednostkami, a nawet możesz dodać **daty przydatności do spożycia**!
4.  **Zarządzać spiżarnią:** Po zapisaniu, produkty trafiają do Twojej wirtualnej spiżarni. Możesz przeglądać jej zawartość w dowolnym momencie.
5.  **Pytać Asystenta:** Twój asystent AI potrafi odpowiedzieć na pytania dotyczące zawartości spiżarni, np. "Co mam w lodówce?", "Czy mam mleko?", "Ile mam jajek?".

### ☀️ Sprawdzanie Pogody
Jeśli zapytasz o pogodę w dowolnym mieście na świecie, asystent skorzysta z serwisu pogodowego, aby podać Ci aktualną prognozę.

---

## Wymagania Systemowe

### Minimalne:
- **Python 3.13+** 
- **4 GB RAM**
- **2 GB wolnego miejsca na dysku**
- **Przeglądarka internetowa** (Chrome, Firefox, Edge)

### Zalecane dla najlepszej wydajności:
- **Karta graficzna NVIDIA RTX** (dla przyspieszenia GPU)
- **8 GB RAM lub więcej**
- **CUDA 12.9+** (automatycznie wykrywane)

### 🚀 Optymalizacja GPU
Jeśli masz kartę NVIDIA RTX, aplikacja **automatycznie wykryje i wykorzysta GPU** do:
- Szybszego przetwarzania paragonów (EasyOCR)
- Przyspieszenia rozpoznawania tekstu
- Lepszej wydajności modeli AI

Sprawdź czy Twoja karta jest wykryta przez uruchomienie `nvidia-smi` w terminalu.

---

## Jak Zacząć? (Instrukcja krok po kroku)

Uruchomienie aplikacji jest bardzo proste.

1.  **Znajdź plik `start.sh`** w głównym folderze aplikacji.
2.  **Kliknij go dwukrotnie**. Na ekranie pojawi się czarne okno terminala z przewijającym się tekstem. To znak, że Twój asystent "budzi się do życia".
3.  **Poczekaj chwilę**. W terminalu pojawi się informacja podobna do tej: `Starting development server at http://127.0.0.1:8000/`. Oznacza to, że wszystko jest gotowe.
4.  **Otwórz przeglądarkę internetową** (np. Chrome, Firefox, Edge).
5.  W pasku adresu wpisz: `http://127.0.0.1:8000/` i naciśnij Enter.

To wszystko! Powinieneś teraz zobaczyć **nowoczesny dashboard** z przeglądem wszystkich funkcji aplikacji.

---

## Jak Korzystać z Aplikacji?

Aplikacja ma teraz **nowoczesny, intuicyjny dashboard** z łatwą nawigacją:

### 🏠 Dashboard - Strona Główna
Po wejściu na `http://127.0.0.1:8000/` zobaczysz:
- **Statystyki** - liczba aktywnych agentów, dokumentów, produktów w spiżarni
- **Karty funkcji** - kliknij w dowolną kartę aby przejść do odpowiedniej sekcji
- **Ostatnie paragony** - podgląd statusów przetwarzania paragonów
- **Górna nawigacja** - dostęp do wszystkich funkcji jednym kliknięciem

### 💬 Chat - Rozmowa z Asystentem
**Najnowocześniejszy interfejs czatu z AI:**
- **Bubble UI** - nowoczesny wygląd wiadomości z animacjami
- **Wskaźniki pisania** - widzisz gdy asystent pisze odpowiedź
- **Quick Actions** - szybkie pytania jednym kliknięciem
- **Smart Status** - bieżący status połączenia z agentem
- **Zalecamy agenta `bielik`** - ma dostęp do wszystkich narzędzi
- **GPU Optimization** - szybsze przetwarzanie na kartach RTX

### 📄 Dokumenty RAG - Twoja Baza Wiedzy
**Nowocześnie przeprojektowany system dokumentów:**
- **Drag & Drop Upload** - przeciągnij pliki bezpośrednio do przeglądarki
- **Karty dokumentów** - elegancki widok grid z ikonami typu pliku
- **Status badges** - sprawdzaj stan przetwarzania w czasie rzeczywistym
- **Smart Preview** - podgląd informacji o plikach przed wysyłaniem
- **Direct Chat Integration** - przejdź do czatu z pytaniem o dokument jednym kliknięciem
- **Walidacja kliencka** - sprawdzanie rozmiaru i typu pliku przed wysłaniem

### 🧾 Paragony - Automatyczna Analiza
**Teraz z przyspieszeniem GPU!** System szybciej przetwarza obrazy:
1. **Prześlij zdjęcie paragonu** - przeciągnij i upuść lub wybierz plik
2. **Automatyczne OCR** - rozpoznawanie tekstu z wykorzystaniem karty graficznej
3. **Ekstrakcja AI** - wyodrębnianie produktów, cen, ilości
4. **Przegląd i edycja** - sprawdź dane przed zapisem
5. **Dodanie dat przydatności** - kontroluj świeżość produktów

### 🏪 Spiżarnia - Zarządzanie Produktami
- **Przegląd zawartości** - co masz w domu
- **Daty przydatności** - kontrola świeżości
- **Integracja z AI** - pytaj asystenta o produkty
- Przykłady: "Co mam w lodówce?", "Czy mam mleko?", "Co wkrótce się zepsuje?"

### Panel Administracyjny (Dla Ciekawskich)

Pod adresem `http://127.0.0.1:8000/admin` znajduje się panel administracyjny. To jest "zaplecze" Twojej aplikacji. Możesz tam zobaczyć listę dostępnych agentów i ich konfigurację. Nie musisz tam nic zmieniać, aby aplikacja działała, ale warto wiedzieć, że takie miejsce istnieje.

---

## 🆕 Najnowsze Aktualizacje

### Wersja 2.0 (Sierpień 2025)
- ✅ **Nowy Dashboard** - Nowoczesny interfejs z przeglądem wszystkich funkcji
- ✅ **Przyspieszenie GPU** - Automatyczne wykrywanie i wykorzystanie kart NVIDIA RTX
- ✅ **Ulepszona Nawigacja** - Intuicyjne menu z emoji i responsive design  
- ✅ **Lepsze UX** - Karty funkcji, statystyki, smooth transitions
- ✅ **Optymalizacja EasyOCR** - Szybsze przetwarzanie paragonów na GPU
- ✅ **Responsywny Design** - Działa na wszystkich rozmiarach ekranów
- ✅ **Kompletny Redesign UI/UX** - Spójny system designowy z Tailwind CSS
- ✅ **Nowoczesny Chat Interface** - Bubble UI, wskaźniki pisania, quick actions
- ✅ **Ulepszone Formularze** - Drag & drop, walidacja, loading states
- ✅ **Glass Effects** - Efekty szkła, animacje, ripple effects na przyciskach
- ✅ **Toast Notifications** - Inteligentny system powiadomień
- ✅ **Animacje i Transycje** - Płynne przejścia między stanami

### Funkcje w przygotowaniu:
- 🔄 **Tryb ciemny** - dla osób preferujących dark mode
- 🔄 **Powiadomienia** - alerty o produktach z kończącą się przydatnością  
- 🔄 **Eksport danych** - backup spiżarni do plików CSV/JSON
- 🔄 **Więcej języków** - obsługa paragonów w różnych językach

---

## 📞 Pomoc i Wsparcie

Jeśli napotkasz problemy:
1. Sprawdź czy aplikacja działa pod `http://127.0.0.1:8000/`
2. Upewnij się że terminal z `./start.sh` jest nadal otwarty
3. Zrestartuj aplikację zatrzymując terminal (Ctrl+C) i uruchamiając ponownie

**Masz kartę RTX ale widzisz "Using CPU"?**
- Sprawdź `nvidia-smi` w terminalu
- Aplikacja automatycznie wykryje i użyje GPU przy następnym analizowaniu paragonu

---

## 🎉 Ciesz się swoim osobistym asystentem AI!

Teraz masz dostęp do pełni możliwości swojego inteligentnego asystenta. Eksploruj funkcje, przesyłaj dokumenty, analizuj paragony i rozmawiaj z AI - wszystko w jednym, bezpiecznym miejscu na Twoim komputerze.