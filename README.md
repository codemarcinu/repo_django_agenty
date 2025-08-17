# Agenty - Twój Inteligentny Asystent AI 🤖

**Agenty** to Twój osobisty asystent sztucznej inteligencji, który działa całkowicie offline na Twoim komputerze. 

✨ **Prywatność przede wszystkim** - Żadne Twoje dane nie opuszczają Twojego komputera  
🚀 **Przyspieszenie GPU** - Wykorzystuje kartę graficzną dla błyskawicznej pracy  
🧠 **Inteligentny i wszechstronny** - Pomaga z dokumentami, paragonami, pogodą i wieloma innymi zadaniami

---

## 🎯 Czym jest Agenty?

Wyobraź sobie asystenta, który:
- 💬 **Rozmawia z Tobą** w naturalny sposób, jak z przyjacielem
- 📄 **Czyta dokumenty** i odpowiada na pytania o ich zawartość
- 🛒 **Analizuje paragony** i automatycznie dodaje produkty do Twojej spiżarni
- 🌡️ **Sprawdza pogodę** i wyszukuje informacje w internecie
- 🏠 **Dba o Twoją spiżarnię** - przypomina o datach przydatności produktów

**Wszystko dzieje się na Twoim komputerze** - żadne dane nie są wysyłane do internetu!

### ✨ Co potrafi Agenty?

**💬 Inteligentna rozmowa**
- Rozmawia z Tobą po polsku w naturalny sposób
- Pamięta kontekst całej rozmowy
- Odpowiada na pytania z różnych dziedzin

**📄 Praca z dokumentami**
- Prześlij PDF, Word, lub zwykły tekst
- Zadawaj pytania o zawartość dokumentów
- Otrzymuj konkretne odpowiedzi z cytatami

**🛒 Inteligentne paragony**
- Zrób zdjęcie paragonu lub prześlij PDF
- System automatycznie rozpozna produkty i ceny
- Produkty trafiają do Twojej cyfrowej spiżarni

**🏠 Cyfrowa spiżarnia**
- Automatyczne przypomnienia o datach przydatności
- Sprawdzanie co masz w domu jednym pytaniem
- Historia zakupów i analiza wydatków

**🌍 Aktualne informacje**
- Sprawdzanie pogody dla dowolnego miasta
- Wyszukiwanie najświeższych informacji w internecie
- Odpowiedzi na pytania o bieżące wydarzenia

---

## 🏗️ Architektura Systemu

### Backend (Django 5.2.5)
```
agenty/
├── core/                    # Konfiguracja Django
│   ├── settings.py         # Główne ustawienia
│   ├── settings_dev.py     # Środowisko development
│   ├── settings_prod.py    # Środowisko produkcyjne
│   ├── celery.py          # Konfiguracja Celery
│   └── database_config.py  # Konfiguracja bazy danych
├── chatbot/                # Główna aplikacja
│   ├── api/               # REST API endpoints
│   │   ├── views.py       # Django views z @csrf_exempt
│   │   ├── drf_views.py   # Django REST Framework views
│   │   └── urls.py        # Routing API
│   ├── services/          # Logika biznesowa (Fat Model pattern)
│   │   ├── agent_factory.py    # Factory pattern dla agentów
│   │   ├── agents.py           # Implementacje agentów AI
│   │   ├── pantry_service.py   # Zarządzanie spiżarnią
│   │   ├── receipt_service.py  # Przetwarzanie paragonów
│   │   └── async_services.py   # Asynchroniczne operacje
│   ├── models.py          # Modele Django z business logic
│   ├── views.py           # Widoki HTML
│   ├── tasks.py           # Zadania Celery
│   └── templates/         # Szablony HTML z Tailwind CSS
└── requirements.txt       # Zależności Python
```

### Frontend (Vanilla JS + Tailwind CSS)
- **Responsive Design** - Działa na wszystkich urządzeniach
- **Modern Chat Interface** - Bubble UI z animacjami
- **Drag & Drop Upload** - Intuicyjne przesyłanie plików
- **Real-time Status** - Live updates statusów przetwarzania
- **Glass Effects** - Nowoczesne efekty wizualne

---

## 💻 Czy mój komputer poradzi sobie z Agenty?

### ✅ Każdy komputer może uruchomić Agenty
**Podstawowe wymagania (wystarczy dla wszystkich funkcji):**
- Komputer z systemem Windows, Mac lub Linux
- **8 GB pamięci RAM** (4GB minimum, ale 8GB zalecane dla płynności)
- **10 GB wolnego miejsca na dysku** (dla wszystkich modeli AI)
- Nowoczesna przeglądarka internetowa

### 🚀 Mam kartę graficzną NVIDIA? Świetnie!
**Jeśli masz kartę RTX (2000, 3000, 4000 series):**
- System automatycznie wykorzysta kartę graficzną
- Analiza paragonów będzie **3-5 razy szybsza**
- Modele AI będą działać **znacznie płynniej**
- **Wymagania te same:** ~10 GB na modele AI

**Nie masz karty NVIDIA?**
- Nie martw się! System automatycznie przełączy się na procesor
- Wszystkie funkcje będą działać, tylko trochę wolniej
- Analiza paragonu zajmie ~30 sekund zamiast ~10 sekund

### 🔧 Instalacja - super prosta!
System sam zainstaluje wszystko co potrzebne:
- **Model główny Bielik** (7.9GB) - polski GPT dla rozmowy
- **Model RAG mxbai-embed-large** (670MB) - dla analizy dokumentów  
- **Narzędzia OCR** (EasyOCR, Tesseract) - rozpoznawanie tekstu
- **Interfejs webowy** z nowoczesnym designem

**📥 Pobieranie modeli AI (automatyczne):**
- **Pierwszy start:** Pobieranie Bielik + mxbai (~8.6GB total)
- **Pierwszy dokument:** Pobranie modelu RAG (jeśli nie było wcześniej)
- **Pierwszy paragon:** Pobranie modeli OCR (~50MB)
- **Na szybkim internecie:** 15-20 minut całość
- **Modele zostają na zawsze** - następne uruchomienia: instant!

---

## 🚀 Jak uruchomić Agenty? (Krok po kroku)

### Krok 1: Pobierz i zainstaluj 📥
**Option A: Masz git? (dla programistów)**
```bash
git clone <repo-url>
cd agenty
```

**Option B: Pobierz ZIP (dla każdego)**
- Pobierz plik ZIP z kodem
- Rozpakuj do folderu na pulpicie
- Otwórz terminal/wiersz poleceń w tym folderze

### Krok 2: Przygotuj środowisko 🔧
```bash
# Zainstaluj Python jeśli nie masz (python.org)
# Następnie uruchom te polecenia:

python -m venv .venv
source .venv/bin/activate     # Na Mac/Linux
# lub
.venv\Scripts\activate        # Na Windows

pip install -r requirements.txt
```

### Krok 3: Podstawowa konfiguracja ⚙️
```bash
# Skopiuj plik przykładowej konfiguracji
cp .env.example .env

# Opcjonalnie: Dodaj klucz API pogody (za darmo na openweathermap.org)
# Edytuj plik .env i dodaj swój klucz w linii OPENWEATHERMAP_API_KEY=
```

### Krok 4: Uruchom! 🎉
```bash
# Najłatwiejszy sposób:
./start.sh

# System automatycznie:
# ✅ Przygotuje bazę danych
# ✅ Uruchomi serwer Ollama
# ✅ Pobierze model Bielik (7.9GB - pierwsza instalacja zajmie ~15 minut)
# ✅ Uruchomi serwer Django
```

**🕐 Pierwsze uruchomienie:**
- Pobieranie modelu Bielik: ~15 minut (szybki internet)
- Zobaczysz postęp pobierania w terminalu
- Modele: `SpeakLeash/bielik-11b-v2.3-instruct:Q5_K_M` + `mxbai-embed-large`
- **Pierwsze przesłanie dokumentu:** Dodatowe ~2 minuty na model RAG
- Po pobraniu wszystkie modele zostają na zawsze

**⚡ Kolejne uruchomienia:**
- Instant start - model już jest pobrany
- Uruchamianie zajmuje ~30 sekund

### Krok 5: Ciesz się! 🎊
Otwórz przeglądarkę i wejdź na:
- **🏠 Strona główna**: http://127.0.0.1:8000/
- **💬 Chat z AI**: http://127.0.0.1:8000/chat/
- **📊 Panel zarządzania**: http://127.0.0.1:8000/admin/

**🎯 Pierwsze kroki:**
1. Wejdź na stronę główną i zobacz dashboard
2. Kliknij "Chat" i porozmawiaj z AI
3. Spróbuj przesłać dokument lub zdjęcie paragonu
4. Sprawdź swoją spiżarnię

---

## 🧠 Modele sztucznej inteligencji w projekcie

### 🇵🇱 Model główny: Bielik
**Pełna nazwa:** `SpeakLeash/bielik-11b-v2.3-instruct:Q5_K_M`

**Dlaczego Bielik?**
- **Mówi po polsku!** - Stworzony specjalnie dla języka polskiego
- **Lokalny i prywatny** - Działa na Twoim komputerze, nie wysyła danych
- **Zoptymalizowany** - Wersja Q5_K_M zapewnia dobry balans szybkości i jakości
- **Rozmiar:** 7.9 GB (pobierany raz, zostaje na zawsze)

**Możliwości modelu:**
- Naturalne rozmowy po polsku
- Analiza dokumentów i tekstu
- Ekstrakcja danych z paragonów
- Integracja z narzędziami (pogoda, wyszukiwanie, spiżarnia)
- Rozumienie kontekstu rozmowy

### 🚀 Optymalizacja GPU
**Konfiguracja dla kart NVIDIA:**
- **num_gpu: 51** - Wykorzystanie wszystkich warstw GPU (RTX 3060/4060)
- **temperature: 0.1** - Niska temperatura dla spójnych wyników
- **num_ctx: 4096** - Okno kontekstu dla długich rozmów
- **num_predict: 1024** - Maksymalna długość odpowiedzi

**Wydajność:**
- **Z GPU (RTX):** Odpowiedzi w 3-8 sekund
- **Bez GPU (CPU):** Odpowiedzi w 15-30 sekund
- **VRAM:** ~1.2GB podczas pracy

### 📚 Inne modele w systemie

**🔗 RAG Embedding Model:**
- **Model:** `mxbai-embed-large` (przez Ollama)
- **Funkcja:** Przekształcanie tekstu na wektory dla wyszukiwania semantycznego
- **Rozmiar:** ~670MB
- **Automatyczne pobieranie:** Przy pierwszym przesłaniu dokumentu
- **Zastosowanie:** Analiza podobieństwa dokumentów, wyszukiwanie kontekstu

**👁️ EasyOCR Models (automatyczne pobieranie):**
- Model rozpoznawania tekstu polskiego (~25MB)
- Model rozpoznawania tekstu angielskiego (~25MB)
- Pobieranie przy pierwszej analizie paragonu

**📝 Tesseract Language Packs:**
- `pol` - Polski pakiet językowy
- `eng` - Angielski pakiet językowy
- Backup gdy EasyOCR nie jest dostępne

### 💾 Zarządzanie modelami
**Gdzie są przechowywane:**
- **Bielik + mxbai-embed-large:** `~/.ollama/models/` (Linux/Mac) lub `%USERPROFILE%\.ollama\models\` (Windows)
- **EasyOCR:** `~/.EasyOCR/model/`
- **ChromaDB (RAG):** `chroma_db/` w folderze projektu

**Zarządzanie przez Ollama:**
```bash
# Lista zainstalowanych modeli
ollama list

# Pobierz modele ręcznie
ollama pull SpeakLeash/bielik-11b-v2.3-instruct:Q5_K_M  # Model główny
ollama pull mxbai-embed-large                            # Model RAG

# Usuń modele (jeśli potrzebujesz miejsca)
ollama rm SpeakLeash/bielik-11b-v2.3-instruct:Q5_K_M
ollama rm mxbai-embed-large
```

**💡 Całkowity rozmiar wszystkich modeli:**
- Bielik (główny AI): ~7.9GB
- mxbai-embed-large (RAG): ~670MB  
- EasyOCR (OCR): ~50MB
- **Łącznie: ~8.6GB**

---

## 📋 Przewodnik dla użytkownika

### 💬 Jak rozmawiać z AI?

**Wejdź na chat i po prostu pisz!**
- "Cześć, jak się masz?" - Zwykła rozmowa
- "Jaka jest pogoda w Krakowie?" - Sprawdzi aktualną pogodę
- "Co wiem o sztucznej inteligencji?" - Wyszuka informacje w internecie
- "Co mam w spiżarni?" - Pokaże zawartość Twojej spiżarni

**AI automatycznie wie, czego potrzebujesz:**
- Rozpoznaje czy pytasz o pogodę, dokumenty, czy chcesz po prostu porozmawiać
- Pamięta kontekst rozmowy
- Odpowiada po polsku w naturalny sposób

### 📄 Jak przesłać dokument i pytać o niego?

**Krok 1: Prześlij dokument**
- Przeciągnij plik na stronę chat lub kliknij "Wybierz plik"
- Obsługiwane: PDF, Word (.docx), zwykły tekst (.txt)
- Maksymalny rozmiar: 10MB

**Krok 2: Poczekaj na przetworzenie**
- System automatycznie przeczyta dokument
- Zobaczysz komunikat "Dokument został przetworzony"

**Krok 3: Zadawaj pytania**
- "Co jest w tym dokumencie?"
- "Znajdź informacje o cenach"
- "Podsumuj główne punkty"
- "Czy jest tam coś o terminach?"

**AI będzie odpowiadać na podstawie treści dokumentu i podawać konkretne fragmenty!**

### 🛒 Jak analizować paragony? (Najfajniejsza funkcja!)

**Super prosty proces:**

**Krok 1: Zrób zdjęcie lub prześlij paragon**
- Zrób zdjęcie telefonem paragonu ze sklepu
- Lub zeskanuj paragon jako PDF
- Prześlij przez stronę z uploadem

**Krok 2: Magia się dzieje automatycznie ✨**
- System rozpoznaje tekst (wykorzystuje kartę graficzną dla szybkości!)
- AI wyciąga nazwy produktów, ceny, ilości
- Automatycznie dodaje produkty do Twojej cyfrowej spiżarni

**Krok 3: Sprawdź wyniki**
- Dostaniesz listę rozpoznanych produktów
- Możesz poprawić błędy jeśli jakieś są
- Kliknij "Zatwierdź" i produkty trafiają do spiżarni

**Co zyskujesz:**
- Nie musisz ręcznie przepisywać zakupów
- System pamięta daty przydatności
- Możesz pytać AI "Co mam w lodówce?"
- Dostaniesz przypomnienia o produktach kończących się

**🚀 Z kartą NVIDIA:** Analiza zajmuje ~10 sekund  
**💻 Na zwykłym procesorze:** Analiza zajmuje ~30 sekund

### 🏠 Twoja cyfrowa spiżarnia

**Jak to działa:**

**Automatyczne dodawanie:**
- Produkty z paragonów trafiają automatycznie do spiżarni
- System pamięta kiedy kupiłeś i kiedy się zepsuje
- Możesz też ręcznie dodać produkty

**Inteligentne przypomnienia:**
- "Mleko się kończy za 2 dni"
- "Jogurt przeterminowany - wyrzuć"
- "Za tydzień kończy Ci się ser"

**Rozmowa z AI o spiżarni:**
- "Co mam w lodówce?" - Dostaniesz pełną listę
- "Czy mam jeszcze mleko?" - Sprawdzi konkretny produkt
- "Co mi się kończy?" - Pokaże produkty o kończących się terminach
- "Co mogę ugotować?" - Zaproponuje przepisy na podstawie produktów

**Panel zarządzania:**
- Zobacz wszystkie produkty na jednej liście
- Edytuj daty, ilości, nazwy
- Oznacz jako zużyte lub wyrzucone
- Historia zakupów i wydatków

### 🌐 Integracje Zewnętrzne

**Web Search (DuckDuckGo):**
- Wyszukiwanie aktualnych informacji
- Bezpieczne API bez logowania
- Integracja z agentami AI

**Weather Service (OpenWeatherMap):**
- Bieżąca pogoda dla dowolnego miasta
- Prognoza 5-dniowa
- Integracja z chat interface

---

## 🔧 Konfiguracja Zaawansowana

### Cache System (Redis + Database Fallback)
```python
# Automatyczne przełączanie Redis ↔ Database
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',  # Jeśli Redis dostępne
        # lub
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',  # Fallback
    }
}
```

### Settings Management
- **settings.py** - Główny entry point z auto-detection
- **settings_dev.py** - Development (SQLite, Debug=True)
- **settings_prod.py** - Production (PostgreSQL, optimizations)

### API Architecture
- **Django Views** - Main API z @csrf_exempt
- **DRF Views** - Backup REST endpoints
- **Async Support** - Przygotowane do async operations

---

## 🧪 Testing

```bash
# Uruchom wszystkie testy
python manage.py test

# Testy z pytest
pytest

# Testy specyficzne
python manage.py test chatbot.tests.test_models
python manage.py test chatbot.tests.test_api
```

**Test Coverage:**
- Models business logic
- API endpoints
- Services layer
- OCR processing
- Agent functionality

---

## 📈 Monitoring i Wydajność

### GPU Monitoring
```bash
# Sprawdź dostępność GPU
nvidia-smi

# Monitor użycia podczas OCR
watch -n 1 nvidia-smi
```

### Django Debug Toolbar
- Dostępny w development mode
- SQL queries profiling
- Cache hits/misses
- Template rendering times

### Logging
```python
# Centralized logging w settings
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'django.log',
        },
    },
    'loggers': {
        'chatbot': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

---

## 🔒 Bezpieczeństwo

### Implemented Security Features
- **CSRF Protection** - Wszystkie formularze zabezpieczone
- **CORS Headers** - Konfigurowane dla API
- **File Upload Validation** - Sprawdzanie typu i rozmiaru plików
- **SQL Injection Protection** - Django ORM
- **XSS Prevention** - Template auto-escaping

### Production Security Checklist
- [ ] DEBUG = False
- [ ] Secure SECRET_KEY
- [ ] HTTPS redirect
- [ ] HSTS headers
- [ ] Secure cookies
- [ ] Database credentials w .env

---

## 🆘 Rozwiązywanie problemów

### "Agenty nie odpowiada" lub "Ładowanie..."

**Problem:** AI nie odpowiada na wiadomości
**Rozwiązanie:**
1. Sprawdź czy terminal/wiersz poleceń z `./start.sh` nadal działa
2. Jeśli widzisz błędy, naciśnij Ctrl+C i uruchom ponownie `./start.sh`
3. Pierwsze uruchomienie może trwać kilka minut (pobieranie modelu AI)

### "Błąd podczas przetwarzania paragonu"

**Problem:** Analiza paragonu się zawiesza
**Rozwiązanie:**
1. Sprawdź czy zdjęcie jest wyraźne i czytelne
2. Spróbuj z mniejszym rozmiarem pliku (max 10MB)
3. Jeśli masz kartę NVIDIA - sprawdź czy sterowniki są aktualne

### "Strona się nie ładuje" (http://127.0.0.1:8000)

**Problem:** Nie można otworzyć interfejsu
**Rozwiązanie:**
1. Sprawdź czy widzisz komunikat "Starting development server at http://127.0.0.1:8000/"
2. Upewnij się że żaden inny program nie używa portu 8000
3. Spróbuj z inną przeglądarką
4. Jeśli nadal nie działa - uruchom ponownie `./start.sh`

### "Model AI odpowiada tylko po angielsku"

**Problem:** AI nie rozumie polskiego lub odpowiada w złym języku
**Rozwiązanie:**
1. Sprawdź czy model Bielik jest załadowany: `ollama list`
2. Powinno być: `SpeakLeash/bielik-11b-v2.3-instruct:Q5_K_M`
3. Jeśli nie ma modelu, uruchom: `ollama pull SpeakLeash/bielik-11b-v2.3-instruct:Q5_K_M`
4. Poczekaj na pełne załadowanie (7.9GB)
5. Uruchom ponownie `./start.sh`

### "Pobieranie modelu przerwane lub błąd"

**Problem:** Model się nie pobiera lub pobieranie zostało przerwane
**Rozwiązanie:**
1. Sprawdź połączenie internetowe
2. Uruchom ręcznie: `ollama pull SpeakLeash/bielik-11b-v2.3-instruct:Q5_K_M`
3. Model można pobierać częściami - Ollama wznowi pobieranie
4. Potrzeba ~8GB wolnego miejsca na dysku
5. Na wolnym internecie może zająć do godziny

### "AI odpowiada bardzo wolno"

**Problem:** Odpowiedzi trwają bardzo długo (>1 minuta)
**Rozwiązanie:**
1. **Z kartą NVIDIA:** Sprawdź czy GPU jest wykorzystywane: `nvidia-smi`
2. **Bez karty NVIDIA:** To normalne - odpowiedzi mogą trwać 15-30 sekund
3. Sprawdź RAM - model potrzebuje ~8GB pamięci
4. Zamknij inne programy zużywające pamięć
5. Jeśli bardzo wolno - rozważ restart komputera

### "Gdzie znaleźć pomoc?"

**Szybkie sprawdzenie:**
1. Wejdź na http://127.0.0.1:8000/ - powinieneś zobaczyć dashboard
2. Sprawdź terminal - czy nie ma błędów w kolorze czerwonym
3. Spróbuj uruchomić ponownie: Ctrl+C, następnie `./start.sh`

**Nadal nie działa?**
- Sprawdź czy masz zainstalowany Python 3.13+
- Upewnij się że masz przynajmniej 4GB wolnej pamięci RAM
- Na Windows: uruchom terminal jako administrator

---

## 🚀 Development Roadmap

### ✅ Completed (v2.0)
- Modern Dashboard UI/UX
- GPU acceleration for OCR
- Fat Model, Thin View architecture
- Complete API refactoring
- CSRF token handling
- Redis cache with fallback
- Responsive design system

### 🔄 In Progress
- [ ] Dark mode support
- [ ] Real-time notifications
- [ ] Advanced pantry analytics
- [ ] Multi-language receipt support
- [ ] Voice interface integration

### 📋 Planned Features
- [ ] Mobile PWA support
- [ ] Advanced AI model integration
- [ ] Barcode scanning
- [ ] Shopping list generation
- [ ] Data export/import
- [ ] Multi-user support

---

## 📞 Support & Contributing

### Getting Help
1. Check status: http://127.0.0.1:8000/
2. Verify terminal z ./start.sh is running
3. Restart: Ctrl+C → ./start.sh
4. Check logs in Django admin

### Development Setup
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run with debug
DEBUG=True python manage.py runserver

# Pre-commit hooks
pre-commit install
```

### Contributing Guidelines
- Follow PEP 8 style guide
- Add tests for new features
- Update documentation
- Use meaningful commit messages
- Fat Model, Thin View pattern

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🎉 Wszystko gotowe - czas na zabawę!

**Twój osobisty asystent AI czeka na Ciebie!** 

### 🚀 Szybki start (3 kroki):
1. **Uruchom**: Otwórz terminal i wpisz `./start.sh`
2. **Otwórz**: Wejdź na http://127.0.0.1:8000/ w przeglądarce
3. **Eksploruj**: 
   - Kliknij **"Chat"** i porozmawiaj z AI
   - Prześlij **dokument** i zadawaj o niego pytania  
   - Zrób **zdjęcie paragonu** i zobacz jak system go analizuje
   - Sprawdź swoją **cyfrową spiżarnię**

### 💡 Pierwsze pytania do AI:
- "Cześć! Opowiedz mi o sobie"
- "Jaka jest pogoda w [twoje miasto]?"
- "Co wiesz o sztucznej inteligencji?"

### 📱 Co dalej?
- Prześlij swój pierwszy dokument (PDF, Word)
- Wypróbuj analizę paragonu ze sklepu
- Zbuduj swoją cyfrową spiżarnię
- Odkryj wszystkie możliwości w naturalnej rozmowie!

---

**🌟 Pamiętaj:** To jest Twój prywatny AI - wszystko dzieje się na Twoim komputerze!

**Miłego korzystania z Agenty!** 🤖✨