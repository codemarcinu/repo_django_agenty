#!/usr/bin/env python
import asyncio
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from chatbot.agents import RouterAgent


async def test_routing_logic():
    print('=== TEST LOGIKI ROUTINGU ===')
    print()

    router = RouterAgent(config={'model': 'SpeakLeash/bielik-11b-v2.3-instruct:Q5_K_M'})

    # Test przypadki
    test_cases = [
        {
            'message': 'Jaka jest dzisiaj pogoda w Warszawie?',
            'expected': 'weather_service',
            'description': 'Pytanie o pogodę'
        },
        {
            'message': 'Wyszukaj najnowsze wiadomości o AI',
            'expected': 'web_search',
            'description': 'Wyszukiwanie w internecie'
        },
        {
            'message': 'Co mam w spiżarni?',
            'expected': 'pantry_management',
            'description': 'Zarządzanie spiżarnią'
        },
        {
            'message': 'Opowiedz mi o dokumencie XYZ',
            'expected': 'rag_search',
            'description': 'Pytanie o dokument'
        },
        {
            'message': 'Cześć, jak się masz?',
            'expected': 'general_conversation',
            'description': 'Powitanie'
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f'Test {i}: {test_case["description"]}')
        print(f'Wiadomość: "{test_case["message"]}"')
        print(f'Oczekiwane: {test_case["expected"]}')

        try:
            # Test tylko routingu - bez pełnego przetwarzania
            tools = [
                "'web_search': Służy do wyszukiwania aktualnych informacji w internecie, faktów, wiadomości lub odpowiadania na ogólne pytania.",
                "'weather_service': Służy do sprawdzania aktualnej prognozy pogody dla konkretnej lokalizacji.",
                "'rag_search': Służy do odpowiadania na pytania dotyczące treści dokumentów, które wcześniej przesłał użytkownik.",
                "'pantry_management': Służy do sprawdzania zawartości spiżarni, dodawania lub usuwania produktów.",
                "'general_conversation': Służy do prowadzenia zwykłej rozmowy, powitań, lub gdy żadne inne narzędzie nie jest odpowiednie."
            ]

            routing_prompt = (
                f"Mając do dyspozycji następujące narzędzia:\n{ chr(10).join(tools) }\n\n"
                f"Na podstawie historii rozmowy i ostatniej wiadomości od użytkownika, wybierz jedno, najbardziej odpowiednie narzędzie do użycia. "
                f"Odpowiedz tylko i wyłącznie nazwą narzędzia (np. 'web_search').\n\n"
                f"Historia: []\nOstatnia wiadomość: {test_case['message']}\n\nNarzędzie:"
            )

            routing_input = {'message': routing_prompt, 'history': []}
            decision_response = await router.process(routing_input)

            if decision_response.success:
                chosen_tool = decision_response.data.get('response', '').strip().replace("'", "").replace('"', "")
                print(f'Wybrane narzędzie: {chosen_tool}')

                if chosen_tool == test_case['expected']:
                    print('✅ POPRAWNE')
                else:
                    print('❌ NIEPOPRAWNE')

                print(f'Pełna odpowiedź: "{decision_response.data.get("response", "")}"')
            else:
                print(f'❌ BŁĄD: {decision_response.error}')

        except Exception as e:
            print(f'❌ WYJĄTEK: {e}')

        print('-' * 50)
        print()

if __name__ == '__main__':
    asyncio.run(test_routing_logic())
