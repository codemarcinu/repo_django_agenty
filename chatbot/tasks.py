# chatbot/tasks.py

import logging
from celery import shared_task
from django.conf import settings
from asgiref.sync import async_to_sync

# --- IMPORTY GLOBALNE ---
# Na górze zostawiamy TYLKO i WYŁĄCZNIE modele Django i podstawowe biblioteki.
# ŻADNYCH importów z chatbot.services.*
from inventory.models import Receipt

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def orchestrate_receipt_processing(self, receipt_id: int):
    """
    Główne zadanie Celery orkiestrujące cały proces przetwarzania paragonu.
    """
    # --- IMPORTY LOKALNE (Wewnątrz zadania) ---
    from chatbot.services.ocr_service import ocr_service
    from chatbot.services.quality_gate_service import QualityGateService
    from chatbot.services.registry import receipt_parser
    from chatbot.services.vision_service import VisionService
    from chatbot.services.product_matcher import ProductMatcher
    from chatbot.services.inventory_service import InventoryService
    from inventory.tasks import run_mistral_ocr_and_save_sample_task # New import

    logger.info(f"▶️ STARTING ORCHESTRATION for Receipt ID: {receipt_id} (Attempt: {self.request.retries + 1})")
    
    receipt = None
    try:
        receipt = Receipt.objects.get(id=receipt_id)
        
        # --- KROK 1: OCR ---
        logger.info(f"  [1/4] OCR | Receipt ID: {receipt_id}")
        receipt.mark_as_processing(step="ocr_in_progress")
        # Używamy zaimportowanej instancji 'ocr_service' i poprawnej metody 'process_file'
        ocr_result = ocr_service.process_file(receipt.receipt_file.path)
        receipt.raw_text = ocr_result.to_dict()
        receipt.save(update_fields=['raw_text', 'updated_at'])
        logger.info(f"  OCR for Receipt ID: {receipt_id} completed.")

        # --- KROK 2: BRAMKA JAKOŚCI ---
        logger.info(f"  [2/4] QUALITY GATE | Receipt ID: {receipt_id}")
        quality_gate = QualityGateService(ocr_result)
        quality_score = quality_gate.calculate_quality_score()
        logger.info(f"  Paragon {receipt_id}: Wynik jakości OCR to {quality_score}%")

        # --- KROK 3: PARSOWANIE (STANDARDOWE LUB WIZYJNE) ---
        if quality_score >= settings.OCR_QUALITY_THRESHOLD:
            logger.info(f"  [3/4] PARSING (LLM) | Receipt ID: {receipt_id}")
            receipt.mark_as_processing(step="parsing")
            raw_text = ocr_result.text # Używamy .text zamiast get_full_text()
            parsed_data = receipt_parser.parse(raw_text)
        else:
            logger.warning(f"  [3/4] PARSING (VISION) | Receipt ID: {receipt_id}. Low quality, switching to VisionService.")
            receipt.mark_as_processing(step="vision_parsing")
            vision_service_instance = VisionService()
            parsed_data = async_to_sync(vision_service_instance.extract_data_from_image)(receipt.receipt_file.path)
            # Trigger Mistral OCR for training sample
            run_mistral_ocr_and_save_sample_task.delay(receipt_id=receipt.id) # New line
        
        receipt.parsed_data = parsed_data.dict()
        receipt.save(update_fields=['parsed_data', 'updated_at'])

        # --- KROK 4: DOPASOWANIE PRODUKTÓW I AKTUALIZACJA INWENTARZA ---
        logger.info(f"  [4/4] MATCH & UPDATE | Receipt ID: {receipt_id}")
        # Inicjalizacja pozostałych serwisów
        product_matcher = ProductMatcher()
        inventory_service = InventoryService(user=receipt.user)
        
        # Uruchomienie logiki dopasowania i aktualizacji
        final_data = inventory_service.update_inventory_from_parsed_data(parsed_data, product_matcher)
        receipt.extracted_data = final_data 
        
        receipt.mark_as_completed()
        logger.info(f"✅ SUCCESSFULLY PROCESSED Receipt ID: {receipt_id}")

    except Exception as e:
        logger.critical(f"❌ CRITICAL ORCHESTRATION ERROR for Receipt ID: {receipt_id}: {e}", exc_info=True)
        if receipt:
            receipt.mark_as_error(str(e))
        raise self.retry(exc=e)
