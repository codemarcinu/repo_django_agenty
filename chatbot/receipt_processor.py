import easyocr
import logging
import json
import os
import fitz  # PyMuPDF
from PIL import Image
import tempfile
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from asgiref.sync import sync_to_async
from .models import PantryItem, ReceiptProcessing
from .services.agents import OllamaAgent # Assuming OllamaAgent can be used for extraction
from .validators import get_file_type

logger = logging.getLogger(__name__)

class ReceiptProcessor:
    def __init__(self):
        # Initialize EasyOCR reader. This can be slow, so do it once.
        # Specify languages, e.g., ['en', 'pl'] for English and Polish
        self.reader = easyocr.Reader(['pl', 'en'], gpu=True) # GPU enabled for faster processing

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
                    pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))  # 2x scale for better OCR
                    
                    # Save to temporary file for OCR
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
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
            logger.debug(f"Initializing EasyOCR reader for image processing...")
            
            result = self.reader.readtext(image_path)
            logger.info(f"EasyOCR detected {len(result)} text regions")
            
            # Log each detected text region for debugging
            for i, (bbox, text, prob) in enumerate(result):
                logger.debug(f"Region {i+1}: '{text}' (confidence: {prob:.2f})")
            
            # Concatenate all detected text into a single string
            extracted_text = " ".join([text for (bbox, text, prob) in result])
            logger.info(f"✅ OCR extraction completed. Total text length: {len(extracted_text)} characters")
            logger.debug(f"OCR extracted text: {extracted_text}")
            return extracted_text
        except Exception as e:
            logger.error(f"❌ Error during OCR text extraction from {image_path}: {e}", exc_info=True)
            return None
    
    def _extract_text_from_file(self, file_path):
        """Extract text from either image or PDF file."""
        file_extension = os.path.splitext(file_path)[1].lower()
        
        if file_extension == '.pdf':
            return self._extract_text_from_pdf(file_path)
        else:
            return self._extract_text_from_image(file_path)

    async def _extract_products_with_llm(self, receipt_text):
        logger.info(f"🤖 Starting LLM product extraction...")
        
        if not receipt_text:
            logger.warning("No receipt text provided to LLM")
            return []

        logger.debug(f"Input text length: {len(receipt_text)} characters")
        logger.debug(f"Input text preview: {receipt_text[:300]}...")

        # Prompt for LLM to extract structured product data
        # The LLM should return a JSON array of objects with 'product', 'quantity', 'unit'
        prompt = f"""
        Jesteś asystentem, który analizuje tekst z paragonów. Twoim zadaniem jest wyodrębnienie nazw produktów, ich ilości oraz jednostek (np. szt., kg, g, l, ml) z podanego tekstu.
        Zwróć wynik w formacie JSON, jako listę obiektów. Jeśli nie możesz znaleźć ilości lub jednostki, użyj wartości domyślnych: ilość 1.0, jednostka 'szt.'.
        Dodatkowo, jeśli w tekście paragonu znajdziesz datę, spróbuj ją wyodrębnić i dodać jako pole 'purchase_date' w formacie YYYY-MM-DD.
        
        Przykładowy format JSON:
        [
            {{"product": "Mleko", "quantity": 1.0, "unit": "l", "purchase_date": "2025-08-14"}},
            {{"product": "Chleb", "quantity": 1.0, "unit": "szt."}},
            {{"product": "Jabłka", "quantity": 0.5, "unit": "kg"}}
        ]

        Tekst z paragonu:
        """
        {receipt_text}
        """

        Wyodrębnione produkty (tylko JSON):
        """
        
        logger.debug(f"Prepared LLM prompt (length: {len(prompt)} chars)")
        logger.info("Sending request to LLM model...")

        # Use a dedicated OllamaAgent instance for this task
        # Assuming 'bielik' is the model name for the OllamaAgent
        logger.debug("Initializing OllamaAgent for product extraction...")
        ollama_agent = OllamaAgent(config={'model': 'SpeakLeash/bielik-11b-v2.3-instruct:Q5_K_M'}) # Adjust model name if different
        
        try:
            # The process method of OllamaAgent expects 'message' and 'history'
            logger.info("Calling LLM to process receipt text...")
            response = await ollama_agent.process({'message': prompt, 'history': []})
            
            if response.success:
                llm_response_text = response.data.get('response', '').strip()
                logger.info(f"✅ LLM response received (length: {len(llm_response_text)} chars)")
                logger.debug(f"LLM raw response: {llm_response_text}")
                
                # Attempt to parse JSON. LLMs can sometimes add extra text.
                # Find the first and last brace to isolate the JSON.
                logger.info("Parsing JSON from LLM response...")
                json_start = llm_response_text.find('[')
                json_end = llm_response_text.rfind(']')
                
                if json_start != -1 and json_end != -1 and json_end > json_start:
                    json_string = llm_response_text[json_start : json_end + 1]
                    logger.debug(f"Extracted JSON string: {json_string}")
                    
                    products_data = json.loads(json_string)
                    logger.info(f"✅ Successfully parsed {len(products_data)} products from LLM response")
                    logger.info(f"Extracted products: {products_data}")
                    return products_data
                else:
                    logger.warning(f"❌ LLM response did not contain valid JSON array")
                    logger.debug(f"Problematic response: {llm_response_text}")
                    return []
            else:
                logger.error(f"❌ LLM processing failed: {response.error}")
                return []
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON decoding error from LLM response: {e}")
            logger.debug(f"Problematic response: {llm_response_text}")
            return []
        except Exception as e:
            logger.error(f"❌ Unexpected error during LLM product extraction: {e}", exc_info=True)
            return []

    async def process_receipt(self, receipt_processing_id):
        logger.info(f"🔄 STARTING OCR PROCESSING for receipt ID: {receipt_processing_id}")
        receipt_record = None
        
        try:
            # Get receipt record
            logger.debug(f"Fetching receipt record from database...")
            receipt_record = await sync_to_async(ReceiptProcessing.objects.get)(id=receipt_processing_id)
            logger.info(f"✅ Found receipt record: {receipt_record.id}, current status: {receipt_record.status}")
            
            # Update status to OCR in progress
            logger.info(f"Updating receipt {receipt_processing_id} status to 'ocr_in_progress'")
            receipt_record.status = 'ocr_in_progress'
            await sync_to_async(receipt_record.save)()
            logger.debug(f"Receipt {receipt_processing_id} status updated successfully")

            # Get file path and verify file exists
            file_path = receipt_record.receipt_file.path
            logger.info(f"Processing file: {file_path}")
            
            if not os.path.exists(file_path):
                error_msg = f"File does not exist: {file_path}"
                logger.error(f"❌ {error_msg}")
                receipt_record.status = 'error'
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
                receipt_record.status = 'error'
                receipt_record.error_message = error_msg
                await sync_to_async(receipt_record.save)()
                return
            
            # OCR completed successfully
            logger.info(f"✅ OCR text extraction completed. Extracted {len(receipt_text)} characters")
            logger.debug(f"Extracted text preview: {receipt_text[:200]}...")
            
            receipt_record.raw_ocr_text = receipt_text
            receipt_record.status = 'ocr_done'
            await sync_to_async(receipt_record.save)()
            logger.info(f"Receipt {receipt_processing_id} status updated to 'ocr_done'")

            # Start LLM processing
            logger.info(f"🤖 Starting LLM product extraction for receipt {receipt_processing_id}")
            receipt_record.status = 'llm_in_progress'
            await sync_to_async(receipt_record.save)()
            logger.debug(f"Receipt {receipt_processing_id} status updated to 'llm_in_progress'")

            products_data = await self._extract_products_with_llm(receipt_text)
            logger.info(f"LLM processing completed. Found {len(products_data) if products_data else 0} products")
            
            if not products_data:
                error_msg = "Nie udało się wyodrębnić produktów przez LLM."
                logger.error(f"❌ {error_msg}")
                receipt_record.status = 'error'
                receipt_record.error_message = error_msg
                await sync_to_async(receipt_record.save)()
                return False
            
            # Processing completed successfully
            logger.info(f"✅ Product extraction successful: {products_data}")
            receipt_record.extracted_data = products_data
            receipt_record.status = 'ready_for_review'
            receipt_record.processed_at = timezone.now()
            await sync_to_async(receipt_record.save)()
            
            logger.info(f"🎉 Receipt {receipt_processing_id} processing COMPLETED and ready for review!")
            logger.info(f"=== RECEIPT PROCESSING SUMMARY ===")
            logger.info(f"Receipt ID: {receipt_processing_id}")
            logger.info(f"Text length: {len(receipt_text)} characters")
            logger.info(f"Products found: {len(products_data)}")
            logger.info(f"Status: ready_for_review")
            logger.info(f"===================================")
            return True

        except ReceiptProcessing.DoesNotExist:
            logger.error(f"❌ ReceiptProcessing record with ID {receipt_processing_id} not found in database")
            return False
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR during receipt processing for ID {receipt_processing_id}: {e}", exc_info=True)
            if receipt_record:
                try:
                    receipt_record.status = 'error'
                    receipt_record.error_message = str(e)
                    await sync_to_async(receipt_record.save)()
                    logger.info(f"Marked receipt {receipt_processing_id} as error in database")
                except Exception as save_error:
                    logger.error(f"Failed to save error status for receipt {receipt_processing_id}: {save_error}")
            return False

    def update_pantry(self, products_data):
        try:
            with transaction.atomic():
                for item_data in products_data:
                    product_name = item_data.get('product').strip()
                    quantity = float(item_data.get('quantity', 1.0))
                    unit = item_data.get('unit', 'szt.').strip()
                    expiry_date_str = item_data.get('expiry_date')
                    
                    expiry_date = None
                    if expiry_date_str:
                        try:
                            expiry_date = timezone.datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
                        except ValueError:
                            logger.warning(f"Invalid expiry date format for {product_name}: {expiry_date_str}")

                    if not product_name:
                        logger.warning(f"Skipping item with empty product name: {item_data}")
                        continue

                    pantry_item, created = PantryItem.objects.get_or_create(
                        name__iexact=product_name, # Case-insensitive match for existing item
                        defaults={'name': product_name, 'quantity': quantity, 'unit': unit, 'expiry_date': expiry_date}
                    )
                    if not created:
                        # If item exists, update quantity. Consider how to handle units.
                        # For simplicity, just add quantity if units match, otherwise log warning.
                        if pantry_item.unit.lower() == unit.lower():
                            pantry_item.quantity += quantity
                            pantry_item.expiry_date = expiry_date # Update expiry date as well
                            pantry_item.save()
                            logger.info(f"Updated existing pantry item: {pantry_item.name}, new quantity: {pantry_item.quantity}")
                        else:
                            logger.warning(f"Unit mismatch for {product_name}: existing unit {pantry_item.unit}, new unit {unit}. Not updating quantity.")
                    else:
                        logger.info(f"Added new pantry item: {pantry_item.name}, quantity: {pantry_item.quantity}")
            return True
        except Exception as e:
            logger.error(f"Error updating pantry: {e}")
            return False

# Instantiate the processor once to load OCR models
receipt_processor = ReceiptProcessor()