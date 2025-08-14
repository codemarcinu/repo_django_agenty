# chatbot/weather_service.py
import logging
import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

def get_weather(city: str) -> str:
    """
    Fetches weather data for a city from OpenWeatherMap API.
    """
    api_key = getattr(settings, 'OPENWEATHERMAP_API_KEY', None)
    if not api_key:
        return "Error: OpenWeatherMap API key not configured."

    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric&lang=pl"
    
    logger.info(f"Requesting weather for '{city}' from OpenWeatherMap.")
    try:
        with httpx.Client() as client:
            response = client.get(url)
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

            data = response.json()
            
            main = data.get('main', {})
            weather_desc = data.get('weather', [{}])[0].get('description', 'Brak opisu')
            
            formatted_weather = (
                f"Pogoda w mieście {data.get('name', city)}:\n"
                f"- Temperatura: {main.get('temp', 'N/A')}°C (odczuwalna: {main.get('feels_like', 'N/A')}°C)\n"
                f"- Opis: {weather_desc.capitalize()}\n"
                f"- Ciśnienie: {main.get('pressure', 'N/A')} hPa\n"
                f"- Wilgotność: {main.get('humidity', 'N/A')} %"
            )
            return formatted_weather

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.warning(f"City not found on OpenWeatherMap: {city}")
            return f"Nie znaleziono miasta o nazwie '{city}'."
        elif e.response.status_code == 401:
            logger.error("Invalid OpenWeatherMap API key.")
            return "Błąd: Nieprawidłowy klucz API do serwisu pogodowego."
        else:
            logger.error(f"HTTP error fetching weather for {city}: {e}")
            return f"Wystąpił błąd HTTP podczas pobierania pogody: {e}"
    except Exception as e:
        logger.error(f"An unexpected error occurred in get_weather: {e}", exc_info=True)
        return "Wystąpił nieoczekiwany błąd podczas sprawdzania pogody."
