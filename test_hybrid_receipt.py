#!/usr/bin/env python3
"""
Test hybrydowego pipeline paragonów: PaddleOCR + Vision zgodnie z planem zmiana_modeli.md
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add Django setup
sys.path.append('/home/marcin/PycharmProjects/agenty')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings_dev')

import django
django.setup()

from chatbot.services.paddleocr_service import paddleocr_service
from chatbot.services.vision_service import vision_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_hybrid_pipeline(image_path: str):
    """
    Test hybrydowego pipeline zgodnie z planem:
    1. PaddleOCR → jeśli confidence >= 0.75 → przyjmij
    2. Jeśli nie → Vision (Qwen2.5-VL) → poproś o JSON z pozycjami
    3. Łączenie wyników
    """
    
    logger.info(f"🔄 Testowanie hybrydowego pipeline dla: {image_path}")
    
    if not os.path.exists(image_path):
        logger.error(f"❌ Plik nie istnieje: {image_path}")
        return None
    
    # FAZA 1: PaddleOCR
    logger.info("🔍 FAZA 1: PaddleOCR extraction")
    
    if not paddleocr_service.is_service_available():
        logger.warning("⚠️ PaddleOCR nie jest dostępny, przechodzę do Vision")
        ocr_text = ""
        ocr_confidence = 0.0
    else:
        try:
            ocr_results = paddleocr_service.extract_text_from_image(image_path)
            
            if ocr_results:
                # Calculate average confidence
                ocr_confidence = sum(r.confidence for r in ocr_results) / len(ocr_results)
                ocr_text = " ".join(r.text for r in ocr_results)
                
                high_conf_results = [r for r in ocr_results if r.confidence >= 0.75]
                high_conf_ratio = len(high_conf_results) / len(ocr_results)
                
                logger.info(f"✅ OCR: {len(ocr_results)} segments, avg confidence: {ocr_confidence:.2f}")
                logger.info(f"   High confidence ratio: {high_conf_ratio:.2f}")
                logger.info(f"   Text preview: {ocr_text[:200]}...")
                
            else:
                ocr_confidence = 0.0
                ocr_text = ""
                logger.warning("⚠️ OCR nie wydobył żadnego tekstu")
                
        except Exception as e:
            logger.error(f"❌ OCR error: {e}")
            ocr_confidence = 0.0
            ocr_text = ""
    
    # DECYZJA: czy użyć Vision
    use_vision = ocr_confidence < 0.75 or len(ocr_text.strip()) < 50
    
    if use_vision:
        logger.info("🖼️ FAZA 2: Vision analysis (OCR insufficient)")
        
        try:
            # Use receipt-specific analysis
            vision_result = await vision_service.analyze_receipt(image_path, "qwen2.5vl:7b")
            
            if vision_result.success:
                logger.info(f"✅ Vision analysis successful")
                logger.info(f"   Content length: {len(vision_result.content)}")
                logger.info(f"   Content preview: {vision_result.content[:300]}...")
                
                # Check if JSON was parsed
                if vision_result.metadata and "parsed_products" in vision_result.metadata:
                    products = vision_result.metadata["parsed_products"]
                    logger.info(f"✅ Vision extracted {len(products)} products")
                    for i, product in enumerate(products[:3]):  # Show first 3
                        logger.info(f"   Product {i+1}: {product}")
                else:
                    logger.info("⚠️ Vision response not parsed as JSON")
                
            else:
                logger.error(f"❌ Vision analysis failed: {vision_result.error}")
                vision_result = None
                
        except Exception as e:
            logger.error(f"❌ Vision error: {e}")
            vision_result = None
    else:
        logger.info("✅ SKIP Vision: OCR confidence sufficient")
        vision_result = None
    
    # FAZA 3: Łączenie wyników
    logger.info("🔄 FAZA 3: Hybrid result combination")
    
    final_result = {
        "strategy": "hybrid",
        "ocr_used": bool(ocr_text),
        "vision_used": use_vision,
        "primary_source": "vision" if use_vision and vision_result and vision_result.success else "ocr",
        "ocr_data": {
            "text": ocr_text,
            "confidence": ocr_confidence,
            "length": len(ocr_text)
        },
        "vision_data": {
            "success": vision_result.success if vision_result else False,
            "content": vision_result.content if vision_result and vision_result.success else "",
            "products": vision_result.metadata.get("parsed_products", []) if vision_result and vision_result.metadata else []
        } if vision_result else None
    }
    
    # Summary
    if final_result["primary_source"] == "ocr":
        logger.info(f"🎯 RESULT: Using OCR (confidence: {ocr_confidence:.2f})")
    elif final_result["vision_data"] and len(final_result["vision_data"]["products"]) > 0:
        products_count = len(final_result["vision_data"]["products"])
        logger.info(f"🎯 RESULT: Using Vision ({products_count} products extracted)")
    else:
        logger.info("⚠️ RESULT: Both methods failed or insufficient")
    
    return final_result

async def test_multiple_receipts():
    """Test pipeline na różnych typach obrazów"""
    
    test_files = [
        "/home/marcin/PycharmProjects/agenty/media/receipt_files/test_receipt.pdf",
        "/home/marcin/PycharmProjects/agenty/media/receipt_files/test_receipt.jpg", 
        "/home/marcin/PycharmProjects/agenty/media/receipt_files/test_receipt.png"
    ]
    
    results = {}
    
    for test_file in test_files:
        if os.path.exists(test_file):
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing: {test_file}")
            logger.info('='*60)
            
            result = await test_hybrid_pipeline(test_file)
            results[test_file] = result
        else:
            logger.info(f"⚠️ Skipping non-existent file: {test_file}")
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("📊 HYBRID PIPELINE TEST SUMMARY")
    logger.info('='*60)
    
    for file_path, result in results.items():
        if result:
            filename = Path(file_path).name
            strategy = result["primary_source"]
            success = "✅" if (
                strategy == "ocr" and result["ocr_data"]["confidence"] >= 0.75 or
                strategy == "vision" and result["vision_data"] and len(result["vision_data"]["products"]) > 0
            ) else "⚠️"
            
            logger.info(f"{success} {filename}: {strategy.upper()} strategy")

async def main():
    logger.info("🚀 Starting hybrid receipt pipeline test")
    
    # Check services availability
    logger.info("🔍 Checking services...")
    logger.info(f"PaddleOCR available: {paddleocr_service.is_service_available()}")
    
    qwen_available = await vision_service.check_model_availability("qwen2.5vl:7b")
    logger.info(f"Qwen2.5-VL available: {qwen_available}")
    
    if not paddleocr_service.is_service_available() and not qwen_available:
        logger.error("❌ Neither OCR nor Vision services available")
        return
    
    await test_multiple_receipts()

if __name__ == "__main__":
    asyncio.run(main())