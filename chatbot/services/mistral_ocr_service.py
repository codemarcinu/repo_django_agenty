# chatbot/services/mistral_ocr_service.py
import httpx
import logging
from pathlib import Path
from typing import Optional, List
from django.conf import settings
from asgiref.sync import async_to_sync
import fitz  # PyMuPDF for PDF processing
import io
from PIL import Image

from chatbot.schemas import ParsedReceipt, ProductSchema

logger = logging.getLogger(__name__)


class MistralOcrService:
    """
    Service for interacting with Mistral OCR API.
    This serves as the "golden standard" for receipt processing.
    """

    def __init__(self):
        self.api_url = "https://api.mistral.ai/v1/ocr/process"
        self.api_key = settings.MISTRAL_API_KEY
        self.timeout = 120.0  # 2 minutes timeout for OCR processing
        self.notifier = None  # Will be set when processing starts
        self.receipt_id = None  # Will be set when processing starts

    def set_processing_context(self, receipt_id: int, notifier):
        """Set the processing context for status updates."""
        self.receipt_id = receipt_id
        self.notifier = notifier

    async def extract_data_from_file(self, file_path: str) -> Optional[ParsedReceipt]:
        """
        Extract receipt data using Mistral OCR API with Chat Completions endpoint.

        Args:
            file_path: Path to the receipt file (image or PDF)

        Returns:
            ParsedReceipt object with extracted items, or None if failed
        """
        logger.info(f"🚀 Sending receipt to Mistral OCR API: {file_path}")

        if not self.api_key:
            logger.error("❌ Mistral API key not configured")
            raise ValueError("Mistral API key not configured")

        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            # Check if file is PDF and convert to images if needed
            extension = file_path_obj.suffix.lower()
            if extension == '.pdf':
                logger.info("📄 PDF file detected, converting to images...")
                image_data_urls = self._convert_pdf_to_images(file_path)
                if not image_data_urls:
                    logger.error("❌ Failed to convert PDF to images")
                    return None

                # Process each page/image and combine results
                return await self._process_multiple_images(image_data_urls)
            else:
                # Handle image files directly
                with open(file_path, "rb") as f:
                    import base64
                    file_content = base64.b64encode(f.read()).decode('utf-8')

                content_type = self._get_content_type(file_path)
                data_url = f"data:{content_type};base64,{file_content}"

                return await self._process_single_image(data_url)

        except httpx.TimeoutException:
            logger.error(f"⏰ Timeout error with Mistral API for file: {file_path}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"🔴 HTTP error with Mistral API: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error in MistralOcrService: {e}", exc_info=True)
            raise

    async def _process_single_image(self, data_url: str) -> Optional[ParsedReceipt]:
        """Process a single image with Mistral OCR API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Prompt for receipt data extraction
        extraction_prompt = """
        Wyodrębnij wszystkie produkty z tego paragonu i zwróć je w formacie JSON:

        {
            "store_name": "Nazwa sklepu",
            "total_amount": 0.00,
            "items": [
                {
                    "product_name": "Nazwa produktu",
                    "quantity": 1.0,
                    "unit": "szt.",
                    "price": 0.00
                }
            ]
        }

        Zwróć tylko JSON bez dodatkowych komentarzy.
        """

        payload = {
            "model": "pixtral-12b-2409",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": extraction_prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": data_url
                            }
                        }
                    ]
                }
            ],
            "response_format": {"type": "json_object"}
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.info(f"📤 Making request to Mistral Chat Completions API...")
            response = await client.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()

        # Parse response
        response_data = response.json()
        logger.info(f"✅ Received response from Mistral API")

        if 'choices' in response_data and len(response_data['choices']) > 0:
            import json
            content = response_data['choices'][0]['message']['content']
            parsed_data = json.loads(content)

            # Convert to our format
            items = []
            for item in parsed_data.get('items', []):
                try:
                    from chatbot.schemas import ProductSchema
                    product_schema = ProductSchema(
                        product_name=item.get('product_name', item.get('name', '')),
                        quantity=float(item.get('quantity', 1.0)),
                        unit=item.get('unit', 'szt.'),
                        price=float(item.get('price', 0.0))
                    )
                    items.append(product_schema)
                except Exception as e:
                    logger.warning(f"Error parsing item {item}: {e}")
                    continue

            logger.info(f"📊 Extracted {len(items)} products from Mistral response")
            return ParsedReceipt(
                store_name=parsed_data.get('store_name', ''),
                total_amount=parsed_data.get('total_amount', 0),
                items=items
            )
        else:
            logger.warning("⚠️ No valid response from Mistral API")
            return None

    async def _process_multiple_images(self, image_data_urls: List[str]) -> Optional[ParsedReceipt]:
        """Process multiple images and combine the results."""
        logger.info(f"🔄 Processing {len(image_data_urls)} images from PDF")

        all_items = []
        store_names = []
        total_amounts = []

        # Send initial OCR processing status
        if self.notifier and self.receipt_id:
            self.notifier.send_status_update(
                self.receipt_id, "processing",
                f"Przetwarzanie OCR: {len(image_data_urls)} stron", 42
            )

        for i, data_url in enumerate(image_data_urls):
            logger.info(f"📷 Processing page {i + 1}/{len(image_data_urls)}")
            try:
                result = await self._process_single_image(data_url)
                if result:
                    all_items.extend(result.items)
                    if result.store_name:
                        store_names.append(result.store_name)
                    if result.total_amount > 0:
                        total_amounts.append(result.total_amount)

                # Send progress update for each page processed
                if self.notifier and self.receipt_id:
                    progress = 42 + int((i + 1) / len(image_data_urls) * 18)  # 42-60% range
                    self.notifier.send_status_update(
                        self.receipt_id, "processing",
                        f"OCR strony {i + 1}/{len(image_data_urls)}", progress
                    )

            except Exception as e:
                logger.warning(f"⚠️ Error processing page {i + 1}: {e}")
                continue

        if not all_items:
            logger.error("❌ No items extracted from any page")
            return None

        # Determine the most common store name
        store_name = ""
        if store_names:
            store_name = max(set(store_names), key=store_names.count)

        # Use the highest total amount (assuming it includes all pages)
        total_amount = max(total_amounts) if total_amounts else 0

        logger.info(f"📊 Combined results: {len(all_items)} total products from {len(image_data_urls)} pages")

        # Send OCR completion status
        if self.notifier and self.receipt_id:
            self.notifier.send_status_update(
                self.receipt_id, "processing",
                f"OCR zakończone - {len(all_items)} produktów", 60
            )

        return ParsedReceipt(
            store_name=store_name,
            total_amount=total_amount,
            items=all_items
        )

    def _get_content_type(self, file_path: str) -> str:
        """Get MIME content type based on file extension."""
        extension = Path(file_path).suffix.lower()
        content_types = {
            '.pdf': 'application/pdf',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.webp': 'image/webp'
        }
        return content_types.get(extension, 'application/octet-stream')

    def _convert_pdf_to_images(self, file_path: str) -> List[str]:
        """
        Convert PDF pages to base64 encoded images.

        Args:
            file_path: Path to the PDF file

        Returns:
            List of base64 encoded image strings (data:image/jpeg;base64,...)
        """
        images = []
        try:
            # Open PDF with PyMuPDF
            doc = fitz.open(file_path)
            total_pages = len(doc)
            logger.info(f"📄 Converting PDF with {total_pages} pages to images")

            # Send initial PDF conversion status
            if self.notifier and self.receipt_id:
                self.notifier.send_status_update(
                    self.receipt_id, "processing",
                    f"Konwertowanie PDF ({total_pages} stron)...", 30
                )

            for page_num in range(total_pages):
                try:
                    # Render page to image
                    page = doc.load_page(page_num)
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x scaling for better quality

                    # Convert to PIL Image
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))

                    # Convert to RGB if necessary
                    if img.mode != 'RGB':
                        img = img.convert('RGB')

                    # Convert to base64
                    import base64
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=85)
                    img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

                    # Create data URL
                    data_url = f"data:image/jpeg;base64,{img_base64}"
                    images.append(data_url)

                    logger.debug(f"📷 Converted page {page_num + 1} to image")

                    # Send progress update for PDF conversion
                    if self.notifier and self.receipt_id:
                        progress = 30 + int((page_num + 1) / total_pages * 10)  # 30-40% range
                        self.notifier.send_status_update(
                            self.receipt_id, "processing",
                            f"Konwertowanie PDF: strona {page_num + 1}/{total_pages}", progress
                        )

                except Exception as e:
                    logger.warning(f"⚠️ Error converting page {page_num + 1}: {e}")
                    continue

            doc.close()
            logger.info(f"✅ Successfully converted {len(images)} pages to images")

            # Send PDF conversion completion status
            if self.notifier and self.receipt_id:
                self.notifier.send_status_update(
                    self.receipt_id, "processing",
                    f"Konwersja PDF zakończona ({len(images)} stron)", 40
                )

            return images

        except Exception as e:
            logger.error(f"❌ Error converting PDF to images: {e}", exc_info=True)
            return []

    def _parse_mistral_response(self, response_data: dict) -> list[ProductSchema]:
        """
        Parse Mistral OCR API response into our ProductSchema format.

        Expected Mistral response format:
        {
            "pages": [...],
            "extracted_items": [
                {
                    "description": "Product name",
                    "price": 9.99,
                    "quantity": 1.0,
                    "category": "optional"
                }
            ],
            "total": 99.99
        }
        """
        items = []

        try:
            # Extract items from different possible response structures
            extracted_items = []

            if "extracted_items" in response_data:
                extracted_items = response_data["extracted_items"]
            elif "items" in response_data:
                extracted_items = response_data["items"]
            elif "products" in response_data:
                extracted_items = response_data["products"]
            else:
                logger.warning("⚠️  No items found in Mistral response")
                return items

            for item in extracted_items:
                try:
                    # Handle different field name variations
                    product_name = (
                        item.get("description") or
                        item.get("name") or
                        item.get("product_name") or
                        str(item)
                    )

                    # Extract price - handle both string and numeric
                    price = item.get("price", 0)
                    if isinstance(price, str):
                        price = float(price.replace(",", "."))
                    price = float(price)

                    # Extract quantity - default to 1.0 if not specified
                    quantity = item.get("quantity", 1.0)
                    if isinstance(quantity, str):
                        quantity = float(quantity.replace(",", "."))
                    quantity = float(quantity)

                    # Skip if essential data is missing
                    if not product_name or price <= 0:
                        logger.warning(f"⚠️  Skipping invalid item: {item}")
                        continue

                    # Create ProductSchema
                    product_schema = ProductSchema(
                        product_name=str(product_name).strip(),
                        quantity=quantity,
                        unit=item.get("unit", "szt."),
                        price=price
                    )

                    items.append(product_schema)
                    logger.debug(f"📦 Added product: {product_name} - {price} x {quantity}")

                except (ValueError, TypeError) as e:
                    logger.warning(f"⚠️  Error parsing item {item}: {e}")
                    continue

            logger.info(f"✅ Successfully parsed {len(items)} items from Mistral response")
            return items

        except Exception as e:
            logger.error(f"❌ Error parsing Mistral response: {e}", exc_info=True)
            return []

    def is_available(self) -> bool:
        """Check if Mistral OCR service is available and configured."""
        return bool(self.api_key)


# Singleton instance for easy importing
mistral_ocr_service = MistralOcrService()
