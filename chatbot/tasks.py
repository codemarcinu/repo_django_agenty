# W pliku chatbot/tasks.py - dodaj debugging

from celery import shared_task
import logging
import re
import os
import shutil
from pathlib import Path

from inventory.models import Receipt, ReceiptLineItem
from django.conf import settings
from django.db import transaction
from asgiref.sync import async_to_sync

from .models import Document
from .rag_processor import rag_processor
from .schemas import ParsedReceipt
from .services.exceptions_receipt import (
    DatabaseError,
    MatchingError,
    OCRError,
    ParsingError,
)
from .services.pantry_service_v2 import PantryServiceV2

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
    Orchestrates the full, multi-step receipt processing pipeline with Mistral OCR integration.
    Implements hybrid strategy: Mistral OCR (golden standard) → Local Pipeline (fallback)
    """
    from .services.ocr_backends import OCRResult
    from .services.ocr_service import ocr_service
    from .services.quality_gate_service import QualityGateService
    from .services.receipt_parser import get_receipt_parser, AdaptiveReceiptParser
    from .services.receipt_service import get_receipt_service
    from .services.vision_service import VisionService
    from .services.basic_parser import BasicReceiptParser
    from .services.mistral_ocr_service import MistralOcrService
    from .services.websocket_notifier import get_websocket_notifier

    logger.info(f"🚀 STARTING HYBRID ORCHESTRATION for Receipt ID: {receipt_id} (Attempt: {self.request.retries + 1})")

    try:
        receipt = Receipt.objects.get(id=receipt_id)
        parsed_data = None
        notifier = get_websocket_notifier()

        # Send immediate status update that processing has started
        notifier.send_status_update(
            receipt_id=receipt_id,
            status="processing",
            message="Rozpoczęto przetwarzanie paragonu",
            progress=30,
            processing_step="processing_started"
        )

        try:
            # --- STRATEGIA 1: Użyj Premium Backend (Mistral OCR) ---
            logger.info(f"🤖 [Premium] Trying Mistral OCR for Receipt {receipt_id}")
            mistral_service = MistralOcrService()

            if mistral_service.is_available():
                mistral_result = async_to_sync(mistral_service.extract_data_from_file)(receipt.receipt_file.path)

                if mistral_result and len(mistral_result.items) > 0:
                    logger.info(f"✅ [Premium] Mistral OCR SUCCESS: {len(mistral_result.items)} items extracted")

                    # 🔥 PĘTLA ZWROTNA - ZAPISYWANIE DANYCH DO UCZENIA 🔥
                    save_for_fine_tuning(receipt.receipt_file.path, mistral_result)

                    # Konwertuj na format oczekiwany przez dalszy pipeline
                    parsed_data = {
                        "products": [
                            {
                                "product": item.product_name,
                                "name": item.product_name,
                                "quantity": item.quantity,
                                "unit": item.unit,
                                "price": item.price
                            }
                            for item in mistral_result.items
                        ],
                        "store_name": getattr(mistral_result, 'store_name', ''),
                        "total_amount": getattr(mistral_result, 'total_amount', 0)
                    }
                else:
                    logger.warning(f"⚠️ [Premium] Mistral OCR returned no items")
                    raise Exception("Mistral OCR returned no items")
            else:
                logger.warning(f"🚫 [Premium] Mistral OCR not available (API key missing)")
                raise Exception("Mistral OCR not available")

        except Exception as mistral_error:
            logger.warning(f"💥 [Premium] Mistral OCR failed ({mistral_error}). Switching to local pipeline.")

            # Send notification about fallback to local pipeline
            notifier.send_status_update(
                receipt_id=receipt_id,
                status="processing",
                message="Mistral OCR niedostępny, używam lokalnego przetwarzania...",
                progress=35,
                processing_step="fallback_to_local"
            )

            # --- STRATEGIA 2: Fallback na Lokalny Hybrydowy Pipeline ---
            logger.info(f"🔄 [Fallback] Starting Local Pipeline for Receipt {receipt_id}")

            # --- KROK 1: OCR ---
            logger.info(f" [1/4] OCR | Receipt ID: {receipt_id}")
            receipt.mark_as_processing(step="ocr_in_progress")

            # Send OCR start notification
            notifier.send_status_update(
                receipt_id=receipt_id,
                status="processing",
                message="Rozpoznawanie tekstu z paragonu...",
                progress=40,
                processing_step="ocr_in_progress"
            )

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
                raise TypeError("OCRService.process_document() must return OCRResult instance")

            quality_gate = QualityGateService(ocr_result)
            quality_score = quality_gate.calculate_quality_score()
            logger.info(f"Paragon {receipt_id}: Wynik jakości OCR to {quality_score}")

            # Send OCR completion notification and pause for user review
            receipt.mark_as_processing(step="ocr_completed")
            notifier.send_status_update(
                receipt_id=receipt_id,
                status="pending_review",
                message="Tekst został rozpoznany. Sprawdź i potwierdź przed kontynuacją.",
                progress=60,
                processing_step="ocr_completed"
            )

            logger.info(f"✅ OCR COMPLETED for Receipt ID: {receipt_id} - WAITING FOR USER REVIEW")
            return  # Pause processing here for user review

            # --- KROK 3: PARSING ---
            logger.info(f" [3/4] PARSING | Receipt ID: {receipt_id}")
            receipt.mark_as_processing(step="parsing_in_progress")

            # Send parsing start notification
            notifier.send_status_update(
                receipt_id=receipt_id,
                status="processing",
                message="Analizuję produkty na paragonie...",
                progress=70,
                processing_step="parsing_in_progress"
            )

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

                parsed_data = extracted_dict
            else:
                logger.error(f"❌ Parser returned empty result for receipt {receipt_id}")
                # FALLBACK: Spróbuj prostego parsowania regex
                fallback_products = simple_text_parser(ocr_result.text)
                if fallback_products:
                    logger.info(f"🔄 Fallback parser found {len(fallback_products)} products")
                    parsed_data = {"products": fallback_products, "store_name": "", "total": 0}
                else:
                    receipt.mark_as_error("Parsing failed: No data extracted from OCR.")
                    raise ParsingError(f"No data extracted for receipt {receipt_id}")

        if not parsed_data:
             raise ValueError("Both Mistral OCR and local pipeline failed to parse receipt data.")

        # --- Dalsze kroki są już wspólne ---
        receipt.extracted_data = parsed_data
        receipt.mark_llm_done(parsed_data)

        # Send parsing completion notification
        notifier.send_status_update(
            receipt_id=receipt_id,
            status="processing",
            message="Produkty zostały rozpoznane, dopasowuję do bazy...",
            progress=85,
            processing_step="parsing_completed"
        )

        # --- KROK 4: MATCHING ---
        logger.info(f" [4/4] MATCHING | Receipt ID: {receipt_id}")

        # Send matching start notification
        notifier.send_status_update(
            receipt_id=receipt_id,
            status="processing",
            message="Dopasowuję produkty do bazy danych...",
            progress=90,
            processing_step="matching_in_progress"
        )

        receipt_service = get_receipt_service()
        receipt_service.process_receipt_matching(receipt_id)

        # Send final completion notification
        notifier.send_status_update(
            receipt_id=receipt_id,
            status="completed",
            message="Paragon został pomyślnie przetworzony!",
            progress=100,
            processing_step="done"
        )

        logger.info(f"✅ HYBRID ORCHESTRATION COMPLETED for Receipt ID: {receipt_id}.")

    except Exception as e:
        logger.error(f"❌ HYBRID ORCHESTRATION ERROR for Receipt ID: {receipt_id}: {e}", exc_info=True)
        try:
            receipt_to_update = Receipt.objects.get(id=receipt_id)
            receipt_to_update.mark_as_error(f"Critical error: {e}")
        except Receipt.DoesNotExist:
            logger.error(f"Could not find receipt {receipt_id} to mark as error.")
        raise


@shared_task
def continue_receipt_processing_after_ocr_review(receipt_id: int):
    """
    Continue receipt processing after OCR text has been reviewed and potentially edited by user.
    This picks up from where OCR completed and continues with quality gate and parsing.
    """
    from .services.ocr_backends import OCRResult
    from .services.ocr_service import ocr_service
    from .services.quality_gate_service import QualityGateService
    from .services.receipt_parser import get_receipt_parser, AdaptiveReceiptParser
    from .services.receipt_service import get_receipt_service
    from .services.vision_service import VisionService
    from .services.basic_parser import BasicReceiptParser
    from .services.websocket_notifier import get_websocket_notifier

    logger.info(f"🔄 CONTINUING PROCESSING AFTER OCR REVIEW for Receipt ID: {receipt_id}")

    try:
        receipt = Receipt.objects.get(id=receipt_id)
        notifier = get_websocket_notifier()

        # Use the updated OCR text (if user edited it)
        ocr_text = receipt.raw_ocr_text

        # Create a proper OCRResult with the updated text
        ocr_result = OCRResult(
            text=ocr_text,
            confidence=0.9,
            backend="user_reviewed",
            processing_time=0.0,
            metadata={"source": "user_edited"},
            success=True
        )

        # --- KROK 2: QUALITY GATE ---
        logger.info(f" [2/4] QUALITY GATE | Receipt ID: {receipt_id}")
        receipt.mark_as_processing(step="quality_gate")

        quality_gate = QualityGateService(ocr_result)
        quality_score = quality_gate.calculate_quality_score()
        logger.info(f"Paragon {receipt_id}: Wynik jakości OCR to {quality_score}")

        # Send quality gate completion notification
        notifier.send_status_update(
            receipt_id=receipt_id,
            status="processing",
            message="Jakość tekstu została sprawdzona, analizuję produkty...",
            progress=75,
            processing_step="quality_gate"
        )

        # --- KROK 3: PARSING ---
        logger.info(f" [3/4] PARSING | Receipt ID: {receipt_id}")
        receipt.mark_as_processing(step="parsing_in_progress")

        # Send parsing start notification
        notifier.send_status_update(
            receipt_id=receipt_id,
            status="processing",
            message="Analizuję produkty na paragonie...",
            progress=80,
            processing_step="parsing_in_progress"
        )

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

            parsed_data = extracted_dict
        else:
            logger.error(f"❌ Parser returned empty result for receipt {receipt_id}")
            # FALLBACK: Spróbuj prostego parsowania regex
            fallback_products = simple_text_parser(ocr_result.text)
            if fallback_products:
                logger.info(f"🔄 Fallback parser found {len(fallback_products)} products")
                parsed_data = {"products": fallback_products, "store_name": "", "total": 0}
            else:
                receipt.mark_as_error("Parsing failed: No data extracted from OCR.")
                raise ParsingError(f"No data extracted for receipt {receipt_id}")

        # --- Dalsze kroki są już wspólne ---
        receipt.extracted_data = parsed_data
        receipt.mark_llm_done(parsed_data)

        # Send parsing completion notification
        notifier.send_status_update(
            receipt_id=receipt_id,
            status="processing",
            message="Produkty zostały rozpoznane, dopasowuję do bazy...",
            progress=90,
            processing_step="parsing_completed"
        )

        # --- KROK 4: MATCHING ---
        logger.info(f" [4/4] MATCHING | Receipt ID: {receipt_id}")

        # Send matching start notification
        notifier.send_status_update(
            receipt_id=receipt_id,
            status="processing",
            message="Dopasowuję produkty do bazy danych...",
            progress=95,
            processing_step="matching_in_progress"
        )

        receipt_service = get_receipt_service()
        receipt_service.process_receipt_matching(receipt_id)

        # Send final completion notification
        notifier.send_status_update(
            receipt_id=receipt_id,
            status="completed",
            message="Paragon został pomyślnie przetworzony!",
            progress=100,
            processing_step="done"
        )

        logger.info(f"✅ OCR REVIEW PROCESSING COMPLETED for Receipt ID: {receipt_id}")

    except Exception as e:
        logger.error(f"❌ OCR REVIEW PROCESSING ERROR for Receipt ID: {receipt_id}: {e}", exc_info=True)
        try:
            receipt_to_update = Receipt.objects.get(id=receipt_id)
            receipt_to_update.mark_as_error(f"Critical error: {e}")
        except Receipt.DoesNotExist:
            logger.error(f"Could not find receipt {receipt_id} to mark as error.")
        raise


def save_for_fine_tuning(image_path: str, parsed_data: ParsedReceipt):
    """
    Save receipt image and corresponding parsed data for fine-tuning local models.

    Args:
        image_path: Path to the receipt image file
        parsed_data: ParsedReceipt object with golden standard annotations
    """
    try:
        # Create fine-tuning dataset directory
        dataset_dir = settings.BASE_DIR / "fine_tuning_dataset"
        dataset_dir.mkdir(exist_ok=True)

        # Generate filenames
        image_filename = Path(image_path).name
        json_filename = Path(image_path).stem + ".json"

        # Copy image to dataset
        shutil.copy(image_path, dataset_dir / image_filename)

        # Save JSON annotations
        with open(dataset_dir / json_filename, 'w', encoding='utf-8') as f:
            # Convert to JSON-serializable format
            json_data = {
                "store_name": getattr(parsed_data, 'store_name', ''),
                "total_amount": getattr(parsed_data, 'total_amount', 0),
                "items": [
                    {
                        "product_name": item.product_name,
                        "quantity": item.quantity,
                        "unit": item.unit,
                        "price": item.price
                    }
                    for item in parsed_data.items
                ]
            }
            import json
            f.write(json.dumps(json_data, indent=2, ensure_ascii=False))

        logger.info(f"💾 Saved training pair for fine-tuning: {image_filename} + {json_filename}")

    except Exception as e:
        logger.error(f"❌ Failed to save data for fine-tuning: {e}")

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

@shared_task(bind=True)
def finalize_receipt_inventory(self, receipt_id: int):
    """
    Finalizes a receipt after user review, adding its line items to the pantry.
    """
    logger.info(f"[Finalize Task] Starting finalization for Receipt ID: {receipt_id}. Task ID: {self.request.id}")
    try:
        with transaction.atomic():
            receipt = Receipt.objects.select_related('user').prefetch_related('line_items__matched_product').get(id=receipt_id)
            logger.info(f"[Finalize Task] Processing {receipt.line_items.count()} line items for Receipt ID: {receipt.id}.")

            if receipt.status == 'completed':
                logger.warning(f"[Finalize Task] Receipt {receipt.id} is already marked as completed. Skipping.")
                return

            pantry_service = PantryServiceV2()
            
            for item in receipt.line_items.all():
                product_name = item.product_name
                quantity = item.quantity
                # Get unit from matched product or default to 'szt.' if no product is matched
                unit = getattr(item.matched_product, 'unit', 'szt.') if item.matched_product else 'szt.' 
                
                logger.info(f"[Finalize Task] Adding to inventory: '{product_name}' (Quantity: {quantity}, Unit: {unit})")
                
                pantry_service.add_or_update_item(
                    name=product_name,
                    quantity=float(quantity),
                    unit=unit,
                    # expiry_date is not available in ReceiptLineItem, so we pass None
                    expiry_date=None 
                )
                logger.debug(f"[Finalize Task] Successfully processed item '{product_name}' for Receipt ID: {receipt.id}.")

            # Mark the receipt as completed
            receipt.status = 'completed'
            receipt.processing_step = 'done'
            receipt.error_message = '' # Clear any previous errors
            receipt.save()
            
            logger.info(f"✅ [Finalize Task] Successfully finalized Receipt ID: {receipt.id}. All items added to inventory.")

    except Receipt.DoesNotExist:
        logger.error(f"[Finalize Task] CRITICAL: Receipt with ID {receipt_id} not found.")
    except Exception as e:
        logger.error(f"[Finalize Task] CRITICAL: An unexpected error occurred while finalizing Receipt ID: {receipt_id}. Error: {e}", exc_info=True)
        try:
            # Attempt to mark the receipt as failed
            receipt_to_fail = Receipt.objects.get(id=receipt_id)
            receipt_to_fail.status = 'error'
            receipt_to_fail.processing_step = 'finalization_failed'
            receipt_to_fail.error_message = f"Finalization failed: {e}"
            receipt_to_fail.save()
            logger.warning(f"[Finalize Task] Marked Receipt ID: {receipt_id} as 'error' due to finalization failure.")
        except Receipt.DoesNotExist:
            logger.error(f"[Finalize Task] Could not even find Receipt {receipt_id} to mark as failed. Data may be inconsistent.")
        # Re-raise the exception to let Celery know the task failed
        raise