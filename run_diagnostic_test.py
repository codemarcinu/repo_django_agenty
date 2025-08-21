# /run_diagnostic_test.py

import logging
import os
from pathlib import Path

import django
from django.contrib.auth import get_user_model
from django.core.files import File

# 1. Inicjalizacja Django (aby mieć dostęp do modeli i usług)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from chatbot.services.receipt_service import ReceiptService

# 2. Konfiguracja loggera, aby wszystko widzieć w konsoli
# To jest DODATKOWE logowanie, oprócz tego do pliku.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
diag_logger = logging.getLogger(__name__)

def run_pipeline_test(file_path: str, user_id: int):
    """
    Funkcja, która przeprowadza cały test end-to-end dla danego pliku paragonu.
    """
    diag_logger.info(f"--- ROZPOCZYNAM DIAGNOSTYCZNY TEST PIPELINE'U DLA PLIKU: {file_path} ---")

    receipt_file = Path(file_path)
    if not receipt_file.exists():
        diag_logger.error(f"Plik nie istnieje: {file_path}")
        return

    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
        diag_logger.info(f"Znaleziono użytkownika: {user.username}")
    except User.DoesNotExist:
        diag_logger.error(f"Użytkownik o ID {user_id} nie istnieje.")
        return

    # 3. Symulacja wgrania pliku i uruchomienie serwisu
    try:
        with receipt_file.open('rb') as f:
            django_file = File(f, name=receipt_file.name)

            # Pobieramy instancję głównego serwisu
            receipt_service = ReceiptService(user=user)

            # To jest serce testu - uruchamiamy cały proces
            diag_logger.info("Uruchamiam `receipt_service.process_receipt_file`...")
            receipt = receipt_service.process_receipt_file(django_file)
            diag_logger.info(f"Wstępne przetwarzanie zakończone. Utworzono obiekt paragonu o ID: {receipt.id}")
            diag_logger.info(f"Status początkowy: {receipt.status}, Krok przetwarzania: {receipt.processing_step}")
            diag_logger.info("Zadanie asynchroniczne zostało przekazane do Celery. Sprawdź logi Celery oraz `pipeline_diagnostic.log`.")

    except Exception:
        diag_logger.critical("Krytyczny błąd na etapie uruchamiania serwisu!", exc_info=True)

    diag_logger.info(f"--- ZAKOŃCZONO DIAGNOSTYCZNY TEST PIPELINE'U DLA PLIKU: {file_path} ---")


if __name__ == "__main__":
    # 4. Tutaj podajesz, co chcesz przetestować
    RECEIPT_TO_TEST = "paragony_do testów/20250626LIDL.png"
    TEST_USER_ID = 1  # ID użytkownika, do którego ma być przypisany paragon

    run_pipeline_test(RECEIPT_TO_TEST, TEST_USER_ID)
