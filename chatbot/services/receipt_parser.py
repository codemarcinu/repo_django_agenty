"""
Receipt parser service for extracting structured data from OCR text.
Implements pattern matching and heuristics for Polish retail receipts.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

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

    def __post_init__(self):
        if self.products is None:
            self.products = []

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

        # Price patterns (Polish format: 12,34 or 12.34)
        self.price_patterns = [
            r"(\d{1,4})[,.](\d{2})\s*(?:zł|PLN|A)?",  # 12,34 zł or 12.34
            r"(\d{1,4})[,.](\d{2})$",  # Just the number at end of line
        ]

        # Product line patterns
        self.product_patterns = [
            # Pattern: NAME QUANTITY x UNIT_PRICE = TOTAL_PRICE
            r"^(.+?)\s+(\d+(?:[,.]?\d+)?)\s*x\s*(\d+[,.]?\d{2})\s*=?\s*(\d+[,.]?\d{2})",
            # Pattern: NAME TOTAL_PRICE [A/B/C] (tax code)
            r"^(.+?)\s+(\d+[,.]?\d{2})\s*[ABC]?\s*$",
            # Pattern: NAME QUANTITY UNIT_PRICE TOTAL_PRICE
            r"^(.+?)\s+(\d+(?:[,.]?\d+)?)\s+(\d+[,.]?\d{2})\s+(\d+[,.]?\d{2})",
            # Pattern: NAME TOTAL_PRICE (simple)
            r"^(.+?)\s+(\d+[,.]?\d{2})$",
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
            r"(?:SUMA|RAZEM|TOTAL|ŁĄCZNIE|LACZNIE)[\s:]*(\d+[,.]?\d{2})",
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

            if pattern_index == 0:  # NAME QUANTITY x UNIT_PRICE = TOTAL_PRICE
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

            elif pattern_index == 1:  # NAME TOTAL_PRICE [TAX]
                name, total_price = groups
                return ParsedProduct(
                    name=name.strip(),
                    total_price=Decimal(total_price.replace(",", ".")),
                    line_number=line_number,
                    confidence=0.7,
                    raw_line=line,
                )

            elif pattern_index == 2:  # NAME QUANTITY UNIT_PRICE TOTAL_PRICE
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

            elif pattern_index == 3:  # NAME TOTAL_PRICE (simple)
                name, total_price = groups
                return ParsedProduct(
                    name=name.strip(),
                    total_price=Decimal(total_price.replace(",", ".")),
                    line_number=line_number,
                    confidence=0.6,
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


def get_receipt_parser() -> ReceiptParser:
    """Get default receipt parser instance."""
    return RegexReceiptParser()
