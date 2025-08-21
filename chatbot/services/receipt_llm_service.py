"""
LLM service for receipt product extraction with caching and error handling.
"""

import json
import logging
from typing import Any

from django.conf import settings

from ..services.agents import OllamaAgent
from .cache_service import cache_service
from .exceptions_receipt import LLMError

logger = logging.getLogger(__name__)


class ReceiptLLMService:
    """Service for LLM-based product extraction from receipt text."""

    def __init__(self):
        self.model_name = getattr(settings, 'RECEIPT_LLM_MODEL', 'qwen2:7b')  # Updated to default text model
        self.ollama_config = getattr(settings, 'RECEIPT_OLLAMA_CONFIG', {})
        self.timeout = getattr(settings, 'RECEIPT_LLM_TIMEOUT', 180)
        self.max_retry_attempts = getattr(settings, 'RECEIPT_LLM_MAX_RETRIES', 2)

    def _create_ollama_agent(self) -> OllamaAgent:
        """Create OllamaAgent instance with configured settings."""
        config = {
            "model": self.model_name,
            **self.ollama_config
        }
        return OllamaAgent(config=config)

    def _create_extraction_prompt(self, receipt_text: str) -> str:
        """Create optimized prompt for product extraction."""
        return f"""
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
{receipt_text}

Wyodrębnione produkty (tylko JSON):
"""

    async def _parse_llm_response(self, response_text: str) -> list[dict[str, Any]]:
        """Parse LLM response and extract JSON products data."""
        try:
            # Find JSON array in response
            json_start = response_text.find("[")
            json_end = response_text.rfind("]")

            if json_start == -1 or json_end == -1 or json_end <= json_start:
                logger.warning("❌ LLM response did not contain valid JSON array")
                logger.debug(f"Problematic response: {response_text}")
                raise LLMError(
                    "LLM response format invalid - no JSON array found",
                    model_name=self.model_name,
                    details={"response_preview": response_text[:200]}
                )

            json_string = response_text[json_start:json_end + 1]
            logger.debug(f"Extracted JSON string: {json_string}")

            products_data = json.loads(json_string)

            if not isinstance(products_data, list):
                raise LLMError(
                    "LLM response is not a list",
                    model_name=self.model_name,
                    details={"response_type": type(products_data).__name__}
                )

            # Validate each product entry
            validated_products = []
            for i, product in enumerate(products_data):
                if not isinstance(product, dict):
                    logger.warning(f"Product {i} is not a dictionary, skipping")
                    continue

                if not product.get("product"):
                    logger.warning(f"Product {i} has no product name, skipping")
                    continue

                # Ensure required fields with defaults
                validated_product = {
                    "product": str(product["product"]).strip(),
                    "quantity": float(product.get("quantity", 1.0)),
                    "unit": str(product.get("unit", "szt.")).strip(),
                }

                # Add optional fields if present
                if "purchase_date" in product:
                    validated_product["purchase_date"] = product["purchase_date"]

                validated_products.append(validated_product)

            logger.info(f"✅ Successfully parsed {len(validated_products)} products from LLM response")
            return validated_products

        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON decoding error from LLM response: {e}")
            logger.debug(f"Problematic response: {response_text}")
            raise LLMError(
                f"JSON parsing failed: {str(e)}",
                model_name=self.model_name,
                details={"json_error": str(e), "response_preview": response_text[:200]}
            )

    async def extract_products_with_retry(self, receipt_text: str) -> list[dict[str, Any]]:
        """Extract products with retry logic and caching."""
        if not receipt_text or not receipt_text.strip():
            logger.warning("No receipt text provided to LLM")
            return []

        logger.info("🤖 Starting LLM product extraction...")
        logger.debug(f"Input text length: {len(receipt_text)} characters")
        logger.debug(f"Input text preview: {receipt_text[:300]}...")

        # Check cache first
        text_hash = cache_service.get_text_hash(receipt_text)
        try:
            cached_result = await cache_service.get_cached_llm_result(text_hash)
            if cached_result:
                logger.info(f"✅ Using cached LLM result for text hash {text_hash[:8]}...")
                return cached_result
        except Exception as e:
            logger.warning(f"Cache retrieval failed for LLM: {e}")

        # Prepare prompt and agent
        prompt = self._create_extraction_prompt(receipt_text)
        logger.debug(f"Prepared LLM prompt (length: {len(prompt)} chars)")

        ollama_agent = self._create_ollama_agent()

        # Retry logic
        last_error = None
        for attempt in range(self.max_retry_attempts):
            try:
                logger.info(f"LLM attempt {attempt + 1}/{self.max_retry_attempts}")

                # Check Ollama health first
                if not await ollama_agent.health_check_ollama():
                    error_msg = "Ollama service is not available for receipt processing"
                    logger.error(error_msg)
                    raise LLMError(error_msg, model_name=self.model_name)

                # Call Ollama directly to avoid fallback system
                response = await ollama_agent.process_with_ollama({
                    "message": prompt,
                    "history": []
                })

                if not response.success:
                    error_msg = f"LLM processing failed: {response.error}"
                    logger.error(error_msg)
                    raise LLMError(error_msg, model_name=self.model_name)

                llm_response_text = response.data.get("response", "").strip()
                logger.info(f"✅ LLM response received (length: {len(llm_response_text)} chars)")
                logger.debug(f"LLM raw response: {llm_response_text}")

                # Parse response
                products_data = await self._parse_llm_response(llm_response_text)

                # Cache successful result
                if products_data:
                    try:
                        await cache_service.cache_llm_result(text_hash, products_data)
                    except Exception as e:
                        logger.warning(f"Failed to cache LLM result: {e}")

                logger.info(f"✅ LLM extraction completed successfully with {len(products_data)} products")
                return products_data

            except LLMError:
                # Re-raise LLM errors as-is
                raise
            except Exception as e:
                last_error = e
                logger.warning(f"LLM attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retry_attempts - 1:
                    logger.info(f"Retrying LLM extraction (attempt {attempt + 2})...")
                    continue

        # All attempts failed
        error_msg = f"LLM extraction failed after {self.max_retry_attempts} attempts"
        if last_error:
            error_msg += f": {str(last_error)}"

        logger.error(f"❌ {error_msg}")
        raise LLMError(error_msg, model_name=self.model_name, details={"last_error": str(last_error)})

    async def extract_products(self, receipt_text: str) -> list[dict[str, Any]]:
        """Main method to extract products from receipt text."""
        try:
            return await self.extract_products_with_retry(receipt_text)
        except LLMError:
            # Re-raise LLM errors
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error during LLM product extraction: {e}", exc_info=True)
            raise LLMError(f"Unexpected error: {str(e)}", model_name=self.model_name)

    def get_service_info(self) -> dict[str, Any]:
        """Get service configuration and status information."""
        return {
            "model_name": self.model_name,
            "timeout": self.timeout,
            "max_retry_attempts": self.max_retry_attempts,
            "config": self.ollama_config
        }


# Global LLM service instance
receipt_llm_service = ReceiptLLMService()
