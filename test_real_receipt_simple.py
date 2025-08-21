#!/usr/bin/env python
"""
Simple test z rzeczywistym paragonem - test tylko OCR
"""

import os

import django

# Ustaw Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings_dev')
django.setup()

from pathlib import Path

from chatbot.services.ocr_service import get_ocr_service
from chatbot.services.product_matcher import ProductMatcher
from chatbot.services.receipt_parser import get_receipt_parser
from inventory.models import Category, Product

# Katalog z testowymi paragonami
RECEIPTS_DIR = Path("paragony_do testów")

def test_real_receipt_ocr():
    """Test rzeczywisty OCR z prawdziwymi paragonami."""

    print("=== Test OCR z rzeczywistymi paragonami ===")

    ocr_service = get_ocr_service()
    if not ocr_service.is_available():
        print("❌ OCR service niedostępny")
        return

    print(f"✅ OCR service dostępny: {ocr_service.get_available_backends()}")

    # Testuj każdy paragon
    for receipt_file in RECEIPTS_DIR.glob("*"):
        if receipt_file.suffix.lower() in ['.pdf', '.png', '.jpg', '.jpeg']:
            print(f"\n🔄 Przetwarzanie: {receipt_file.name}")

            try:
                # OCR
                ocr_result = ocr_service.process_file(str(receipt_file))

                if ocr_result.success:
                    print(f"✅ OCR Success: {ocr_result.confidence:.2f} confidence")
                    print(f"📄 Tekst (pierwsze 200 znaków): {ocr_result.text[:200]}...")

                    # Parser
                    parser = get_receipt_parser()
                    parsed_receipt = parser.parse(ocr_result.text)

                    print(f"🏪 Sklep: {parsed_receipt.store_name}")
                    print(f"💰 Suma: {parsed_receipt.total_amount}")
                    print(f"🛒 Produkty: {len(parsed_receipt.products)}")

                    for i, product in enumerate(parsed_receipt.products[:3]):
                        print(f"   {i+1}. {product.name} - {product.total_price}")

                    if len(parsed_receipt.products) > 3:
                        print(f"   ... i {len(parsed_receipt.products) - 3} więcej")

                else:
                    print(f"❌ OCR Failed: {ocr_result.error_message}")

            except Exception as e:
                print(f"❌ Błąd: {e}")

def test_product_matching():
    """Test dopasowywania produktów."""

    print("\n=== Test dopasowywania produktów ===")

    # Stwórz testowe kategorie i produkty
    dairy_cat, _ = Category.objects.get_or_create(name="Nabiał")
    bread_cat, _ = Category.objects.get_or_create(name="Pieczywo")

    # Stwórz testowe produkty
    milk_product, _ = Product.objects.get_or_create(
        name="Mleko 3,2%",
        defaults={"category": dairy_cat, "aliases": ["mleko", "milk"]}
    )
    bread_product, _ = Product.objects.get_or_create(
        name="Chleb graham",
        defaults={"category": bread_cat, "aliases": ["chleb", "bread"]}
    )

    print(f"✅ Produkty w bazie: {Product.objects.count()}")

    matcher = ProductMatcher()

    # Test przykładowych nazw produktów z paragonów
    test_names = [
        "Mleko 3,2% 1L",
        "CHLEB GRAHAM 500G",
        "Masło extra 200g",
        "Banan żółty kg",
        "Nieznany Produkt XYZ"
    ]

    for name in test_names:
        from decimal import Decimal

        from chatbot.services.receipt_parser import ParsedProduct

        parsed = ParsedProduct(name=name, total_price=Decimal("5.99"))
        result = matcher.match_product(parsed)

        print(f"🔍 '{name}':")
        print(f"   ➜ {result.match_type}: {result.product.name if result.product else 'None'}")
        print(f"   ➜ Pewność: {result.confidence:.2f}")

if __name__ == "__main__":
    # Sprawdź czy istnieje katalog z paragonami
    if not RECEIPTS_DIR.exists():
        print(f"❌ Katalog {RECEIPTS_DIR} nie istnieje")
        exit(1)

    # Uruchom testy
    test_real_receipt_ocr()
    test_product_matching()

    print("\n✅ Testy zakończone!")
