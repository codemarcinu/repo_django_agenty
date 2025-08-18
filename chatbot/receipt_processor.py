import json
import logging
import os
import tempfile

import easyocr
import fitz  # PyMuPDF
from asgiref.sync import sync_to_async
from django.db import transaction
from django.utils import timezone

from .services.agents import (
    OllamaAgent,
)  # Assuming OllamaAgent can be used for extraction
from .validators import get_file_type

logger = logging.getLogger(__name__)


class ReceiptProcessor:
    def __init__(self):
        # Initialize EasyOCR reader. This can be slow, so do it once.
        # Specify languages, e.g., ['en', 'pl'] for English and Polish
        self.reader = easyocr.Reader(
            ["pl", "en"], gpu=True
        )  # GPU enabled for faster processing

    def _extract_text_from_pdf(self, pdf_path):
        """Extract text from PDF file using PyMuPDF."""
        try:
            doc = fitz.open(pdf_path)
            text = ""

            for page_num in range(len(doc)):
                page = doc[page_num]
                # First try to extract text directly
                page_text = page.get_text()

                if page_text.strip():
                    text += page_text + "\n"
                else:
                    # If no text, convert page to image and use OCR
                    logger.info(f"PDF page {page_num} has no text, using OCR")
                    pix = page.get_pixmap(
                        matrix=fitz.Matrix(2.0, 2.0)
                    )  # 2x scale for better OCR

                    # Save to temporary file for OCR
                    with tempfile.NamedTemporaryFile(
                        suffix=".png", delete=False
                    ) as temp_file:
                        pix.save(temp_file.name)
                        ocr_text = self._extract_text_from_image(temp_file.name)
                        if ocr_text:
                            text += ocr_text + "\n"
                        os.unlink(temp_file.name)  # Clean up temp file

            doc.close()
            logger.info(f"PDF text extracted: {text}")
            return text.strip()

        except Exception as e:
            logger.error(f"Error during PDF text extraction from {pdf_path}: {e}")
            return None

    def _extract_text_from_image(self, image_path):
        logger.info(f"📷 Starting OCR text extraction from image: {image_path}")
        try:
            logger.debug("Initializing EasyOCR reader for image processing...")

            result = self.reader.readtext(image_path)
            logger.info(f"EasyOCR detected {len(result)} text regions")

            # Log each detected text region for debugging
            for i, (_bbox, text, prob) in enumerate(result):
                logger.debug(f"Region {i+1}: '{text}' (confidence: {prob:.2f})")

            # Concatenate all detected text into a single string
            extracted_text = " ".join([text for (_bbox, text, _prob) in result])
            logger.info(
                f"✅ OCR extraction completed. Total text length: {len(extracted_text)} characters"
            )
            logger.debug(f"OCR extracted text: {extracted_text}")
            return extracted_text
        except Exception as e:
            logger.error(
                f"❌ Error during OCR text extraction from {image_path}: {e}",
                exc_info=True,
            )
            return None

    def _extract_text_from_file(self, file_path):
        """Extract text from either image or PDF file."""
        file_extension = os.path.splitext(file_path)[1].lower()

        if file_extension == ".pdf":
            return self._extract_text_from_pdf(file_path)
        else:
            return self._extract_text_from_image(file_path)

    async def _extract_products_with_llm(self, receipt_text):
        logger.info("🤖 Starting LLM product extraction...")

        if not receipt_text:
            logger.warning("No receipt text provided to LLM")
            return []

        logger.debug(f"Input text length: {len(receipt_text)} characters")
        logger.debug(f"Input text preview: {receipt_text[:300]}...")

        # Prompt for LLM to extract structured product data
        # The LLM should return a JSON array of objects with 'product', 'quantity', 'unit'
        prompt = f"""
        Jesteś precyzyjnym asystentem do analizy tekstu z paragonów. Twoim zadaniem jest wyodrębnienie wszystkich produktów wraz z ich ilością i jednostką.
        Przeanalizuj poniższy tekst i zwróć listę produktów w formacie JSON. Umieść finalny JSON wewnątrz bloku kodu markdown, czyli ```json ... ```.

        Zasady:
        - Każdy produkt musi być osobnym obiektem w liście JSON.
        - Każdy obiekt musi zawierać klucze: "product_name" (string), "quantity" (float), "unit" (string).
        - Jeśli nie możesz określić ilości lub jednostki, użyj wartości domyślnych: quantity = 1.0, unit = 'szt.'.
        - Zignoruj pozycje, które nie są produktami (np. sumy, rabaty, dane sklepu).
        - Nazwy produktów powinny być czyste i pozbawione dodatkowych informacji, jak cena czy kod.

        Przykład formatu wyjściowego:
        ```json
        [
            {{"product_name": "Mleko Wiejskie 2%", "quantity": 1.0, "unit": "l"}},
            {{"product_name": "Chleb Razowy", "quantity": 1.0, "unit": "szt."}},
            {{"product_name": "Jabłka Golden", "quantity": 0.5, "unit": "kg"}}
        ]
        ```

        Tekst z paragonu do analizy:
        ---
        {receipt_text}
        ---

        Wyodrębnione produkty (tylko blok JSON):
        """

        logger.debug(f"Prepared LLM prompt (length: {len(prompt)} chars)")
        logger.info("Sending request to LLM model...")

        # Dynamically find and configure the agent for receipt processing
        try:
            from .models import Agent
            from asgiref.sync import sync_to_async

            # Get all active agents and filter by capability
            def get_receipt_agent():
                agents = Agent.objects.filter(is_active=True)
                for agent in agents:
                    if agent.has_capability("receipt_extraction"):
                        return agent
                raise Agent.DoesNotExist("No agent with receipt_extraction capability found")
                        
            receipt_agent_model = await sync_to_async(get_receipt_agent)()
            agent_config = receipt_agent_model.config
            logger.info(
                f"Using agent '{receipt_agent_model.name}' for receipt extraction."
            )

        except Agent.DoesNotExist:
            logger.error(
                "No active agent with 'receipt_extraction' capability found. Please configure an agent."
            )
            raise ValueError("Receipt processing agent not configured.")

        # Instantiate the agent with the loaded config
        ollama_agent = OllamaAgent(config=agent_config)

        try:
            # For receipt processing, call Ollama directly to avoid fallbacks
            logger.info("Calling LLM to process receipt text...")
            
            # First check if Ollama is available
            if not await ollama_agent.health_check_ollama():
                logger.error("Ollama service is not available for receipt processing")
                # This will trigger a retry in Celery
                raise ConnectionError("Ollama service is not available.")
            
            # Call Ollama directly, bypassing the fallback system
            response = await ollama_agent.process_with_ollama({"message": prompt, "history": []})

            if response.success:
                llm_response_text = response.data.get("response", "").strip()
                logger.info(
                    f"✅ LLM response received (length: {len(llm_response_text)} chars)"
                )
                logger.debug(f"LLM raw response: {llm_response_text}")

                # Attempt to parse JSON from markdown code block
                logger.info("Parsing JSON from LLM response's markdown block...")
                
                import re
                json_match = re.search(r"```json\n(.*?)\n```", llm_response_text, re.DOTALL)
                
                if json_match:
                    json_string = json_match.group(1).strip()
                    logger.debug(f"Extracted JSON string: {json_string}")

                    # Validate the data structure using Pydantic
                    from pydantic import ValidationError
                    from .schemas import ReceiptDataSchema, ProductSchema

                    try:
                        products_data = json.loads(json_string)
                        validated_data = [ProductSchema(**item) for item in products_data]
                        
                        logger.info(
                            f"✅ Successfully parsed and validated {len(validated_data)} products from LLM response"
                        )
                        # Convert Pydantic models back to dicts for JSON serialization
                        return [item.dict() for item in validated_data]
                    
                    except (ValidationError, json.JSONDecodeError) as e:
                        logger.error(f"❌ Data validation failed for LLM response: {e}")
                        logger.debug(f"Problematic JSON string: {json_string}")
                        return [] # Return empty list on validation failure

                else:
                    logger.warning("❌ LLM response did not contain a valid ```json``` block.")
                    logger.debug(f"Problematic response: {llm_response_text}")
                    return [] # Return empty list to signify parsing failure at this stage
        except Exception as e:
            logger.error(
                f"❌ Unexpected error during LLM product extraction: {e}", exc_info=True
            )
            # Re-raise the exception to allow Celery to handle retries
            raise

    async def process_receipt(self, receipt_id):
        logger.info(
            f"🔄 STARTING OCR PROCESSING for receipt ID: {receipt_id}"
        )
        receipt_record = None

        try:
            # Get receipt record
            from inventory.models import Receipt
            logger.debug("Fetching receipt record from database...")
            receipt_record = await sync_to_async(Receipt.objects.get)(
                id=receipt_id
            )
            logger.info(
                f"✅ Found receipt record: {receipt_record.id}, current status: {receipt_record.status}"
            )

            # Update status to OCR in progress
            logger.info(
                f"Updating receipt {receipt_id} status to 'ocr_in_progress'"
            )
            receipt_record.status = "ocr_in_progress"
            await sync_to_async(receipt_record.save)()
            logger.debug(f"Receipt {receipt_id} status updated successfully")

            # Get file path and verify file exists
            file_path = receipt_record.receipt_file.path
            logger.info(f"Processing file: {file_path}")

            if not os.path.exists(file_path):
                error_msg = f"File does not exist: {file_path}"
                logger.error(f"❌ {error_msg}")
                receipt_record.status = "error"
                receipt_record.error_message = error_msg
                await sync_to_async(receipt_record.save)()
                return

            # Check file size
            file_size = os.path.getsize(file_path)
            logger.info(f"File size: {file_size} bytes")

            # Detect file type
            file_type = get_file_type(file_path)
            logger.info(f"Detected file type: {file_type}")

            # Extract text from file
            logger.info(f"🔍 Starting text extraction from {file_type} file...")
            receipt_text = self._extract_text_from_file(file_path)

            if not receipt_text:
                error_msg = "Nie udało się wyodrębnić tekstu z pliku paragonu."
                logger.error(f"❌ {error_msg}")
                receipt_record.status = "error"
                receipt_record.error_message = error_msg
                await sync_to_async(receipt_record.save)()
                return

            # OCR completed successfully
            logger.info(
                f"✅ OCR text extraction completed. Extracted {len(receipt_text)} characters"
            )
            logger.debug(f"Extracted text preview: {receipt_text[:200]}...")

            receipt_record.raw_ocr_text = receipt_text
            receipt_record.status = "ocr_done"
            await sync_to_async(receipt_record.save)()
            logger.info(f"Receipt {receipt_id} status updated to 'ocr_done'")

            # Start LLM processing
            logger.info(
                f"🤖 Starting LLM product extraction for receipt {receipt_id}"
            )
            receipt_record.status = "llm_in_progress"
            await sync_to_async(receipt_record.save)()
            logger.debug(
                f"Receipt {receipt_id} status updated to 'llm_in_progress'"
            )

            products_data = await self._extract_products_with_llm(receipt_text)
            logger.info(
                f"LLM processing completed. Found {len(products_data) if products_data else 0} products"
            )

            if not products_data:
                error_msg = "Nie udało się wyodrębnić produktów przez LLM."
                logger.error(f"❌ {error_msg}")
                receipt_record.status = "error"
                receipt_record.error_message = error_msg
                await sync_to_async(receipt_record.save)()
                return False

            # Processing completed successfully
            logger.info(f"✅ Product extraction successful: {products_data}")
            receipt_record.extracted_data = products_data
            receipt_record.status = "ready_for_review"
            receipt_record.processed_at = timezone.now()
            await sync_to_async(receipt_record.save)()

            logger.info(
                f"🎉 Receipt {receipt_id} processing COMPLETED and ready for review!"
            )
            logger.info("=== RECEIPT PROCESSING SUMMARY ===")
            logger.info(f"Receipt ID: {receipt_id}")
            logger.info(f"Text length: {len(receipt_text)} characters")
            logger.info(f"Products found: {len(products_data)}")
            logger.info("Status: ready_for_review")
            logger.info("===================================")
            return True

        except Receipt.DoesNotExist:
            logger.error(
                f"❌ Receipt record with ID {receipt_id} not found in database"
            )
            return False
        except Exception as e:
            logger.error(
                f"❌ CRITICAL ERROR during receipt processing for ID {receipt_id}: {e}",
                exc_info=True,
            )
            if receipt_record:
                try:
                    receipt_record.status = "error"
                    receipt_record.error_message = str(e)
                    await sync_to_async(receipt_record.save)()
                    logger.info(
                        f"Marked receipt {receipt_id} as error in database"
                    )
                except Exception as save_error:
                    logger.error(
                        f"Failed to save error status for receipt {receipt_id}: {save_error}"
                    )
            return False

    def update_pantry(self, products_data):
        try:
            with transaction.atomic():
                for item_data in products_data:
                    product_name = item_data.get("product").strip()
                    quantity = float(item_data.get("quantity", 1.0))
                    unit = item_data.get("unit", "szt.").strip()
                    expiry_date_str = item_data.get("expiry_date")

                    expiry_date = None
                    if expiry_date_str:
                        try:
                            expiry_date = timezone.datetime.strptime(
                                expiry_date_str, "%Y-%m-%d"
                            ).date()
                        except ValueError:
                            logger.warning(
                                f"Invalid expiry date format for {product_name}: {expiry_date_str}"
                            )

                    if not product_name:
                        logger.warning(
                            f"Skipping item with empty product name: {item_data}"
                        )
                        continue

                    # TODO: Replace with PantryServiceV2 for consistency
                    logger.info(f"Processing product: {product_name}, quantity: {quantity}, unit: {unit}")
                    
                    # Use the new PantryServiceV2 instead of direct PantryItem access
                    from .services.pantry_service_v2 import PantryServiceV2
                    pantry_service = PantryServiceV2()
                    
                    try:
                        inventory_item = pantry_service.add_or_update_item(
                            name=product_name,
                            quantity=quantity,
                            unit=unit,
                            expiry_date=expiry_date
                        )
                        logger.info(f"Successfully added/updated inventory item: {inventory_item.id}")
                    except Exception as e:
                        logger.error(f"Error adding product {product_name} to pantry: {e}")
                        continue
            return True
        except Exception as e:
            logger.error(f"Error updating pantry: {e}")
            return False


# Instantiate the processor once to load OCR models
receipt_processor = ReceiptProcessor()


# Compatibility layer for gradual migration to V2
def _should_use_v2():
    """Check if we should use ReceiptProcessorV2."""
    from django.conf import settings
    return getattr(settings, 'USE_RECEIPT_PROCESSOR_V2', False)


async def process_receipt_with_migration_support(receipt_id: int) -> bool:
    """
    Process receipt with migration support.
    Uses V2 if enabled, falls back to V1 if needed.
    """
    if _should_use_v2():
        try:
            from .services.receipt_processor_adapter import process_receipt
            logger.info(f"Using ReceiptProcessorV2 for receipt {receipt_id}")
            return await process_receipt(receipt_id)
        except Exception as e:
            logger.error(f"ReceiptProcessorV2 failed for receipt {receipt_id}: {e}")
            logger.info("Falling back to legacy ReceiptProcessor")
    
    # Use legacy processor
    logger.info(f"Using legacy ReceiptProcessor for receipt {receipt_id}")
    return await receipt_processor.process_receipt(receipt_id)
