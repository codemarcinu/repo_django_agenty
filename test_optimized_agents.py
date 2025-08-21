#!/usr/bin/env python
"""
Test script for optimized agent system.
Tests all functionality including fallback mechanisms.
"""
import asyncio
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from chatbot.agents import RouterAgent


async def test_all_functionality():
    print('=== TEST ZOPTYMALIZOWANEGO SYSTEMU AGENTÓW ===')
    print()

    router = RouterAgent(config={'model': 'SpeakLeash/bielik-11b-v2.3-instruct:Q5_K_M'})

    # Test cases covering all functionalities
    test_cases = [
        {
            'message': 'Jaka jest dzisiaj pogoda w Warszawie?',
            'expected_tool': 'weather_service',
            'description': 'Test weather service'
        },
        {
            'message': 'Wyszukaj najnowsze wiadomości o sztucznej inteligencji',
            'expected_tool': 'web_search',
            'description': 'Test web search'
        },
        {
            'message': 'Co mam w spiżarni?',
            'expected_tool': 'pantry_management',
            'description': 'Test pantry management'
        },
        {
            'message': 'Opowiedz mi o dokumencie projektu',
            'expected_tool': 'rag_search',
            'description': 'Test RAG search'
        },
        {
            'message': 'Cześć, jak się masz?',
            'expected_tool': 'general_conversation',
            'description': 'Test general conversation'
        },
        {
            'message': 'Czy pada deszcz?',
            'expected_tool': 'weather_service',
            'description': 'Test rule-based weather routing'
        },
        {
            'message': 'Znajdź informacje o Python',
            'expected_tool': 'web_search',
            'description': 'Test rule-based web search routing'
        }
    ]

    success_count = 0
    total_tests = len(test_cases)

    for i, test_case in enumerate(test_cases, 1):
        print(f'Test {i}: {test_case["description"]}')
        print(f'Wiadomość: "{test_case["message"]}"')
        print(f'Oczekiwane narzędzie: {test_case["expected_tool"]}')

        try:
            # Test routing logic
            user_message = test_case["message"]

            # Check if rule-based routing works
            chosen_tool_rule = router._rule_based_routing(user_message)
            if chosen_tool_rule:
                chosen_tool = chosen_tool_rule
                routing_method = "rule-based"
            else:
                # Fallback to LLM routing
                chosen_tool = await router._llm_based_routing(user_message)
                routing_method = "LLM-based"

            print(f'Wybrane narzędzie: {chosen_tool} ({routing_method})')

            if chosen_tool == test_case['expected_tool']:
                print('✅ ROUTING - POPRAWNY')
                routing_success = True
            else:
                print('❌ ROUTING - NIEPOPRAWNY')
                routing_success = False

            # Test full processing with fallback
            print('Testowanie pełnego przetwarzania...')
            input_data = {
                'message': user_message,
                'history': []
            }

            response = await router.process(input_data)

            if response.success:
                print('✅ PRZETWARZANIE - SUKCES')
                print(f'Odpowiedź: "{response.data.get("response", "")[:100]}..."')
                processing_success = True
            else:
                print('❌ PRZETWARZANIE - BŁĄD')
                print(f'Błąd: {response.error}')
                processing_success = False

            if routing_success and processing_success:
                success_count += 1
                print('✅ TEST CAŁKOWICIE ZALICZONY')
            else:
                print('❌ TEST CZĘŚCIOWO LUB CAŁKOWICIE NIEZALICZONY')

        except Exception as e:
            print(f'❌ WYJĄTEK: {e}')

        print('-' * 60)
        print()

    # Final summary
    print('=== PODSUMOWANIE ===')
    print(f'Zaliczone testy: {success_count}/{total_tests}')
    print(f'Wskaźnik sukcesu: {(success_count/total_tests)*100:.1f}%')

    if success_count == total_tests:
        print('🎉 WSZYSTKIE TESTY ZALICZONE!')
    elif success_count > total_tests * 0.7:
        print('✅ Większość testów zaliczona - system działa poprawnie')
    else:
        print('⚠️  Wymagana jest dodatkowa optymalizacja')

async def test_fallback_system():
    print('\n=== TEST SYSTEMU FALLBACK ===')
    print()

    # Test with invalid Ollama URL to trigger fallback
    router = RouterAgent(config={
        'model': 'nonexistent-model',
        'ollama_url': 'http://invalid-url:99999'
    })

    test_message = "Cześć, jak się masz?"
    input_data = {'message': test_message, 'history': []}

    print('Testowanie fallback z nieprawidłowym URL Ollama...')
    print(f'Wiadomość: "{test_message}"')

    try:
        response = await router.process(input_data)

        if response.success:
            print('✅ FALLBACK DZIAŁA')
            print(f'Odpowiedź: "{response.data.get("response", "")}"')
            print(f'Agent: {response.data.get("agent", "N/A")}')
            print(f'Typ odpowiedzi: {response.data.get("response_type", "N/A")}')

            if response.metadata.get('fallback_used'):
                print('✅ Potwierdzono użycie fallback')
            else:
                print('⚠️  Fallback może nie być oznaczony poprawnie')
        else:
            print('❌ FALLBACK NIE DZIAŁA')
            print(f'Błąd: {response.error}')

    except Exception as e:
        print(f'❌ WYJĄTEK W TEŚCIE FALLBACK: {e}')

    print('-' * 60)

if __name__ == '__main__':
    asyncio.run(test_all_functionality())
    asyncio.run(test_fallback_system())
