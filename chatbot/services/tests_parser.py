"""
Tests for receipt parser service.
"""

from datetime import datetime
from decimal import Decimal

from django.test import TestCase

from .receipt_parser import (
    ParsedProduct,
    ParsedReceipt,
    RegexReceiptParser,
    get_receipt_parser,
)


class ParsedProductTest(TestCase):
    """Test ParsedProduct dataclass."""

    def test_parsed_product_creation(self):
        """Test creating ParsedProduct instance."""
        product = ParsedProduct(
            name="Mleko 3,2%",
            quantity=1.0,
            unit_price=Decimal("2.99"),
            total_price=Decimal("2.99"),
            unit="szt",
            confidence=0.9,
            raw_line="Mleko 3,2% 1 x 2,99 = 2,99",
        )

        self.assertEqual(product.name, "Mleko 3,2%")
        self.assertEqual(product.quantity, 1.0)
        self.assertEqual(product.unit_price, Decimal("2.99"))
        self.assertEqual(product.total_price, Decimal("2.99"))
        self.assertEqual(product.unit, "szt")
        self.assertEqual(product.confidence, 0.9)


class ParsedReceiptTest(TestCase):
    """Test ParsedReceipt dataclass."""

    def test_parsed_receipt_creation(self):
        """Test creating ParsedReceipt instance."""
        receipt = ParsedReceipt(
            store_name="Biedronka", total_amount=Decimal("15.47"), products=[]
        )

        self.assertEqual(receipt.store_name, "Biedronka")
        self.assertEqual(receipt.total_amount, Decimal("15.47"))
        self.assertEqual(len(receipt.products), 0)

    def test_to_dict_conversion(self):
        """Test converting receipt to dictionary."""
        product = ParsedProduct(
            name="Test Product", total_price=Decimal("5.99"), confidence=0.8
        )

        receipt = ParsedReceipt(
            store_name="Test Store",
            total_amount=Decimal("5.99"),
            transaction_date=datetime(2024, 1, 15, 14, 30),
            products=[product],
        )

        receipt_dict = receipt.to_dict()

        self.assertEqual(receipt_dict["store_name"], "Test Store")
        self.assertEqual(receipt_dict["total_amount"], "5.99")
        self.assertEqual(receipt_dict["transaction_date"], "2024-01-15T14:30:00")
        self.assertEqual(len(receipt_dict["products"]), 1)
        self.assertEqual(receipt_dict["products"][0]["name"], "Test Product")


class RegexReceiptParserTest(TestCase):
    """Test RegexReceiptParser implementation."""

    def setUp(self):
        """Set up test parser."""
        self.parser = RegexReceiptParser()

    def test_parser_initialization(self):
        """Test parser initialization."""
        self.assertIsInstance(self.parser.store_patterns, dict)
        self.assertIn("biedronka", self.parser.store_patterns)
        self.assertIn("tesco", self.parser.store_patterns)
        self.assertTrue(len(self.parser.product_patterns) > 0)

    def test_clean_text(self):
        """Test text cleaning functionality."""
        text = "  Line 1  \n\n  Line 2   \n\n\n  Line 3  "
        lines = self.parser._clean_text(text)

        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], "Line 1")
        self.assertEqual(lines[1], "Line 2")
        self.assertEqual(lines[2], "Line 3")

    def test_extract_store_name_biedronka(self):
        """Test store name extraction for Biedronka."""
        lines = ["BIEDRONKA SP. Z O.O.", "ul. Testowa 123", "00-000 Warszawa"]

        store_name = self.parser._extract_store_name(lines)
        self.assertEqual(store_name, "Biedronka")

    def test_extract_store_name_tesco(self):
        """Test store name extraction for Tesco."""
        lines = ["TESCO Stores Sp. z o.o.", "ul. Przykładowa 45", "Data: 15.01.2024"]

        store_name = self.parser._extract_store_name(lines)
        self.assertEqual(store_name, "Tesco")

    def test_extract_tax_id(self):
        """Test tax ID (NIP) extraction."""
        lines = ["BIEDRONKA SP. Z O.O.", "NIP: 123-456-78-90", "ul. Testowa 123"]

        tax_id = self.parser._extract_tax_id(lines)
        self.assertEqual(tax_id, "123-456-78-90")

    def test_extract_receipt_number(self):
        """Test receipt number extraction."""
        lines = ["PARAGON FISKALNY", "Nr 123/456/789", "Data: 15.01.2024"]

        receipt_num = self.parser._extract_receipt_number(lines)
        self.assertEqual(receipt_num, "123/456/789")

    def test_extract_date(self):
        """Test date extraction."""
        lines = ["BIEDRONKA SP. Z O.O.", "15.01.2024 14:30", "Kasjer: 001"]

        date = self.parser._extract_date(lines)
        self.assertIsNotNone(date)
        self.assertEqual(date.year, 2024)
        self.assertEqual(date.month, 1)
        self.assertEqual(date.day, 15)
        self.assertEqual(date.hour, 14)
        self.assertEqual(date.minute, 30)

    def test_extract_total_amount(self):
        """Test total amount extraction."""
        lines = [
            "Produkt 1                5,99",
            "Produkt 2                3,50",
            "SUMA:                   9,49",
            "Gotówka:               10,00",
        ]

        total = self.parser._extract_total_amount(lines)
        self.assertEqual(total, Decimal("9.49"))

    def test_looks_like_product(self):
        """Test product line detection."""
        # Positive cases
        self.assertTrue(self.parser._looks_like_product("Mleko 3,2% 1L 2,99"))
        self.assertTrue(self.parser._looks_like_product("Chleb graham    3,50"))
        self.assertTrue(self.parser._looks_like_product("Masło extra 200g 5,99"))

        # Negative cases
        self.assertFalse(self.parser._looks_like_product("NIP: 123-456-78-90"))
        self.assertFalse(self.parser._looks_like_product("Tel: +48 123 456 789"))
        self.assertFalse(self.parser._looks_like_product(""))
        self.assertFalse(self.parser._looks_like_product("AB"))  # Too short
        self.assertFalse(self.parser._looks_like_product("12345"))  # Only numbers

    def test_parse_product_line_simple(self):
        """Test parsing simple product line."""
        line = "Mleko 3,2% 1L                2,99"
        product = self.parser._parse_product_line(line, 1)

        self.assertIsNotNone(product)
        self.assertEqual(product.name, "Mleko 3,2% 1L")
        self.assertEqual(product.total_price, Decimal("2.99"))
        self.assertEqual(product.line_number, 1)
        self.assertGreater(product.confidence, 0)

    def test_parse_product_line_with_quantity(self):
        """Test parsing product line with quantity and unit price."""
        line = "Jabłka 2 x 3,50 = 7,00"
        product = self.parser._parse_product_line(line, 2)

        self.assertIsNotNone(product)
        self.assertEqual(product.name, "Jabłka")
        self.assertEqual(product.quantity, 2.0)
        self.assertEqual(product.unit_price, Decimal("3.50"))
        self.assertEqual(product.total_price, Decimal("7.00"))

    def test_parse_empty_text(self):
        """Test parsing empty text."""
        receipt = self.parser.parse("")

        self.assertIsInstance(receipt, ParsedReceipt)
        self.assertIsNone(receipt.store_name)
        self.assertEqual(len(receipt.products), 0)

    def test_parse_simple_biedronka_receipt(self):
        """Test parsing a simple Biedronka receipt."""
        receipt_text = """BIEDRONKA SP. Z O.O.
ul. Przykładowa 123
00-000 Warszawa
NIP: 123-456-78-90

PARAGON FISKALNY
Nr 123/456/789
15.01.2024 14:30
Kasjer: 001

Mleko 3,2% 1L                2,99
Chleb graham                 3,50
Masło extra 200g             5,99

SUMA:                       12,48
Gotówka:                    15,00
Reszta:                      2,52

Dziękujemy za zakupy!
"""

        receipt = self.parser.parse(receipt_text)

        # Check store information
        self.assertEqual(receipt.store_name, "Biedronka")
        self.assertEqual(receipt.store_tax_id, "123-456-78-90")
        self.assertEqual(receipt.receipt_number, "123/456/789")

        # Check date
        self.assertIsNotNone(receipt.transaction_date)
        self.assertEqual(receipt.transaction_date.year, 2024)
        self.assertEqual(receipt.transaction_date.month, 1)
        self.assertEqual(receipt.transaction_date.day, 15)

        # Check total
        self.assertEqual(receipt.total_amount, Decimal("12.48"))

        # Check products
        self.assertEqual(len(receipt.products), 3)

        # Check first product
        product1 = receipt.products[0]
        self.assertEqual(product1.name, "Mleko 3,2% 1L")
        self.assertEqual(product1.total_price, Decimal("2.99"))

        # Check second product
        product2 = receipt.products[1]
        self.assertEqual(product2.name, "Chleb graham")
        self.assertEqual(product2.total_price, Decimal("3.50"))

        # Check third product
        product3 = receipt.products[2]
        self.assertEqual(product3.name, "Masło extra 200g")
        self.assertEqual(product3.total_price, Decimal("5.99"))

    def test_parse_tesco_receipt_with_quantities(self):
        """Test parsing Tesco receipt with quantities."""
        receipt_text = """TESCO STORES SP. Z O.O.
Warszawa, ul. Testowa 45
NIP: 987-654-32-10

RECEIPT
NO: 456789
Date: 16/01/2024 16:45

Apples 1.5 kg x 4.50 = 6.75
Bread Whole Grain    3.20
Butter 250g 2 x 5.99 = 11.98

TOTAL:              21.93
CARD:               21.93

Thank you for shopping!
"""

        receipt = self.parser.parse(receipt_text)

        # Check store information
        self.assertEqual(receipt.store_name, "Tesco")
        self.assertEqual(receipt.receipt_number, "456789")

        # Check total
        self.assertEqual(receipt.total_amount, Decimal("21.93"))

        # Check products
        self.assertEqual(len(receipt.products), 3)

        # Check product with quantity
        apple_product = receipt.products[0]
        self.assertEqual(apple_product.name, "Apples")
        self.assertEqual(apple_product.quantity, 1.5)
        self.assertEqual(apple_product.unit_price, Decimal("4.50"))
        self.assertEqual(apple_product.total_price, Decimal("6.75"))

    def test_parse_malformed_receipt(self):
        """Test parsing malformed receipt text."""
        receipt_text = """Some random text
123456789
More random text without proper format
"""

        receipt = self.parser.parse(receipt_text)

        # Should still create receipt object but with minimal data
        self.assertIsInstance(receipt, ParsedReceipt)
        # May extract some data depending on heuristics
        self.assertIsNotNone(receipt)


class ReceiptParserFactoryTest(TestCase):
    """Test receipt parser factory function."""

    def test_get_receipt_parser(self):
        """Test getting default parser instance."""
        parser = get_receipt_parser()

        self.assertIsInstance(parser, RegexReceiptParser)
        self.assertIsNotNone(parser.store_patterns)
        self.assertIsNotNone(parser.product_patterns)


class ReceiptServiceIntegrationTest(TestCase):
    """Integration test for ReceiptService with parser."""

    def setUp(self):
        """Set up test data."""
        from django.utils import timezone

        from inventory.models import Receipt

        from ..services.receipt_service import ReceiptService

        self.service = ReceiptService()

        # Create test receipt with OCR data
        self.receipt = Receipt.objects.create(
            purchased_at=timezone.now(),
            total=Decimal("0.00"),  # Will be updated after parsing
            source_file_path="/fake/receipt.pdf",
            status="ocr_completed",
            raw_text={
                "text": """BIEDRONKA SP. Z O.O.
ul. Przykładowa 123
NIP: 123-456-78-90

PARAGON FISKALNY
Nr 456789
15.01.2024 14:30

Mleko 3,2% 1L                2,99
Chleb graham                 3,50
Masło extra 200g             5,99

SUMA:                       12,48
Gotówka:                    15,00
""",
                "confidence": 0.9,
                "backend": "test_backend",
            },
        )

    def test_process_receipt_parsing_success(self):
        """Test successful receipt parsing integration."""
        success = self.service.process_receipt_parsing(self.receipt.id)

        self.assertTrue(success)

        # Reload receipt to check updates
        self.receipt.refresh_from_db()

        self.assertEqual(self.receipt.status, "parsing_completed")
        self.assertIsInstance(self.receipt.parsed_data, dict)
        self.assertIn("products", self.receipt.parsed_data)
        self.assertIn("store_name", self.receipt.parsed_data)
        self.assertIn("Parsing completed", self.receipt.processing_notes)

    def test_process_receipt_parsing_wrong_status(self):
        """Test parsing with wrong receipt status."""
        # Change status to something other than ocr_completed
        self.receipt.status = "pending_ocr"
        self.receipt.save()

        success = self.service.process_receipt_parsing(self.receipt.id)

        self.assertFalse(success)

    def test_process_receipt_parsing_no_ocr_text(self):
        """Test parsing with no OCR text."""
        self.receipt.raw_text = {}
        self.receipt.save()

        success = self.service.process_receipt_parsing(self.receipt.id)

        self.assertFalse(success)

        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, "error")

    def test_process_receipt_parsing_empty_text(self):
        """Test parsing with empty OCR text."""
        self.receipt.raw_text = {"text": ""}
        self.receipt.save()

        success = self.service.process_receipt_parsing(self.receipt.id)

        self.assertFalse(success)

        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, "error")
