"""
Receipt parser service for extracting structured data from OCR text.
Implements pattern matching and heuristics for Polish retail receipts.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ParsedProduct:
    """Parsed product information from receipt."""

    name: str
    quantity: float | None = None
    unit_price: Decimal | None = None
    total_price: Decimal | None = None
    unit: str | None = None
    category: str | None = None
    discount: Decimal | None = None
    tax_rate: str | None = None
    line_number: int | None = None
    confidence: float = 0.0
    raw_line: str | None = None


@dataclass
class ParsedReceipt:
    """Complete parsed receipt information."""

    store_name: str | None = None
    store_address: str | None = None
    store_tax_id: str | None = None
    receipt_number: str | None = None
    cashier_id: str | None = None
    transaction_date: datetime | None = None
    total_amount: Decimal | None = None
    tax_amount: Decimal | None = None
    payment_method: str | None = None
    products: list[ParsedProduct] = None
    meta: dict[str, Any] = None

    def __post_init__(self):
        if self.products is None:
            self.products = []
        if self.meta is None:
            self.meta = {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "store_name": self.store_name,
            "store_address": self.store_address,
            "store_tax_id": self.store_tax_id,
            "receipt_number": self.receipt_number,
            "cashier_id": self.cashier_id,
            "transaction_date": (
                self.transaction_date.isoformat() if self.transaction_date else None
            ),
            "total_amount": str(self.total_amount) if self.total_amount else None,
            "tax_amount": str(self.tax_amount) if self.tax_amount else None,
            "payment_method": self.payment_method,
            "products": [
                {
                    "name": p.name,
                    "quantity": p.quantity,
                    "unit_price": str(p.unit_price) if p.unit_price else None,
                    "total_price": str(p.total_price) if p.total_price else None,
                    "unit": p.unit,
                    "category": p.category,
                    "discount": str(p.discount) if p.discount else None,
                    "tax_rate": p.tax_rate,
                    "line_number": p.line_number,
                    "confidence": p.confidence,
                    "raw_line": p.raw_line,
                }
                for p in self.products
            ],
        }


class ReceiptParser:
    """Base receipt parser interface."""

    def parse(self, ocr_text: str) -> ParsedReceipt:
        """Parse OCR text into structured receipt data."""
        raise NotImplementedError


class StoreDetector:
    """Detects store type from receipt text."""
    
    def __init__(self):
        """Initialize store detection patterns."""
        self.store_signatures = {
            "lidl": {
                "patterns": [r"lidl\s+sp\.\s*z\s*o\.\s*o\.", r"lidl"],
                "confidence_threshold": 0.9,
                "characteristics": ["* format", "tax codes A/B/C", "PTU sections"]
            },
            "biedronka": {
                "patterns": [r"biedronka", r"ladybird"],
                "confidence_threshold": 0.8,
                "characteristics": ["different format"]
            },
            "kaufland": {
                "patterns": [r"kaufland"],
                "confidence_threshold": 0.8,
                "characteristics": ["german format"]
            },
            "tesco": {
                "patterns": [r"tesco"],
                "confidence_threshold": 0.8,
                "characteristics": ["international format"]
            }
        }
    
    def detect_store(self, ocr_text: str) -> tuple[str | None, float]:
        """
        Detect store type from OCR text.
        
        Returns:
            Tuple of (store_name, confidence)
        """
        if not ocr_text:
            return None, 0.0
            
        text_lower = ocr_text.lower()
        
        for store_name, config in self.store_signatures.items():
            for pattern in config["patterns"]:
                if re.search(pattern, text_lower):
                    # Additional validation for higher confidence
                    confidence = config["confidence_threshold"]
                    
                    # Boost confidence if we find characteristic elements
                    if store_name == "lidl":
                        if "*" in ocr_text and re.search(r"[ABC]\s*$", ocr_text, re.MULTILINE):
                            confidence = 0.95
                        if "PTU" in ocr_text.upper():
                            confidence = min(confidence + 0.05, 1.0)
                    
                    return store_name, confidence
        
        return None, 0.0


class RegexReceiptParser(ReceiptParser):
    """Regex-based receipt parser for Polish retail receipts."""

    def __init__(self):
        """Initialize parser with Polish retail patterns."""

        # Store chain patterns
        self.store_patterns = {
            "biedronka": [r"biedronka", r"ladybird"],
            "tesco": [r"tesco"],
            "carrefour": [r"carrefour"],
            "auchan": [r"auchan"],
            "kaufland": [r"kaufland"],
            "lidl": [r"lidl"],
            "żabka": [r"żabka", r"zabka"],
            "netto": [r"netto"],
            "polo_market": [r"polo\s*market"],
            "dino": [r"dino"],
            "intermarche": [r"intermarche"],
            "mila": [r"mila"],
        }

        # Price patterns (Polish format: 12,34 or 12.34, also handles formats like 1234c = 12.34)
        self.price_patterns = [
            r"(\d{1,4})[,.](\d{2})\s*(?:zł|PLN|A)?",  # 12,34 zł or 12.34
            r"(\d{1,4})[,.](\d{2})$",  # Just the number at end of line
            r"(\d{3,6})c",  # Format like 1234c = 12.34 PLN
            r"(\d{1,4})\s*[,.]?\s*(\d{2})\s*(?:PLN|zł|€|C)$",  # Various endings
        ]

        # Product line patterns
        self.product_patterns = [
            # NEW: Lidl format - NAME QUANTITY * UNIT_PRICE TOTAL_PRICE TAX_CODE
            r"^(.+?)\s+(\d+(?:[,.]?\d+)?)\s*\*\s*(\d+[,.]?\d{2})\s+(\d+[,.]?\d{2})\s+[ABC]\s*$",
            # Pattern: NAME QUANTITY x UNIT_PRICE = TOTAL_PRICE
            r"^(.+?)\s+(\d+(?:[,.]?\d+)?)\s*x\s*(\d+[,.]?\d{2})\s*=?\s*(\d+[,.]?\d{2})",
            # Pattern: NAME TOTAL_PRICE [A/B/C] (tax code)
            r"^(.+?)\s+(\d+[,.]?\d{2})\s*[ABC]?\s*$",
            # Pattern: NAME QUANTITY UNIT_PRICE TOTAL_PRICE
            r"^(.+?)\s+(\d+(?:[,.]?\d+)?)\s+(\d+[,.]?\d{2})\s+(\d+[,.]?\d{2})",
            # Pattern: NAME TOTAL_PRICE (simple)
            r"^(.+?)\s+(\d+[,.]?\d{2})$",
            # Pattern: Auchan-style PRODUCT_CODE_WITH_PRICE like "492359C" = 49.23 PLN
            r"^(\d{2,6})\s*([Cc€])\s*$",
        ]

        # Date patterns
        self.date_patterns = [
            r"(\d{1,2})[.-](\d{1,2})[.-](\d{4})\s+(\d{1,2}):(\d{2})",  # dd.mm.yyyy hh:mm
            r"(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2}):(\d{2})",  # yyyy-mm-dd hh:mm
            r"(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})",  # dd/mm/yyyy hh:mm
        ]

        # Tax ID pattern (NIP)
        self.tax_id_pattern = r"NIP:?\s*(\d{3}[-\s]?\d{3}[-\s]?\d{2}[-\s]?\d{2})"

        # Receipt number patterns
        self.receipt_patterns = [
            r"(?:PARAGON|RACHUNEK|RECEIPT)[\s#:]*(\d+(?:/\d+)*)",
            r"(?:Nr|NO|NUM)[\s.:#]*(\d+(?:/\d+)*)",
        ]

        # Total amount patterns
        self.total_patterns = [
            r"(?:RAZEM|TOTAL)[\s:]*(\d+[,.]?\d{2})",  # Prefer RAZEM for main total
            r"(?:SUMA|ŁĄCZNIE|LACZNIE)[\s:]*(\d+[,.]?\d{2})",
            r"(?:DO ZAPŁATY|DO ZAPLATY)[\s:]*(\d+[,.]?\d{2})",
        ]

    def parse(self, ocr_text: str) -> ParsedReceipt:
        """Parse OCR text into structured receipt data."""
        if not ocr_text or not ocr_text.strip():
            logger.warning("Empty OCR text provided to parser")
            return ParsedReceipt()

        logger.info(f"Parsing receipt text: {len(ocr_text)} characters")

        # Clean and normalize text
        lines = self._clean_text(ocr_text)

        receipt = ParsedReceipt()

        try:
            # Parse store information
            receipt.store_name = self._extract_store_name(lines)
            receipt.store_address = self._extract_store_address(lines)
            receipt.store_tax_id = self._extract_tax_id(lines)

            # Parse transaction details
            receipt.receipt_number = self._extract_receipt_number(lines)
            receipt.transaction_date = self._extract_date(lines)
            receipt.total_amount = self._extract_total_amount(lines)

            # Parse products
            receipt.products = self._extract_products(lines)
            
            # VALIDATION: Logical validation of products
            receipt.products = self._validate_products(receipt.products)

            logger.info(
                f"Parsed receipt: {len(receipt.products)} products, total: {receipt.total_amount}"
            )
            return receipt

        except Exception as e:
            logger.error(f"Error parsing receipt: {str(e)}", exc_info=True)
            return ParsedReceipt()

    def _clean_text(self, text: str) -> list[str]:
        """Clean and normalize OCR text."""
        # Split into lines and clean each line
        lines = []
        for line in text.split("\n"):
            # Remove extra whitespace
            line = " ".join(line.split())
            # Skip empty lines
            if line.strip():
                lines.append(line.strip())

        return lines

    def _extract_store_name(self, lines: list[str]) -> str | None:
        """Extract store name from receipt lines."""
        # Check first few lines for store name
        for i, line in enumerate(lines[:5]):
            line_lower = line.lower()

            for store, patterns in self.store_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, line_lower):
                        logger.debug(f"Found store: {store} in line: {line}")
                        return store.replace("_", " ").title()

        # If no pattern matches, return first line if it looks like a store name
        if lines and len(lines[0]) > 3 and not re.search(r"\d", lines[0]):
            return lines[0]

        return None

    def _extract_store_address(self, lines: list[str]) -> str | None:
        """Extract store address from receipt lines."""
        # Look for address-like patterns in first few lines
        for line in lines[:10]:
            # Address typically contains numbers and common address words
            if re.search(r"\d+.*(?:ul\.|al\.|pl\.|str\.|street|avenue)", line.lower()):
                return line
            # Or postal code pattern
            if re.search(r"\d{2}-\d{3}", line):
                return line

        return None

    def _extract_tax_id(self, lines: list[str]) -> str | None:
        """Extract tax ID (NIP) from receipt lines."""
        for line in lines:
            match = re.search(self.tax_id_pattern, line)
            if match:
                return match.group(1)

        return None

    def _extract_receipt_number(self, lines: list[str]) -> str | None:
        """Extract receipt number from receipt lines."""
        for line in lines:
            for pattern in self.receipt_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    return match.group(1)

        return None

    def _extract_date(self, lines: list[str]) -> datetime | None:
        """Extract transaction date from receipt lines."""
        for line in lines:
            for pattern in self.date_patterns:
                match = re.search(pattern, line)
                if match:
                    try:
                        if len(match.groups()) == 5:  # dd.mm.yyyy hh:mm
                            day, month, year, hour, minute = match.groups()
                            if pattern.startswith(r"(\d{4})"):  # yyyy-mm-dd format
                                year, month, day = match.groups()[:3]
                            return datetime(
                                int(year), int(month), int(day), int(hour), int(minute)
                            )
                    except ValueError as e:
                        logger.warning(f"Invalid date format in line '{line}': {e}")
                        continue

        return None

    def _extract_total_amount(self, lines: list[str]) -> Decimal | None:
        """Extract total amount from receipt lines."""
        for line in lines:
            for pattern in self.total_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    try:
                        amount_str = match.group(1).replace(",", ".")
                        return Decimal(amount_str)
                    except InvalidOperation:
                        continue

        # Fallback: look for largest amount in the receipt
        amounts = []
        for line in lines:
            for pattern in self.price_patterns:
                matches = re.findall(pattern, line)
                for match in matches:
                    try:
                        if isinstance(match, tuple):
                            amount_str = f"{match[0]}.{match[1]}"
                        else:
                            amount_str = match.replace(",", ".")
                        amounts.append(Decimal(amount_str))
                    except InvalidOperation:
                        continue

        if amounts:
            return max(amounts)  # Return largest amount as likely total

        return None

    def _extract_products(self, lines: list[str]) -> list[ParsedProduct]:
        """Extract products from receipt lines."""
        products = []

        # Skip header lines (store info, date, etc.) - typically first 5-10 lines
        product_start = self._find_products_start(lines)
        product_end = self._find_products_end(lines)

        logger.debug(f"Product lines range: {product_start} to {product_end}")

        for i, line in enumerate(lines[product_start:product_end], start=product_start):
            product = self._parse_product_line(line, i)
            if product:
                products.append(product)

        return products

    def _find_products_start(self, lines: list[str]) -> int:
        """Find where product listing starts."""
        # Look for common product section indicators
        for i, line in enumerate(lines):
            line_lower = line.lower()

            # Skip obvious header information
            if any(
                keyword in line_lower
                for keyword in [
                    "nip",
                    "tax",
                    "adres",
                    "address",
                    "tel",
                    "phone",
                    "www",
                    "email",
                ]
            ):
                continue

            # Look for first line that looks like a product
            if self._looks_like_product(line):
                return max(0, i - 1)  # Start one line before for safety

        # Default: start after first 5 lines
        return min(5, len(lines) // 3)

    def _find_products_end(self, lines: list[str]) -> int:
        """Find where product listing ends."""
        # Look for total/summary section
        for i, line in enumerate(lines):
            line_lower = line.lower()

            # CRITICAL FIX: Add PTU and Kwota as end indicators
            if re.match(r"^ptu\s+[abc]", line_lower):
                return i
                
            if re.match(r"^kwota\s+[abc]", line_lower):
                return i

            # Common end-of-products indicators
            if any(
                keyword in line_lower
                for keyword in [
                    "suma",
                    "razem", 
                    "total",
                    "łącznie",
                    "lacznie",
                    "do zapłaty",
                    "do zaplaty",
                    "payment",
                    "płatność",
                    "platnosc",
                    "gotówka",
                    "gotowka",
                    "karta",
                    "card",
                    "reszta",
                    "change",
                ]
            ):
                return i

        # Default: use most of the lines
        return len(lines)

    def _looks_like_product(self, line: str) -> bool:
        """Check if line looks like a product entry."""
        # Must contain letters (product name)
        if not re.search(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]", line):
            return False

        # Should contain a price
        if not re.search(r"\d+[,.]?\d{2}", line):
            return False

        # Should not be too short
        if len(line.strip()) < 5:
            return False

        # Should not start with common non-product indicators
        line_lower = line.lower().strip()
        if line_lower.startswith(("tel", "nip", "www", "email", "adres")):
            return False

        # CRITICAL FIX: Exclude tax/summary lines
        if re.match(r"^ptu\s+[abc]\s+\d+[,.]?\d{2}", line_lower):
            return False
        
        if re.match(r"^kwota\s+[abc]\s+\d+[,.]?\d+%?\s+\d+[,.]?\d{2}", line_lower):
            return False
            
        if line_lower.startswith(("suma", "razem", "total", "łącznie", "lacznie")):
            return False

        return True

    def _parse_product_line(self, line: str, line_number: int) -> ParsedProduct | None:
        """Parse a single product line."""
        if not self._looks_like_product(line):
            return None

        logger.debug(f"Parsing product line {line_number}: {line}")

        # Try each product pattern
        for i, pattern in enumerate(self.product_patterns):
            match = re.search(pattern, line)
            if match:
                return self._extract_product_from_match(match, line, line_number, i)

        # Fallback: try to extract name and price
        return self._extract_simple_product(line, line_number)

    def _extract_product_from_match(
        self, match, line: str, line_number: int, pattern_index: int
    ) -> ParsedProduct | None:
        """Extract product information from regex match."""
        try:
            groups = match.groups()

            if pattern_index == 0:  # NEW: Lidl format - NAME QUANTITY * UNIT_PRICE TOTAL_PRICE TAX_CODE
                name, quantity, unit_price, total_price = groups
                return ParsedProduct(
                    name=name.strip(),
                    quantity=float(quantity.replace(",", ".")),
                    unit_price=Decimal(unit_price.replace(",", ".")),
                    total_price=Decimal(total_price.replace(",", ".")),
                    line_number=line_number,
                    confidence=0.95,  # Highest confidence for Lidl format
                    raw_line=line,
                )

            elif pattern_index == 1:  # NAME QUANTITY x UNIT_PRICE = TOTAL_PRICE
                name, quantity, unit_price, total_price = groups
                return ParsedProduct(
                    name=name.strip(),
                    quantity=float(quantity.replace(",", ".")),
                    unit_price=Decimal(unit_price.replace(",", ".")),
                    total_price=Decimal(total_price.replace(",", ".")),
                    line_number=line_number,
                    confidence=0.9,
                    raw_line=line,
                )

            elif pattern_index == 2:  # NAME TOTAL_PRICE [TAX]
                name, total_price = groups
                return ParsedProduct(
                    name=name.strip(),
                    total_price=Decimal(total_price.replace(",", ".")),
                    line_number=line_number,
                    confidence=0.7,
                    raw_line=line,
                )

            elif pattern_index == 3:  # NAME QUANTITY UNIT_PRICE TOTAL_PRICE
                name, quantity, unit_price, total_price = groups
                return ParsedProduct(
                    name=name.strip(),
                    quantity=float(quantity.replace(",", ".")),
                    unit_price=Decimal(unit_price.replace(",", ".")),
                    total_price=Decimal(total_price.replace(",", ".")),
                    line_number=line_number,
                    confidence=0.8,
                    raw_line=line,
                )

            elif pattern_index == 4:  # NAME TOTAL_PRICE (simple)
                name, total_price = groups
                return ParsedProduct(
                    name=name.strip(),
                    total_price=Decimal(total_price.replace(",", ".")),
                    line_number=line_number,
                    confidence=0.6,
                    raw_line=line,
                )

            elif pattern_index == 5:  # Auchan-style PRODUCT_CODE_WITH_PRICE
                price_code, currency_code = groups
                # Convert format like "492359C" to "49.23" PLN (last 2 digits = cents)
                if len(price_code) >= 2:
                    if len(price_code) == 2:
                        # For 2-digit codes like "99C", treat as 0.99 PLN
                        total_price = Decimal(f"0.{price_code}")
                    else:
                        # For longer codes, last 2 digits are cents
                        price_major = price_code[:-2]
                        price_minor = price_code[-2:]
                        total_price = Decimal(f"{price_major}.{price_minor}")
                    
                    return ParsedProduct(
                        name=f"Product {price_code}",  # Placeholder name
                        total_price=total_price,
                        line_number=line_number,
                        confidence=0.5,  # Lower confidence due to missing name
                        raw_line=line,
                    )

        except (ValueError, InvalidOperation, IndexError) as e:
            logger.warning(f"Failed to parse product from line '{line}': {e}")
            return None

        return None

    def _extract_simple_product(
        self, line: str, line_number: int
    ) -> ParsedProduct | None:
        """Extract product using simple heuristics."""
        # Find all prices in the line
        prices = []
        for pattern in self.price_patterns:
            matches = re.finditer(pattern, line)
            for match in matches:
                try:
                    if match.groups():
                        if len(match.groups()) == 2:
                            price_str = f"{match.group(1)}.{match.group(2)}"
                        elif pattern == r"(\d{3,6})c":  # Handle "1234c" format
                            price_code = match.group(1)
                            if len(price_code) >= 3:
                                price_str = f"{price_code[:-2]}.{price_code[-2:]}"
                            else:
                                continue
                        else:
                            price_str = match.group(0).replace(",", ".")
                    else:
                        price_str = match.group(0).replace(",", ".")

                    # Clean price string
                    price_str = re.sub(r"[^\d.]", "", price_str)
                    prices.append((Decimal(price_str), match.start()))
                except (InvalidOperation, ValueError):
                    continue

        if not prices:
            return None

        # Use the last (rightmost) price as total price
        total_price, price_pos = prices[-1]

        # Extract name (everything before the price)
        name = line[:price_pos].strip()

        # Remove common suffixes
        name = re.sub(
            r"\s+\d+(?:[,.]?\d+)?\s*(?:kg|g|l|ml|szt|pcs)?\s*$",
            "",
            name,
            flags=re.IGNORECASE,
        )
        name = name.strip()

        if len(name) < 2:
            return None

        return ParsedProduct(
            name=name,
            total_price=total_price,
            line_number=line_number,
            confidence=0.5,
            raw_line=line,
        )

    def _validate_products(self, products: list[ParsedProduct]) -> list[ParsedProduct]:
        """Validate products using logical checks."""
        validated_products = []
        
        for product in products:
            # Skip products with validation issues
            if self._is_valid_product(product):
                validated_products.append(product)
            else:
                logger.debug(f"Skipping invalid product: {product.name} ({product.raw_line})")
                
        return validated_products
        
    def _is_valid_product(self, product: ParsedProduct) -> bool:
        """Check if product passes logical validation."""
        # Must have a name
        if not product.name or len(product.name.strip()) < 2:
            return False
            
        # Must have price information
        if not product.total_price or product.total_price <= 0:
            return False
            
        # If we have quantity and unit price, validate calculation
        if product.quantity and product.unit_price:
            calculated_total = Decimal(str(product.quantity)) * product.unit_price
            if abs(calculated_total - product.total_price) > Decimal("0.02"):  # Allow 2 cent tolerance
                logger.debug(f"Price calculation mismatch for {product.name}: {calculated_total} vs {product.total_price}")
                # Don't reject, just lower confidence
                product.confidence *= 0.8
                
        # Reject obvious non-products
        name_lower = product.name.lower()
        if any(keyword in name_lower for keyword in ["ptu", "kwota", "suma", "razem", "total"]):
            return False
            
        return True


class LidlReceiptParser(RegexReceiptParser):
    """Specialized parser for Lidl receipts."""
    
    def __init__(self):
        """Initialize Lidl-specific parser."""
        super().__init__()
        
        # Override with Lidl-specific patterns
        self.product_patterns = [
            # Lidl format: QTY * UNIT_PRICE TOTAL_PRICE (like "2 * 3, 59 7,18")
            r"^(\d+)\s*\*\s*(\d+)\s*,\s*(\d{2})\s+(\d+),(\d{2})$",
            # Lidl format: QTY * PRICE (like "1 * 0, 79")
            r"^(\d+)\s*\*\s*(\d+)\s*,\s*(\d{2})$",
            # Lidl format: just price (like "0, 79")
            r"^(\d+)\s*,\s*(\d{2})$",
            # Generic fallbacks
            r"^(.+?)\s+(\d+(?:[,.]?\d+)?)\s*x\s*(\d+[,.]?\d{2})\s*=?\s*(\d+[,.]?\d{2})",
            r"^(.+?)\s+(\d+[,.]?\d{2})$",
        ]
        
        # Lidl-specific total patterns
        self.total_patterns = [
            r"^RAZEM\s+(\d+[,.]?\d{2})$",  # RAZEM is always the final total for Lidl
            r"^Razem\s+(\d+[,.]?\d{2})$",
        ]
        
    def _extract_product_from_match(
        self, match, line: str, line_number: int, pattern_index: int
    ) -> ParsedProduct | None:
        """Extract product information from regex match for Lidl receipts."""
        try:
            groups = match.groups()

            if pattern_index == 0:  # QTY * UNIT_PRICE TOTAL_PRICE (like "2 * 3, 59 7,18")
                quantity, unit_major, unit_minor, total_major, total_minor = groups
                unit_price = Decimal(f"{unit_major}.{unit_minor}")
                total_price = Decimal(f"{total_major}.{total_minor}")
                
                return ParsedProduct(
                    name=f"Product (line {line_number})",  # Placeholder - name is usually on previous line
                    quantity=float(quantity),
                    unit_price=unit_price,
                    total_price=total_price,
                    line_number=line_number,
                    confidence=0.9,
                    raw_line=line,
                )

            elif pattern_index == 1:  # QTY * PRICE (like "1 * 0, 79")
                quantity, price_major, price_minor = groups
                total_price = Decimal(f"{price_major}.{price_minor}")
                unit_price = total_price / Decimal(quantity)
                
                return ParsedProduct(
                    name=f"Product (line {line_number})",  # Placeholder
                    quantity=float(quantity),
                    unit_price=unit_price,
                    total_price=total_price,
                    line_number=line_number,
                    confidence=0.8,
                    raw_line=line,
                )

            elif pattern_index == 2:  # Just price (like "0, 79")
                price_major, price_minor = groups
                total_price = Decimal(f"{price_major}.{price_minor}")
                
                return ParsedProduct(
                    name=f"Product (line {line_number})",  # Placeholder
                    total_price=total_price,
                    line_number=line_number,
                    confidence=0.6,
                    raw_line=line,
                )
                
            else:
                # Fall back to parent method for other patterns
                return super()._extract_product_from_match(match, line, line_number, pattern_index)

        except (ValueError, InvalidOperation, IndexError) as e:
            logger.warning(f"Failed to parse Lidl product from line '{line}': {e}")
            return None
        
    def _looks_like_product(self, line: str) -> bool:
        """Lidl-specific product detection."""
        line = line.strip()
        
        # Skip empty lines
        if not line:
            return False
            
        line_lower = line.lower()
        
        # Lidl-specific exclusions
        if re.match(r"^ptu\s+[abc]\s+\d+[,.]?\d{2}", line_lower):
            return False
        if re.match(r"^kwota\s+[abc]\s+\d+[,.]?\d+%?\s+\d+[,.]?\d{2}", line_lower):
            return False
        if line_lower.startswith(("suma", "razem", "ptu", "kwota")):
            return False
        if "www" in line_lower or "lidl.pl" in line_lower:
            return False
        if re.search(r"^\d{4}-\d{2}-\d{2}$", line):  # Date format
            return False
        if "tarnowo podgórne" in line_lower or "jankowice" in line_lower:
            return False
            
        # Lidl-specific inclusions
        # Lines with * multiplication (like "1 * 0, 79" or "2 * 3, 59 7,18")
        if "*" in line and re.search(r"\d+[,.]?\d{2}", line):
            return True
            
        # Lines that are just prices (like "0, 79")
        if re.match(r"^\d+\s*,\s*\d{2}$", line):
            return True
            
        # Product names that might not have prices on same line
        if any(c.isalpha() for c in line) and len(line) >= 3:
            # Could be a product name, but be conservative
            # Only accept if it's not obviously something else
            if not any(word in line_lower for word in ["płatność", "karta", "zł", "pln", "www", "tel", "adres"]):
                return True
            
        return False
    
    def _find_products_end(self, lines: list[str]) -> int:
        """Lidl-specific end detection."""
        for i, line in enumerate(lines):
            line_lower = line.lower()
            
            # PTU section always ends products in Lidl
            if re.match(r"^ptu\s+[abc]", line_lower):
                return i
                
            # Other end indicators
            if line_lower.startswith(("suma", "razem")):
                return i
                
        return len(lines)


class GenericReceiptParser(RegexReceiptParser):
    """Generic fallback parser for unknown receipt formats."""
    
    def __init__(self):
        """Initialize generic parser with broad patterns."""
        super().__init__()
        
        # More permissive patterns for unknown formats
        self.product_patterns = [
            # Standard patterns
            r"^(.+?)\s+(\d+(?:[,.]?\d+)?)\s*[x*]\s*(\d+[,.]?\d{2})\s*=?\s*(\d+[,.]?\d{2})",
            r"^(.+?)\s+(\d+[,.]?\d{2})\s*[ABC]?\s*$",
            r"^(.+?)\s+(\d+(?:[,.]?\d+)?)\s+(\d+[,.]?\d{2})\s+(\d+[,.]?\d{2})",
            r"^(.+?)\s+(\d+[,.]?\d{2})$",
            # Very permissive fallback
            r"^(.+?)\s+.*?(\d+[,.]?\d{2}).*$",
        ]


class AdaptiveReceiptParser(ReceiptParser):
    """
    Parser, który adaptacyjnie wybiera strategię w zależności od wykrytego sklepu.
    """
    def __init__(self):
        # Inicjalizujemy pusty słownik na parsery.
        self.parsers: Dict[str, ReceiptParser] = {}
        # Definiujemy domyślny parser, jeśli żaden inny nie pasuje.
        self.default_parser = RegexReceiptParser()
        logger.info(f"Initialized AdaptiveReceiptParser with default: {type(self.default_parser).__name__}")

    def register_parser(self, store_keyword: str, parser_instance: ReceiptParser):
        """
        Rejestruje instancję parsera dla danego słowa kluczowego sklepu.
        """
        self.parsers[store_keyword] = parser_instance
        logger.info(f"Registered parser {type(parser_instance).__name__} for keyword '{store_keyword}'")

    def _detect_store(self, text: str) -> Optional[str]:
        """
        Wykrywa sklep na podstawie słów kluczowych w tekście.
        """
        text_lower = text.lower()
        for keyword in self.parsers.keys():
            if keyword in text_lower:
                logger.debug(f"Detected store keyword: '{keyword}'")
                return keyword
        logger.debug("No specific store keyword detected.")
        return None

    def parse(self, text: str) -> ParsedReceipt:
        """
        Wybiera odpowiedni parser i przetwarza tekst.
        """
        store = self._detect_store(text)
        if store and store in self.parsers:
            parser = self.parsers[store]
            logger.info(f"Using {type(parser).__name__} for detected store '{store}'")
            return parser.parse(text)
        
        logger.info(f"No specific parser found, falling back to {type(self.default_parser).__name__}")
        return self.default_parser.parse(text)



