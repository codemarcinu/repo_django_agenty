# Agenty - Inteligentny System Zarządzania Domem 🤖

**Agenty** to zaawansowany system sztucznej inteligencji działający lokalnie na Twoim komputerze. Łączy nowoczesne technologie AI z praktycznym zarządzaniem gospodarstwem domowym.

✨ **Prywatność przede wszystkim** - Wszystkie dane pozostają na Twoim komputerze  
🚀 **GPU Acceleration** - Wykorzystuje karty graficzne NVIDIA dla maksymalnej wydajności  
🧠 **Multi-Agent Architecture** - Inteligentny system routingu i specjalizowanych agentów AI  
📊 **Advanced Analytics & Dashboard** - Zaawansowane analizy wydatków, konsumpcji i wizualizacje  
🛒 **Complete Receipt Processing Pipeline** - Kompletny pipeline: OCR → Parse → Match → Inventory  
🗄️ **Unified Inventory System** - Kompleksowy system zarządzania zapasami z alertami i śledzeniem dat ważności

---

## 🎯 System Capabilities

**Agenty** to kompleksowy ekosystem AI składający się z:

### 💬 Intelligent Conversational AI
- Naturalne rozmowy w języku polskim z wykorzystaniem modelu Bielik
- Zaawansowany system routingu zapytań do specjalistycznych agentów
- Pamięć kontekstu i personalizacja interakcji
- Wsparcie dla zapytań wielomodalnych (tekst + obrazy)

### 📄 Document Processing & RAG
- Przetwarzanie dokumentów PDF, Word, i tekstowych
- System RAG (Retrieval-Augmented Generation) z ChromaDB
- Semantyczne wyszukiwanie w dokumentach z wykorzystaniem embeddings
- Zaawansowane indeksowanie i kategoryzacja treści

### 🛒 Complete Receipt Processing Pipeline
- **Advanced OCR System**: EasyOCR (GPU-accelerated) + Tesseract fallback with confidence scoring
- **Unified Receipt Model**: Single Receipt model consolidating all processing stages
- **AI-Powered Parsing**: LLM-based structured data extraction using Qwen models
- **Intelligent Product Matching**: Fuzzy matching with product catalog and automatic alias creation
- **Async Background Processing**: Celery-based pipeline with real-time status updates
- **Granular Status Tracking**: Complete pipeline visibility (uploaded→OCR→parsing→matching→inventory→review)
- **Error Handling & Alerts**: Comprehensive error tracking with critical error notifications

### 🏠 Unified Inventory Management System
- **Complete Data Models**: Receipt, ReceiptLineItem, Product, Category, InventoryItem, ConsumptionEvent
- **Smart Expiry Management**: Automatic expiry date calculation based on category metadata
- **Multi-Location Storage**: Fridge, freezer, pantry, cabinet with consumption tracking
- **Advanced Analytics**: Spending patterns, consumption heatmaps, waste tracking
- **Intelligent Alerts**: Expiry warnings, low stock notifications, reorder point management
- **Batch Processing**: Support for batch receipt processing with transaction safety

### 🌐 External Integrations
- Weather API (OpenWeatherMap) z intelligent routing
- Web search (DuckDuckGo) dla aktualnych informacji
- Modular architecture dla łatwej rozbudowy integracji

**Wszystko dzieje się offline** - maksymalna prywatność i kontrola nad danymi!

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

## 🏗️ System Architecture

### Backend Stack (Django 5.2.5 + Advanced Services)
```
agenty/
├── core/                           # Core Django Configuration
│   ├── settings.py                # Auto-detecting settings module
│   ├── settings_dev.py            # Development (SQLite, Debug)
│   ├── settings_prod.py           # Production (PostgreSQL optimized)
│   ├── celery.py                  # Celery configuration with Valkey/Redis
│   └── database_config.py         # Multi-database configuration
├── chatbot/                       # Main AI Application
│   ├── api/                      # REST API Layer
│   │   ├── views.py              # Core API endpoints
│   │   ├── receipt_views.py      # Receipt processing endpoints
│   │   ├── tests.py              # Comprehensive API tests
│   │   ├── tests_inventory.py    # Inventory API tests
│   │   └── urls.py               # API routing and versioning
│   ├── services/                 # Business Logic Layer (35+ services)
│   │   ├── agent_factory.py      # Multi-agent creation factory
│   │   ├── agents.py             # Specialized AI agent implementations
│   │   ├── model_router.py       # AI model routing and selection
│   │   ├── unified_receipt_processor.py # NEW: Unified receipt processing pipeline
│   │   ├── receipt_parser.py     # Receipt text parsing with LLM
│   │   ├── product_matcher.py    # Advanced product matching with fuzzy logic
│   │   ├── inventory_service.py  # Inventory management business logic
│   │   ├── async_ocr_service.py  # Async OCR processing service
│   │   ├── hybrid_ocr_service.py # EasyOCR + Tesseract hybrid
│   │   ├── cache_service.py      # Multi-tier caching (Redis + DB)
│   │   ├── async_services.py     # Async operation handlers
│   │   ├── websocket_notifier.py # Real-time notifications
│   │   ├── monitoring.py         # System health monitoring
│   │   └── optimized_queries.py  # Database query optimization
│   ├── models.py                 # Fat Models: Agent, Document, Conversation, Message
│   ├── tasks.py                  # Celery background tasks
│   ├── tasks_alerts.py           # Alert and notification tasks
│   ├── views.py                  # HTML template views
│   ├── views_monitoring.py       # Monitoring dashboard views
│   └── templates/                # Modern responsive UI templates
├── inventory/                     # NEW: Dedicated Inventory App
│   ├── models.py                 # UNIFIED: Receipt, ReceiptLineItem, Product, Category, InventoryItem, ConsumptionEvent
│   ├── views.py                  # Dashboard with analytics and visualizations
│   ├── templates/inventory/      # Complete inventory UI components
│   ├── tests_performance.py     # Performance optimization tests
│   └── urls.py                   # Inventory routing
└── requirements.txt              # Production dependencies (45+ packages)
```

### AI & Machine Learning Infrastructure
- **Ollama Integration**: Local LLM serving with GPU optimization (qwen2:7b, mistral:7b, qwen2.5vl:7b)
- **Multi-Agent System**: Router agents with specialized task routing
- **ChromaDB**: Vector database for RAG and semantic search
- **Advanced OCR Pipeline**: EasyOCR (GPU) + Tesseract fallback with confidence scoring
- **Receipt AI Processing**: LLM-powered structured data extraction from OCR text
- **Product Matching**: Fuzzy matching with aliases and barcode support

### Frontend Architecture (Modern Responsive Design)
- **Vanilla JavaScript**: High-performance client-side logic
- **Tailwind CSS**: Utility-first responsive design system
- **Glass Morphism UI**: Modern glassmorphism effects and animations
- **Real-time Updates**: WebSocket-ready status monitoring
- **Progressive Enhancement**: Works across all device types

---

## 💻 Czy mój komputer poradzi sobie z Agenty?

### ✅ Każdy komputer może uruchomić Agenty
**Podstawowe wymagania (wystarczy dla wszystkich funkcji):**
- Komputer z systemem Linux (CachyOS, Ubuntu, Debian, Arch)
- **8 GB pamięci RAM** (4GB minimum, ale 8GB zalecane dla płynności)
- **15 GB wolnego miejsca na dysku** (dla wszystkich modeli AI)
- Python 3.13+ z venv
- Valkey/Redis dla cache'owania i kolejek zadań

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
- **Pierwszy start:** Pobieranie qwen2:7b + mistral:7b + qwen2.5vl:7b (~15GB total)
- **Pierwszy dokument:** Pobranie modelu RAG (jeśli nie było wcześniej)
- **Pierwszy paragon:** Pobranie modeli OCR (~50MB)
- **Na szybkim internecie:** 25-30 minut całość
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

### Krok 4: Uruchom System! 🎉
```bash
# Automated startup with optimization
./start.sh

# System automatycznie wykonuje:
# ✅ Sprawdza i konfiguruje środowisko GPU (NVIDIA)
# ✅ Uruchamia Ollama z optymalizacją dla RTX 3060/4060
# ✅ Sprawdza dostępność modeli AI (qwen2:7b, qwen2.5vl:7b, mistral:7b)
# ✅ Konfiguruje Valkey/Redis dla cache'owania i kolejek
# ✅ Stosuje migracje bazy danych (SQLite dev/PostgreSQL prod)
# ✅ Uruchamia Celery worker dla zadań w tle
# ✅ Startuje Django development server (127.0.0.1:8000)
```

**🕐 First Installation Timeline:**
- **Models Download**: ~25 minutes for full model suite (21GB on fast internet)
- **Core Models**: qwen2:7b (~4.5GB), qwen2.5vl:7b (~4.9GB), mistral:7b (~4.1GB)
- **RAG Model**: mxbai-embed-large (~670MB) - downloaded on first document upload
- **OCR Models**: EasyOCR language packs (~50MB) - downloaded on first receipt scan
- **Progress Monitoring**: Real-time download progress in terminal

**⚡ Subsequent Starts:**
- **Cold Start**: ~30 seconds (all models cached)
- **GPU Detection**: Automatic CUDA optimization
- **Service Health Checks**: Ollama, Redis, Celery status verification
- **Background Operation**: All services run in background after startup

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

## 🧠 AI Models & Technology Stack

### 🎯 Current Model Configuration

**Primary Models (Manual download required):**
- **qwen2:7b** (~4.5GB) - Main conversational AI model
- **qwen2.5vl:7b** (~4.9GB) - Vision-language model for receipt and document analysis  
- **mistral:7b** (~4.1GB) - Alternative model for specialized tasks
- **mxbai-embed-large** (~670MB) - RAG embeddings for semantic document search

**Download Commands:**
```bash
ollama pull qwen2:7b
ollama pull qwen2.5vl:7b
ollama pull mistral:7b
ollama pull mxbai-embed-large
```

### 🚀 GPU Optimization & Performance

**Ollama Configuration (Optimized for RTX 3060/4060):**
```bash
export OLLAMA_MAX_LOADED_MODELS=1     # Memory optimization
export OLLAMA_NUM_PARALLEL=1          # Single-threaded for stability
export OLLAMA_GPU_OVERHEAD=0          # Minimal GPU overhead
export CUDA_VISIBLE_DEVICES=0         # Primary GPU only
```

**Performance Benchmarks:**
- **RTX 3060**: 5-10 seconds response time, ~3GB VRAM usage (optimized for 8GB VRAM)
- **RTX 4060+**: 3-8 seconds response time, ~2.5GB VRAM usage  
- **CPU Fallback**: 20-45 seconds response time, ~8GB RAM usage

### 🔧 Multi-Backend OCR System

**Primary OCR Backend (EasyOCR):**
- Auto-downloads Polish and English language models (~50MB total)
- GPU-accelerated when NVIDIA card available
- High accuracy for printed text recognition
- Confidence scoring for quality assessment

**Fallback OCR Backend (Tesseract):**
- System Tesseract with `pol` and `eng` language packs
- CPU-based processing as backup
- Reliable for low-quality images

### 🗄️ Vector Database & RAG Architecture

**ChromaDB Integration:**
- Local vector database stored in `chroma_db/`
- Automatic document chunking and embedding
- Semantic similarity search capabilities
- Persistent storage with incremental updates

**RAG Pipeline:**
1. Document upload and preprocessing
2. Text chunking with overlap optimization
3. Embedding generation via mxbai-embed-large
4. Vector storage in ChromaDB
5. Query-time semantic retrieval
6. Context-aware response generation

### 💾 Model Management & Storage

**Storage Locations:**
- **Ollama Models**: `~/.ollama/models/` (Linux/Mac), `%USERPROFILE%\.ollama\models\` (Windows)
- **EasyOCR Cache**: `~/.EasyOCR/model/`
- **ChromaDB Vectors**: `./chroma_db/` (project directory)
- **Tesseract Data**: System-managed language packs

**Model Operations:**
```bash
# Check model status
ollama list

# Download specific models
ollama pull qwen2:7b
ollama pull qwen2.5vl:7b
ollama pull mistral:7b
ollama pull mxbai-embed-large

# Remove models to save space
ollama rm <model_name>

# Monitor GPU usage during inference
nvidia-smi -l 1
```

**💡 Total Storage Requirements:**
- Core models (qwen2:7b + qwen2.5vl:7b + mistral:7b): ~14GB
- RAG embeddings (mxbai-embed-large): ~670MB
- OCR models (EasyOCR): ~50MB
- Application code + database + logs: ~500MB
- **Total: ~15GB for full capabilities**

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

**Krok 2: Kompletny pipeline automatyczny ✨**
- **OCR**: System rozpoznaje tekst (GPU-accelerated dla szybkości!)
- **AI Parsing**: LLM wyciąga strukturalne dane (produkty, ceny, ilości)
- **Product Matching**: Inteligentne dopasowywanie do katalogu produktów
- **Inventory Update**: Automatyczne dodanie do spiżarni z datami ważności
- **Real-time Status**: Otrzymujesz powiadomienia na każdym etapie

**Krok 3: Przegląd i zatwierdzenie**
- System automatycznie przeanalizuje paragon
- Otrzymujesz powiadomienie o zakończeniu przetwarzania
- Możesz przejrzeć rozpoznane produkty w dashboard
- Produkty automatycznie trafiają do spiżarni z obliczonymi datami ważności

**Co zyskujesz:**
- Nie musisz ręcznie przepisywać zakupów
- System pamięta daty przydatności
- Możesz pytać AI "Co mam w lodówce?"
- Dostaniesz przypomnienia o produktach kończących się

**🚀 Z kartą NVIDIA:** Kompletny pipeline zajmuje ~15-30 sekund  
**💻 Na zwykłym procesorze:** Kompletny pipeline zajmuje ~45-60 sekund  
**⚡ Real-time Updates:** Otrzymujesz powiadomienia na każdym etapie przetwarzania

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

**Advanced Analytics Dashboard:**
- Zobacz wszystkie produkty z filtrowaniem i wyszukiwaniem
- Heatmapy konsumpcji i wzorce wydatkowania
- Analiza top kategorii i trendów zakupowych
- Wizualizacje aktywności i alertów dotyczących dat ważności
- Historia zakupów z detalami finansowymi
- Raporty waste'u i optymalizacji zakupów

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

## 🔧 Advanced System Configuration

### ⚡ Intelligent Caching Architecture
```python
# Auto-fallback caching with Redis + Database
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',  # Primary
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CONNECTION_POOL_KWARGS': {'max_connections': 20}
        }
    },
    'database_fallback': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',  # Fallback
        'LOCATION': 'agenty_cache_table',
    }
}
```

### 🏗️ Multi-Environment Settings Management
- **settings.py** - Smart auto-detection entry point
- **settings_dev.py** - Development (SQLite, Debug, Hot reload)
- **settings_prod.py** - Production (PostgreSQL, Redis, Optimizations)
- **Environment Detection** - Automatic based on DJANGO_SETTINGS_MODULE

### 🌐 Advanced API Architecture
```python
# Fat Service Layer with Dependency Injection
chatbot/services/
├── agent_factory.py      # Agent creation and management
├── model_router.py       # AI model selection and routing  
├── receipt_processor_v2.py # Enhanced receipt processing pipeline
├── cache_service.py      # Intelligent caching abstraction
├── async_services.py     # Async operations with proper error handling
└── inventory_service.py  # Business logic for inventory management
```

### 🚀 Performance Optimizations
- **GPU Memory Management**: Dynamic model loading/unloading
- **Database Indexing**: Optimized indexes for high-frequency queries
- **Async Processing**: Celery for background tasks, async views for real-time
- **Caching Strategy**: Multi-layer caching (Redis, database, in-memory)
- **Query Optimization**: Select_related and prefetch_related throughout

### 🔒 Production-Ready Features
- **Health Checks**: Comprehensive system monitoring endpoints
- **Error Handling**: Centralized error processing with severity levels
- **Logging**: Structured logging with rotation and filtering
- **Security**: CSRF protection, input validation, SQL injection prevention
- **Monitoring**: Built-in metrics collection for system performance

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

## 📊 Current Development Status (v4.0)

### ✅ Production-Ready Features
- **🏗️ Multi-Agent Architecture** - Router-based agent system with specialized task routing and model selection
- **⚡ GPU-Optimized Pipeline** - RTX 3060/4060 optimized NVIDIA GPU acceleration with memory management
- **🛒 Complete Receipt Processing Pipeline** - Unified OCR (EasyOCR+Tesseract) → LLM Parse → Fuzzy Match → Inventory
- **📦 Unified Inventory Management** - Single Receipt model with complete product lifecycle tracking
- **🔄 Async Background Processing** - Celery tasks with real-time WebSocket notifications and error alerts
- **💾 Multi-Tier Intelligent Caching** - Redis primary with database fallback and optimized queries
- **🗄️ Advanced RAG Document System** - ChromaDB vector database with semantic search and context management
- **📱 Modern Analytics Dashboard** - Responsive UI with consumption heatmaps, spending analytics, and visualizations
- **🔒 Enterprise Security** - Comprehensive CSRF protection, file validation, and secure processing
- **🧪 Comprehensive Testing Suite** - 40+ test files covering all components with performance benchmarking

### ✅ Latest Implementation Achievements (Recent Commits)
- **✅ Unified Receipt Model** - Complete consolidation of receipt processing into single model
- **✅ Advanced Analytics Dashboard** - Spending patterns, consumption heatmaps, and inventory insights  
- **✅ Real-time Status Updates** - WebSocket-based progress monitoring for receipt processing
- **✅ Intelligent Product Matching** - Fuzzy matching with automatic alias creation and confidence scoring
- **✅ Critical Error Alert System** - Automated error notifications with detailed diagnostics
- **✅ Performance Optimization** - Query optimization and database indexing for large datasets

### 🎯 Future Enhancements
- **🌙 Dark Mode Support** - Complete UI theme system with user preferences
- **📱 Progressive Web App** - Mobile-first PWA implementation with offline capabilities
- **🤖 AI Recipe Suggestions** - Smart meal planning based on current inventory
- **📦 Barcode Scanning** - Mobile barcode scanner integration for manual product entry
- **🔔 Enhanced Push Notifications** - Mobile push notifications for expiry alerts
- **📊 Advanced Waste Analytics** - Food waste tracking and optimization suggestions

### 🚀 Long-term Vision
- **🔗 IoT Integration** - Smart home device connectivity
- **🛒 Shopping Automation** - AI-powered shopping list generation
- **📦 Supplier Integration** - Direct ordering and price comparison
- **🧠 Predictive Analytics** - Consumption prediction and optimization
- **🌐 Cloud Sync** - Optional cloud backup and synchronization

---

## 📞 Support & Contributing

### Getting Help
1. Check status: http://127.0.0.1:8000/
2. Verify terminal z ./start.sh is running
3. Restart: Ctrl+C → ./start.sh
4. Check logs in Django admin

### 🛠️ Development Environment Setup
```bash
# Setup development environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install all dependencies including dev tools
pip install -r requirements.txt

# Install additional development tools
pip install black ruff mypy pytest-django coverage

# Setup pre-commit hooks (optional)
pre-commit install

# Run development server with debug
DJANGO_SETTINGS_MODULE=core.settings_dev python manage.py runserver

# Run tests
python manage.py test
# or with pytest
pytest
```

### 📋 Contributing Guidelines
- **Code Style**: Follow PEP 8, use Black for formatting, Ruff for linting
- **Architecture**: Maintain Fat Model, Thin View pattern with service layer
- **Testing**: Add unit and integration tests for new features
- **Documentation**: Update README and docstrings for public APIs
- **Commits**: Use conventional commit messages with semantic prefixes
- **Security**: Never commit sensitive data, validate all inputs

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🎉 Ready to Explore? Start Your AI Journey!

**Your intelligent home management system is ready!** 

### 🚀 Quick Start Guide (3 Simple Steps):
1. **🔥 Launch**: Open terminal and run `./start.sh`
2. **🌐 Access**: Open http://127.0.0.1:8000/ in your browser
3. **✨ Explore**: 
   - **💬 Chat Interface**: Start conversation with multi-agent AI system
   - **📄 Document Upload**: Upload PDFs/Word docs for intelligent analysis
   - **🛒 Receipt Scanner**: Take photo of receipt for automatic inventory management
   - **📊 Analytics Dashboard**: Monitor your household consumption patterns

### 🗣️ Try These Sample Conversations:
- "Cześć! Pokaż mi możliwości systemu" *(Show me system capabilities)*
- "Jaka jest pogoda dzisiaj w Krakowie?" *(Weather check)*
- "Przeanalizuj ten dokument" *(Document analysis)*
- "Co mam w spiżarni?" *(Inventory check)*
- "Które produkty się kończą?" *(Expiry monitoring)*

### 🔍 Advanced Features to Explore:
- **🤖 Multi-Agent Routing**: Watch AI automatically select specialized agents
- **📊 Analytics Dashboard**: Explore spending patterns and consumption trends  
- **🗄️ RAG Document Search**: Upload documents and ask specific questions
- **⚡ GPU Acceleration**: Experience blazing-fast receipt processing
- **💾 Intelligent Caching**: Notice improved response times on repeated queries

### 🎯 Power User Tips:
- **Monitor Performance**: Check `logs/` directory for system insights
- **GPU Usage**: Run `nvidia-smi` to monitor GPU utilization during processing
- **Model Management**: Use `ollama list` to see loaded AI models
- **Background Services**: All processing happens asynchronously via Celery

---

**🔒 Privacy First:** Everything runs locally on your machine - no data leaves your computer!

**🚀 Welcome to the future of intelligent home management!** 🏠✨