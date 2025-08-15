# Agenty - Twój Inteligentny Asystent AI 🤖

Nowoczesna aplikacja Django z zaawansowanymi agentami AI, zarządzaniem spiżarnią, analizą paragonów i kompletnym systemem RAG (Retrieval-Augmented Generation).

---

## 🎯 Czym jest Agenty?

Agenty to kompleksowy system sztucznej inteligencji działający lokalnie na Twoim komputerze. Zapewnia pełną prywatność danych i oferuje zaawansowane funkcje AI bez konieczności wysyłania informacji do zewnętrznych serwisów.

### ✨ Kluczowe Funkcje

- **🧠 Inteligentne Agenty AI** - Specjalizowane agenty z różnymi kompetencjami
- **📄 System RAG** - Upload dokumentów i rozmowy o ich zawartości  
- **🧾 Analiza Paragonów** - OCR z przyspieszeniem GPU i ekstrakcja produktów
- **🏪 Zarządzanie Spiżarnią** - Inteligentne śledzenie produktów i dat przydatności
- **🌐 Wyszukiwanie Web** - Aktualne informacje z internetu
- **☀️ Prognoza Pogody** - Bieżące warunki pogodowe dla dowolnego miasta
- **💬 Nowoczesny Chat UI** - Responsywny interfejs z animacjami

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

## ⚙️ Wymagania Systemowe

### Minimalne
- **Python 3.13+**
- **4 GB RAM**
- **2 GB miejsca na dysku**
- **Przeglądarka** (Chrome, Firefox, Edge)

### Zalecane dla GPU
- **NVIDIA RTX 20xx/30xx/40xx**
- **8 GB RAM**
- **CUDA 12.9+** (auto-wykrywane)
- **10 GB miejsca** (dla modeli AI)

### 🚀 Przyspieszenie GPU
System automatycznie wykrywa i wykorzystuje karty NVIDIA dla:
- **EasyOCR** - Szybsze rozpoznawanie tekstu z paragonów
- **Przetwarzanie AI** - Przyspieszenie modeli językowych
- **Computer Vision** - Analiza obrazów

---

## 🚀 Instalacja i Uruchomienie

### 1. Przygotowanie środowiska
```bash
# Klonowanie repozytorium
git clone <repo-url>
cd agenty

# Tworzenie środowiska wirtualnego
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# lub .venv\Scripts\activate  # Windows

# Instalacja zależności
pip install -r requirements.txt
```

### 2. Konfiguracja
```bash
# Skopiuj plik środowiskowy
cp .env.example .env

# Edytuj .env file z własnymi ustawieniami:
# - DJANGO_SECRET_KEY
# - OPENWEATHERMAP_API_KEY
# - DATABASE_URL (opcjonalnie)
```

### 3. Uruchomienie
```bash
# Metoda 1: Użyj skryptu startowego (zalecane)
./start.sh

# Metoda 2: Manualne uruchomienie
python manage.py migrate
python manage.py runserver

# Opcjonalnie: Uruchom Celery dla zadań w tle
celery -A core worker --loglevel=info
```

### 4. Dostęp do aplikacji
- **Dashboard**: http://127.0.0.1:8000/
- **Chat**: http://127.0.0.1:8000/chat/
- **Admin Panel**: http://127.0.0.1:8000/admin/
- **API Docs**: http://127.0.0.1:8000/api/

---

## 📋 Główne Funkcjonalności

### 🤖 System Agentów AI

**Dostępni Agenci:**
- **bielik** - Agent główny z dostępem do wszystkich narzędzi
- **router** - Agent routingu i zarządzania rozmowami
- **Specialization agents** - Agenty specjalistyczne dla konkretnych zadań

**Capabilities:**
- `llm_chat` - Rozmowy w języku naturalnym
- `web_search` - Wyszukiwanie informacji w internecie
- `weather_check` - Sprawdzanie prognozy pogody
- `rag_query` - Odpowiedzi na podstawie przesłanych dokumentów
- `pantry_management` - Zarządzanie spiżarnią

### 📄 System RAG (Retrieval-Augmented Generation)

**Upload Dokumentów:**
- Obsługiwane formaty: PDF, TXT, DOCX, MD
- Maksymalny rozmiar: 10MB
- Automatyczne indeksowanie treści
- Vector search dla precyzyjnych odpowiedzi

**Funkcje:**
- Drag & drop interface
- Preview przed wysłaniem
- Status tracking przetwarzania
- Bezpośrednie pytania o dokumenty

### 🧾 Analiza Paragonów (OCR + AI)

**Proces przetwarzania:**
1. **Upload** - Prześlij zdjęcie paragonu
2. **OCR** - EasyOCR z przyspieszeniem GPU
3. **AI Extraction** - Wyodrębnienie produktów, cen, ilości
4. **Review** - Edycja i weryfikacja danych
5. **Save** - Dodanie do spiżarni z datami przydatności

**GPU Optimization:**
- Automatyczne wykrywanie kart NVIDIA
- 3-5x szybsze przetwarzanie na RTX
- Fallback na CPU gdy GPU niedostępne

### 🏪 Zarządzanie Spiżarnią

**Smart Pantry Management:**
- Automatyczne dodawanie produktów z paragonów
- Śledzenie dat przydatności do spożycia
- Alerty o produktach kończących się
- Integracja z AI (pytania o zawartość)
- Bulk operations (dodawanie, edycja, usuwanie)

**Business Logic w modelach:**
```python
# Przykłady użycia
item.is_expired()           # Sprawdź czy produkt się zepsuł
item.days_until_expiry()    # Ile dni do przydatności
PantryItem.get_expiring_soon(7)  # Produkty kończące się w 7 dni
```

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

## 🐛 Troubleshooting

### Częste Problemy

**1. CSRF Errors w API**
```python
# Fixed with @csrf_exempt decorators
@method_decorator(csrf_exempt, name='dispatch')
class ConversationCreateView(View):
    # ...
```

**2. Redis Connection Issues**
```python
# Auto-fallback to database cache
try:
    r = redis.Redis(host='127.0.0.1', port=6379, db=1)
    r.ping()
    # Use Redis
except:
    # Use database cache
```

**3. GPU Not Detected**
```bash
# Check NVIDIA drivers
nvidia-smi

# Install CUDA toolkit if needed
# Application will fallback to CPU automatically
```

**4. OCR Processing Stuck**
```bash
# Check Celery worker status
celery -A core inspect active

# Restart worker if needed
celery -A core worker --loglevel=info
```

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

## 🎉 Ready to Start!

Twój inteligentny asystent AI jest gotowy do pracy! 

1. **Uruchom**: `./start.sh`
2. **Otwórz**: http://127.0.0.1:8000/
3. **Eksploruj**: Dashboard → Chat → Upload dokumentów → Analizuj paragony

Miłego korzystania z Agenty! 🚀