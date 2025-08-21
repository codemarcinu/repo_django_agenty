import logging
from asgiref.sync import async_to_sync
from celery import shared_task, states
from celery.exceptions import Ignore
from django.core.files.base import ContentFile
from django.db import transaction
import os
from pathlib import Path

from django.contrib.auth.models import User  # Dodaj ten import

# Dodaj importy
from pdf2image import convert_from_path
from PIL import Image

from chatbot.services.receipt_llm_service import ReceiptLLMService
from chatbot.services.receipt_parser import AdaptiveReceiptParser
from chatbot.services.vision_service import VisionService
from inventory.models import Receipt
from chatbot.services.ocr_service import OcrService
from chatbot.services.quality_gate_service import QualityGateService
from chatbot.services.product_matcher import ProductMatcher
from inventory.services.inventory_management_service import InventoryManagementService

# Inicjalizacja serwisów
ocr_service_instance = OcrService()
quality_gate_service_instance = QualityGateService(min_confidence=0.6, min_length=50)
llm_service_instance = ReceiptLLMService()
parser_service_instance = AdaptiveReceiptParser()
vision_service_instance = VisionService()
product_matcher_instance = ProductMatcher()
inventory_management_service_instance = InventoryManagementService()

logger = logging.getLogger(__name__)


def convert_pdf_to_image(pdf_path: str) -> str:
    """
    Converts the first page of a PDF to a PNG image.
    Saves the image in the same directory as the PDF.
    Returns the path to the newly created image.
    """
    logger.info(f"Converting PDF to image: {pdf_path}")
    path_obj = Path(pdf_path)
    # Zapisz obraz w tym samym katalogu, co oryginalny PDF
    output_directory = path_obj.parent
    # Użyj nazwy pliku PDF jako podstawy dla nazwy obrazu
    image_path_stem = path_obj.stem
    image_path = output_directory / f"{image_path_stem}.png"

    try:
        # Konwertuj tylko pierwszą stronę
        images = convert_from_path(pdf_path, first_page=1, last_page=1, output_folder=str(output_directory), fmt='png', output_file=image_path_stem)
        
        if images:
            # Zmień nazwę, jeśli to konieczne (pdf2image może dodawać numery stron)
            generated_image_path = images[0].filename
            if str(generated_image_path) != str(image_path):
                 os.rename(generated_image_path, image_path)

            logger.info(f"PDF converted successfully to: {image_path}")
            return str(image_path)
        else:
            logger.error(f"PDF conversion failed for {pdf_path}, no images were returned.")
            raise IOError(f"Could not convert PDF: {pdf_path}")
            
    except Exception as e:
        logger.error(f"Error converting PDF {pdf_path} to image: {e}", exc_info=True)
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def orchestrate_receipt_processing(self, receipt_id):
    """
    Celery task to orchestrate the receipt processing pipeline.
    """
    try:
        with transaction.atomic():
            # Użyj select_for_update, aby zablokować wiersz na czas transakcji
            receipt = Receipt.objects.select_for_update().get(pk=receipt_id)

            if receipt.status not in ['pending', 'retry']:
                logger.warning(f"Receipt {receipt_id} is not in a processable state (status: {receipt.status}). Skipping.")
                return

            receipt.update_status('processing', 'Orchestration started.')
            logger.info(f"▶️ STARTING ORCHESTRATION for Receipt ID: {receipt_id} (Attempt: {self.request.retries + 1})")

            # --- Krok konwersji PDF na obraz ---
            file_path = receipt.receipt_file.path
            if file_path.lower().endswith('.pdf'):
                try:
                    file_path = convert_pdf_to_image(file_path)
                    logger.info(f"Using converted image for processing: {file_path}")
                except Exception as e:
                    receipt.update_status('failed', f"Failed to convert PDF: {e}")
                    raise

            # 1. OCR
            logger.info(f"  [1/4] OCR | Receipt ID: {receipt_id}")
            receipt.update_status('processing', 'Step 1: OCR in progress.')
            ocr_text = ocr_service_instance.perform_ocr(file_path)
            logger.info(f"  OCR for Receipt ID: {receipt_id} completed.")

            # 2. Quality Gate
            logger.info(f"  [2/4] QUALITY GATE | Receipt ID: {receipt_id}")
            receipt.update_status('processing', 'Step 2: Quality Gate check.')
            quality_result = quality_gate_service_instance.validate_ocr_quality(ocr_text, ocr_service_instance.last_confidence)
            logger.info(f"  Paragon {receipt_id}: Wynik jakości OCR to {int(quality_result.score * 100)}%")

            parsed_data = None
            if quality_result.is_sufficient:
                # 3a. LLM Parsing (if quality is good)
                logger.info(f"  [3/4] PARSING (LLM) | Receipt ID: {receipt_id}. High quality, using LLMService.")
                receipt.update_status('processing', 'Step 3: Parsing data with LLM.')
                llm_response = llm_service_instance.process_text(ocr_text)
                parsed_data = parser_service_instance.parse(llm_response)
            else:
                # 3b. Vision Parsing (if quality is low)
                logger.warning(f"  [3/4] PARSING (VISION) | Receipt ID: {receipt_id}. Low quality, switching to VisionService.")
                receipt.update_status('processing', 'Step 3: Low OCR quality, parsing with VisionService.')
                parsed_data = async_to_sync(vision_service_instance.extract_data_from_image)(file_path)

            if not parsed_data or not parsed_data.items:
                 receipt.update_status('failed', 'Parsing failed or returned no items.')
                 raise ValueError("Parsing result is empty or invalid.")

            receipt.extracted_data = parsed_data.to_json()
            receipt.save()

            # 4. Product Matching and Inventory Update
            logger.info(f"  [4/4] MATCH & UPDATE | Receipt ID: {receipt_id}")
            receipt.update_status('processing', 'Step 4: Matching products and updating inventory.')
            
            # --- POPRAWKA ---
            # Pobierz obiekt użytkownika na podstawie user_id z paragonu
            user = User.objects.get(pk=receipt.user_id)
            
            # Utwórz instancję serwisu z poprawnym obiektem użytkownika
            inventory_management_service_instance = InventoryManagementService(user=user)
            product_matcher_instance = ProductMatcher(user=user)
            # --- KONIEC POPRAWKI ---
            
            matched_products = product_matcher_instance.match_products(parsed_data.items)
            inventory_management_service_instance.add_items_from_receipt(receipt, matched_products)
            
            receipt.update_status('completed', 'Successfully processed and inventory updated.')
            logger.info(f"✅ ORCHESTRATION COMPLETED for Receipt ID: {receipt_id}")

    except Receipt.DoesNotExist:
        logger.error(f"Receipt with ID {receipt_id} does not exist.")
        raise Ignore()
    except Exception as e:
        logger.critical(f"❌ CRITICAL ORCHESTRATION ERROR for Receipt ID: {receipt_id}: {e}", exc_info=True)
        if 'receipt' in locals() and isinstance(receipt, Receipt):
            receipt.update_status('failed', str(e))
        # Ponów próbę w przypadku błędu
        raise self.retry(exc=e)