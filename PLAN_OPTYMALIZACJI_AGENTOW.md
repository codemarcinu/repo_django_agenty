# 📋 Plan Optymalizacji Systemu Agentów

## 🔍 Analiza Obecnego Stanu

### Identyfikowane Problemy:

1. **RouterAgent ma dostęp do weather_service, ale problem występuje na poziomie Ollama**
   - ✅ Agent "bielik" ma typ "router" 
   - ✅ RouterAgent ma metodę `_execute_weather_service`
   - ✅ Weather service działa poprawnie
   - ❌ Ollama server nie działa (`Could not connect to Ollama server at http://localhost:11434`)

2. **Problemy z parsowaniem odpowiedzi routingu**
   - Model zwraca długie wyjaśnienia zamiast krótkich nazw narzędzi
   - Potrzebna lepsza instrukcja i parsing

3. **Błędy w dostępie do bazy danych z kontekstu async**
   - `You cannot call this from an async context` przy PantryItem
   - Potrzebne `sync_to_async` lub refactor

4. **Przestarzała biblioteka duckduckgo_search**
   - Warning o rename do `ddgs`
   - Potrzebna aktualizacja dependencies

## 🎯 Plan Działań

### Priorytet 1: Krytyczne (Blokuje podstawowe funkcje)

#### 1.1 Naprawa połączenia z Ollama
- **Problem**: Brak połączenia z serwerem Ollama
- **Rozwiązanie**: 
  - Dodać fallback na inne modele (OpenAI API, Anthropic)
  - Ulepszyć error handling z graceful degradation
  - Dodać health check dla Ollama przed wysłaniem zapytania

#### 1.2 Fix async/sync database calls
- **Problem**: Błędy przy dostępie do PantryItem z async kontekstu
- **Rozwiązanie**: 
  - Użyć `sync_to_async` wrapper
  - Lub przepisać na async database queries (`aget`, `afilter`)

### Priorytet 2: Ważne (Wpływa na jakość działania)

#### 2.1 Ulepszona logika routingu
- **Problem**: Model zwraca długie teksty zamiast nazw narzędzi
- **Rozwiązanie**:
  - Zmienić prompt na few-shot learning z przykładami
  - Dodać lepsze post-processing odpowiedzi
  - Wprowadzić timeout dla decyzji routingu

#### 2.2 Aktualizacja zależności
- **Problem**: Przestarzałe biblioteki
- **Rozwiązanie**:
  - Aktualizować duckduckgo_search → ddgs
  - Przetestować kompatybilność

### Priorytet 3: Usprawnienia (Nice-to-have)

#### 3.1 Inteligentniejszy Router Agent
- **Aktualnie**: Prosty LLM call do wyboru narzędzia
- **Cel**: Hybrydowy system z rules + ML
- **Rozwiązanie**:
  - Dodać rule-based routing dla prostych case'ów
  - Używać LLM tylko dla skomplikowanych decyzji
  - Cache'ować popularne wzorce routingu

#### 3.2 Lepsze zarządzanie agentami
- **Cel**: Dynamiczne ładowanie i konfiguracja agentów
- **Rozwiązanie**:
  - Hot-reload agentów z bazy danych
  - A/B testing różnych konfiguracji
  - Metryki wydajności agentów

#### 3.3 Context Management
- **Cel**: Inteligentne zarządzanie kontekstem rozmowy
- **Rozwiązanie**:
  - Summarization długich historii
  - Context switching między narzędziami
  - Memory management dla agentów

## 🛠️ Szczegółowe Implementacje

### Fix 1: Fallback Model System

```python
class ImprovedRouterAgent(RouterAgent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fallback_models = [
            'ollama',
            'openai_gpt_3_5',
            'anthropic_claude',
            'simple_rules'  # rule-based fallback
        ]
    
    async def process_with_fallback(self, input_data):
        for model in self.fallback_models:
            try:
                return await self.process_with_model(input_data, model)
            except Exception as e:
                logger.warning(f"Model {model} failed: {e}")
                continue
        
        # Ultimate fallback - simple rules
        return await self.rule_based_routing(input_data)
```

### Fix 2: Async Database Wrapper

```python
from asgiref.sync import sync_to_async

async def get_pantry_items_async():
    return await sync_to_async(list)(PantryItem.objects.all())

async def get_pantry_item_async(name):
    return await sync_to_async(PantryItem.objects.filter)(name__icontains=name).afirst()
```

### Fix 3: Few-shot Router Prompt

```python
ROUTER_EXAMPLES = """
Przykłady:

Wiadomość: "Jaka jest pogoda w Krakowie?"
Narzędzie: weather_service

Wiadomość: "Wyszukaj informacje o nowym iPhone"
Narzędzie: web_search

Wiadomość: "Co mam w lodówce?"
Narzędzie: pantry_management

Wiadomość: "Opowiedz o dokumencie ABC.pdf"
Narzędzie: rag_search

Wiadomość: "Jak się masz?"
Narzędzie: general_conversation
"""
```

## 📊 Metryki Sukcesu

### KPI do śledzenia:
1. **Accuracy routingu**: % poprawnie wybranych narzędzi
2. **Response time**: Średni czas odpowiedzi agenta
3. **Error rate**: % błędów w działaniu agentów
4. **User satisfaction**: Jakość odpowiedzi (manual review)

### Testy akceptacyjne:
- [ ] Agent "bielik" prawidłowo odpowiada na pytania o pogodę
- [ ] Wszystkie rodzaje zapytań (weather, search, rag, pantry) działają
- [ ] System gracefully degraduje przy niedostępności Ollama
- [ ] Brak błędów async/sync w logach
- [ ] Response time < 5s dla 95% zapytań

## 🔄 Harmonogram

### Tydzień 1: Krytyczne poprawki
- [ ] Fix połączenia Ollama + fallback
- [ ] Naprawa async database calls  
- [ ] Podstawowe testy integracyjne

### Tydzień 2: Jakość routingu
- [ ] Ulepszona logika routingu
- [ ] Few-shot prompting
- [ ] Aktualizacja dependencies

### Tydzień 3: Usprawnienia
- [ ] Inteligentniejszy router
- [ ] Lepsze error handling
- [ ] Metryki i monitoring

### Tydzień 4: Testowanie i finalizacja
- [ ] Comprehensive testing
- [ ] Performance optimization
- [ ] Dokumentacja

## 🎯 Końcowa Wizja

**Idealny System Agentów powinien:**

1. **Być niezawodny**: 99%+ uptime, graceful fallbacks
2. **Być szybki**: Odpowiedzi w <3s, inteligentne cache'owanie
3. **Być dokładny**: 95%+ accuracy w wyborze narzędzi
4. **Być skalowalny**: Łatwo dodawać nowe agenty i narzędzia
5. **Być monitorowalny**: Pełne logi, metryki, alerting

**Rezultat**: Użytkownik zawsze otrzymuje poprawną, szybką odpowiedź, niezależnie od tego czy pyta o pogodę, dokumenty, czy zawartość spiżarni.