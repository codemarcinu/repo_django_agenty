# W pliku chatbot/tasks.py - dodaj debugging

from celery import shared_task
import logging
import re
import os

from inventory.models import Receipt

from .models import Document
from .rag_processor import rag_processor
from .services.exceptions_receipt import (
    DatabaseError,
    MatchingError,
    OCRError,
    ParsingError,
)

logger = logging.getLogger(__name__)


@shared_task
def process_document_task(document_id):
    try:
        rag_processor.process_document(document_id)
        logger.info(f"Document {document_id} processed successfully by Celery task.")
    except Exception as e:
        logger.error(
            f"Error processing document {document_id} by Celery task: {e}",
            exc_info=True,
        )
        Document.objects.filter(id=document_id).update(status="error")


@shared_task(
    bind=True,
    autoretry_for=(OCRError, ParsingError, MatchingError, DatabaseError),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    retry_backoff=True,
    retry_backoff_max=600,
    task_time_limit=1200,
)
def orchestrate_receipt_processing(self, receipt_id: int):
    """
    Orchestrates the full, multi-step receipt processing pipeline.
    """
    from .services.ocr_backends import OCRResult
    from .services.ocr_service import ocr_service
    from .services.quality_gate_service import QualityGateService
    from .services.receipt_parser import get_receipt_parser, AdaptiveReceiptParser
    from .services.receipt_service import get_receipt_service
    from .services.vision_service import VisionService
    from .services.basic_parser import BasicReceiptParser

    logger.info(f"▶️ STARTING ORCHESTRATION for Receipt ID: {receipt_id} (Attempt: {self.request.retries + 1})")

    try:
        receipt = Receipt.objects.get(id=receipt_id)

        # --- KROK 1: OCR ---
        logger.info(f" [1/4] OCR | Receipt ID: {receipt_id}")
        receipt.mark_as_processing(step="ocr_in_progress")
        ocr_result = ocr_service.process_file(receipt.receipt_file.path)

        if not ocr_result.success:
            receipt.mark_as_error(f"OCR failed: {ocr_result.error_message}")
            raise OCRError(f"OCR failed for receipt {receipt_id}")

        receipt.raw_ocr_text = ocr_result.text
        receipt.raw_text = ocr_result.to_dict()
        receipt.save()

        # 🔍 DEBUGGING: Pokaż surowy tekst OCR
        logger.info(f"🔍 OCR RAW TEXT for Receipt {receipt_id}:")
        logger.info(f"--- START OCR TEXT ---")
        logger.info(ocr_result.text)
        logger.info(f"--- END OCR TEXT ---")

        # --- KROK 2: QUALITY GATE ---
        logger.info(f" [2/4] QUALITY GATE | Receipt ID: {receipt_id}")
        receipt.mark_as_processing(step="quality_gate")

        if not isinstance(ocr_result, OCRResult):
            raise TypeError(f"OCRService.process_document() must return OCRResult instance")

        quality_gate = QualityGateService(ocr_result)
        quality_score = quality_gate.calculate_quality_score()
        logger.info(f"Paragon {receipt_id}: Wynik jakości OCR to {quality_score}")

        # --- KROK 3: PARSING ---
        logger.info(f" [3/4] PARSING | Receipt ID: {receipt_id}")
        receipt.mark_as_processing(step="parsing_in_progress")

        # Spróbuj Vision Service (jeśli działa)
        vision_result = None
        try:
            vision_service = VisionService()
            vision_result = vision_service.analyze_receipt(receipt.receipt_file.path)
            
            if vision_result and vision_result.get('success'):
                logger.info(f"✅ Vision analysis successful for receipt {receipt_id}")
                logger.info(f"Vision result: {vision_result.get('extracted_text', '')[:200]}...")
            else:
                logger.warning(f"Vision service failed for receipt {receipt_id}, using text parsing")
        except Exception as e:
            logger.error(f"Vision service error for receipt {receipt_id}: {e}")

        # Główny parser
        parser_service = AdaptiveReceiptParser(default_parser=BasicReceiptParser())
        
        # 🔍 DEBUGGING: Sprawdź co parser otrzymuje
        logger.info(f"🔍 PARSER INPUT for Receipt {receipt_id}:")
        logger.info(f"OCR Text length: {len(ocr_result.text)} chars")
        logger.info(f"First 300 chars: {ocr_result.text[:300]}...")

        parser_result = parser_service.parse(ocr_result.text, vision_result)

        # 🔍 DEBUGGING: Sprawdź wynik parsera
        logger.info(f"🔍 PARSER OUTPUT for Receipt {receipt_id}:")
        logger.info(f"Parser result: {parser_result}")
        logger.info(f"Parser result type: {type(parser_result)}")

        if parser_result:
            # Konwersja do słownika jeśli potrzebna
            extracted_dict = parser_result if isinstance(parser_result, dict) else parser_result.dict()
            
            # 🔍 DEBUGGING: Sprawdź wyodrębnione produkty  
            products = extracted_dict.get('products', [])
            logger.info(f"🔍 EXTRACTED PRODUCTS for Receipt {receipt_id}: {len(products)} products")
            for i, product in enumerate(products[:3]):  # Pokaż pierwsze 3
                logger.info(f"  Product {i+1}: {product}")

            receipt.extracted_data = extracted_dict
            receipt.mark_llm_done(extracted_dict)
        else:
            logger.error(f"❌ Parser returned empty result for receipt {receipt_id}")
            # FALLBACK: Spróbuj prostego parsowania regex
            fallback_products = simple_text_parser(ocr_result.text)
            if fallback_products:
                logger.info(f"🔄 Fallback parser found {len(fallback_products)} products")
                fallback_dict = {"products": fallback_products, "store_name": "", "total": 0}
                receipt.extracted_data = fallback_dict
                receipt.mark_llm_done(fallback_dict)
            else:
                receipt.mark_as_error("Parsing failed: No data extracted from OCR.")
                raise ParsingError(f"No data extracted for receipt {receipt_id}")

        # --- KROK 4: MATCHING ---
        logger.info(f" [4/4] MATCHING | Receipt ID: {receipt_id}")
        receipt_service = get_receipt_service()
        receipt_service.process_receipt_matching(receipt_id)

        logger.info(f"✅ ORCHESTRATION COMPLETED for Receipt ID: {receipt_id}.")

    except Exception as e:
        logger.error(f"❌ ORCHESTRATION ERROR for Receipt ID: {receipt_id}: {e}", exc_info=True)
        try:
            receipt_to_update = Receipt.objects.get(id=receipt_id)
            receipt_to_update.mark_as_error(f"Critical error: {e}")
        except Receipt.DoesNotExist:
            logger.error(f"Could not find receipt {receipt_id} to mark as error.")
        raise

def simple_text_parser(text: str) -> list:
    """
    Prosty fallback parser używający regex do znajdowania produktów.
    """
    
    products = []
    lines = text.split('n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Szukaj wzorców: "produkt cena" lub "produkt liczba cena"
        # Przykład: "Mleko 4,99" lub "Chleb 1 3,50"
        pattern = r'^(.+?)s+(d+[,.]?d*)s*[A-Z]?s*$'
        match = re.search(pattern, line)
        
        if match:
            product_name = match.group(1).strip()
            price_str = match.group(2).replace(',', '.')
            
            # Filtruj oczywiste nie-produkty
            skip_words = ['suma', 'razem', 'total', 'podatek', 'vat', 'paragon', 'data', 'godzina']
            if any(skip in product_name.lower() for skip in skip_words):
                continue
                
            try:
                price = float(price_str)
                if price > 0 and len(product_name) > 2:  # Sensowne wartości
                    products.append({
                        "product": product_name,
                        "quantity": 1.0,
                        "unit": "szt.",
                        "price": price
                    })
            except ValueError:
                continue
    
    return products