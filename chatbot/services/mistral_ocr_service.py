# chatbot/services/mistral_ocr_service.py
import httpx
import logging
from pathlib import Path
from typing import Optional
from django.conf import settings
from asgiref.sync import async_to_sync

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

    async def extract_data_from_file(self, file_path: str) -> Optional[ParsedReceipt]:
        """
        Extract receipt data using Mistral OCR API.

        Args:
            file_path: Path to the receipt file (image or PDF)

        Returns:
            ParsedReceipt object with extracted items, or None if failed
        """
        logger.info(f"🚀 Sending receipt to Mistral OCR API: {file_path}")

        if not self.api_key:
            logger.error("❌ Mistral API key not configured")
            raise ValueError("Mistral API key not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }

        try:
            # Read file content
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            with open(file_path, "rb") as f:
                files = {"file": (file_path_obj.name, f, self._get_content_type(file_path))}
                data = {"model": "mistral-ocr-latest"}  # Specify OCR model

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    logger.info(f"📤 Making request to Mistral OCR API...")
                    response = await client.post(
                        self.api_url,
                        headers=headers,
                        files=files,
                        data=data
                    )
                    response.raise_for_status()

            # Parse Mistral API response
            response_data = response.json()
            logger.info(f"✅ Received response from Mistral OCR API")

            # Convert response to our internal format
            items = self._parse_mistral_response(response_data)

            logger.info(f"📊 Extracted {len(items)} products from Mistral OCR")
            return ParsedReceipt(items=items)

        except httpx.TimeoutException:
            logger.error(f"⏰ Timeout error with Mistral OCR API for file: {file_path}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"🔴 HTTP error with Mistral OCR API: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error in MistralOcrService: {e}", exc_info=True)
            raise

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
