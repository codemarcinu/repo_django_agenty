# W pliku test_e2e_dashboard.py
import pytest
import re
from playwright.sync_api import Page, expect

# Adres URL Twojej lokalnej aplikacji
BASE_URL = "http://127.0.0.1:8000"
# Dane logowania testowego użytkownika
TEST_USER_EMAIL = "test@example.com"  # Zmień na email testowego użytkownika
TEST_USER_PASSWORD = "twojehaslo"      # Zmień na hasło testowego użytkownika


def test_dashboard_loads_without_errors(page: Page):
    """
    Test E2E weryfikujący:
    1. Poprawne logowanie użytkownika.
    2. Załadowanie strony dashboardu.
    3. Brak krytycznych błędnych JavaScript w konsoli przeglądarki.
    4. Poprawność odpowiedzi API (status 200 OK) dla kluczowych zasobów.
    5. Widoczność kluczowych elementów na stronie.
    """
    
    # Przechowuje błędy napotkane podczas testu
    console_errors = []
    failed_api_requests = []

    # Nasłuchuj na błędy w konsoli JS i dodawaj je do listy
    page.on("console", lambda msg: console_errors.append(f"CONSOLE ERROR: {msg.text}") if msg.type == "error" else None)
    
    # Nasłuchuj na odpowiedzi z serwera i sprawdzaj statusy
    def check_response(response):
        # Sprawdzamy kluczowe endpointy API
        if "/api/" in response.url and response.status != 200:
            failed_api_requests.append(f"API FAILED ({response.status}): {response.url}")

    page.on("response", check_response)

    # --- 1. Logowanie ---
    page.goto(f"{BASE_URL}/admin/login/?next=/inventory/dashboard/") # Przejdź do strony logowania admina
    
    # Wprowadź dane logowania
    page.fill('input[name="username"]', TEST_USER_EMAIL)
    page.fill('input[name="password"]', TEST_USER_PASSWORD)
    
    # Kliknij przycisk logowania i poczekaj na nawigację do dashboardu
    page.click('input[type="submit"]')
    page.wait_for_url(f"{BASE_URL}/inventory/dashboard/")
    
    # Sprawdź, czy jesteśmy na właściwej stronie
    expect(page).to_have_title(re.compile("Dashboard"))
    print("Login successful, navigated to dashboard.")

    # --- 2. Weryfikacja Dashboardu ---
    
    # Poczekaj chwilę, aby dać czas na załadowanie dynamicznych komponentów (np. zapytań AJAX)
    page.wait_for_timeout(3000)

    # Sprawdź, czy główny kontener strony jest widoczny
    dashboard_container = page.locator("#dashboard-container")
    expect(dashboard_container).to_be_visible()
    print("Dashboard container is visible.")

    # Sprawdź, czy kontener na wykresy istnieje
    charts_container = page.locator("#charts-container")
    expect(charts_container).to_be_visible()
    print("Charts container is visible.")

    # --- 3. Asercje końcowe ---
    
    # Sprawdź, czy nie było błędów w konsoli JS
    assert not console_errors, "\n".join(console_errors)

    # Sprawdź, czy wszystkie kluczowe zapytania API zakończyły się sukcesem
    assert not failed_api_requests, "\n".join(failed_api_requests)

    print("E2E test passed successfully: Dashboard loaded without console errors and API failures.")
