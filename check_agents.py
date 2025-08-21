#!/usr/bin/env python
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from chatbot.models import Agent

print('=== AGENCI W BAZIE DANYCH ===')
print()

agents = Agent.objects.all()
if not agents:
    print('❌ Brak agentów w bazie danych')
else:
    for agent in agents:
        status = '✅' if agent.is_active else '❌'
        print(f'{status} {agent.name}:')
        print(f'   Typ: {agent.agent_type}')
        print(f'   Aktywny: {agent.is_active}')
        print(f'   Możliwości: {agent.capabilities}')
        print(f'   Config: {agent.config}')
        print(f'   Persona: {agent.persona_prompt[:100]}...' if len(agent.persona_prompt) > 100 else f'   Persona: {agent.persona_prompt}')
        print()

print('=== ANALIZA PROBLEMU Z POGODĄ ===')
print()

bielik = agents.filter(name='bielik').first()
if bielik:
    print(f'Agent "bielik" - typ: {bielik.agent_type}')
    print(f'Możliwości: {bielik.capabilities}')

    if bielik.agent_type == 'router':
        print('✅ Agent ma typ "router" - powinien mieć dostęp do weather_service')
    else:
        print('❌ Agent nie ma typu "router" - brak dostępu do narzędzi pogodowych')

    # Sprawdź, czy RouterAgent ma implementację weather_service
    from chatbot.agents import RouterAgent
    router = RouterAgent()
    if hasattr(router, '_execute_weather_service'):
        print('✅ RouterAgent ma metodę _execute_weather_service')
    else:
        print('❌ RouterAgent nie ma metody _execute_weather_service')

    # Sprawdź weather_service
    try:
        from chatbot.weather_service import get_weather
        test_weather = get_weather('Warszawa')
        if test_weather and 'error' not in test_weather.lower():
            print('✅ Weather service działa poprawnie')
            print(f'   Test Warszawa: {test_weather[:100]}...')
        else:
            print('❌ Weather service zwraca błąd')
            print(f'   Error: {test_weather}')
    except Exception as e:
        print(f'❌ Problem z weather_service: {e}')
else:
    print('❌ Nie znaleziono agenta "bielik"')
