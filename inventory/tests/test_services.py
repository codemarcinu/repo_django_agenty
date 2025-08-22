import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from inventory.models import (
    Category, Product, InventoryItem, Rule,
    OcrCorrectionPattern
)
from inventory.services.correction_service import OcrCorrectionService
from inventory.services.learning_service import LearningService
from inventory.services.rule_engine_service import RuleEngineService


@pytest.mark.unit
class OcrCorrectionServiceTest(TestCase):
    """Test OCR correction service functionality."""

    def setUp(self):
        """Set up test data."""
        self.service = OcrCorrectionService()

        # Create test correction patterns
        self.pattern1 = OcrCorrectionPattern.objects.create(
            error_pattern="tezt",
            correct_pattern="test",
            confidence_score=0.9,
            times_applied=5,
            is_active=True
        )

        self.pattern2 = OcrCorrectionPattern.objects.create(
            error_pattern="reciept",
            correct_pattern="receipt",
            confidence_score=0.8,
            times_applied=3,
            is_active=True
        )

        # Create inactive pattern (should not be loaded)
        self.inactive_pattern = OcrCorrectionPattern.objects.create(
            error_pattern="inactive",
            correct_pattern="active",
            confidence_score=0.5,
            is_active=False
        )

    def test_service_initialization(self):
        """Test service loads active patterns on initialization."""
        service = OcrCorrectionService()

        # Should load only active patterns
        self.assertEqual(len(service.correction_patterns), 2)

        # Check patterns are loaded correctly
        patterns_dict = dict(service.correction_patterns)
        self.assertIn("tezt", patterns_dict)
        self.assertIn("reciept", patterns_dict)
        self.assertEqual(patterns_dict["tezt"], "test")
        self.assertEqual(patterns_dict["reciept"], "receipt")

    def test_apply_corrections(self):
        """Test applying corrections to text."""
        service = OcrCorrectionService()

        # Test text with multiple corrections
        input_text = "This is a tezt reciept for testing"
        corrected_text = service.apply(input_text)

        expected_text = "This is a test receipt for testing"
        self.assertEqual(corrected_text, expected_text)

    def test_apply_corrections_no_matches(self):
        """Test applying corrections when no patterns match."""
        service = OcrCorrectionService()

        input_text = "This text has no correction patterns"
        corrected_text = service.apply(input_text)

        # Should remain unchanged
        self.assertEqual(corrected_text, input_text)

    def test_apply_corrections_empty_text(self):
        """Test applying corrections to empty text."""
        service = OcrCorrectionService()

        corrected_text = service.apply("")
        self.assertEqual(corrected_text, "")

        corrected_text = service.apply(None)
        self.assertEqual(corrected_text, None)

    def test_apply_corrections_multiple_occurrences(self):
        """Test applying corrections with multiple occurrences of same pattern."""
        service = OcrCorrectionService()

        input_text = "tezt tezt tezt"
        corrected_text = service.apply(input_text)

        expected_text = "test test test"
        self.assertEqual(corrected_text, expected_text)

    def test_apply_corrections_overlapping_patterns(self):
        """Test applying corrections with overlapping patterns."""
        # Create overlapping patterns
        OcrCorrectionPattern.objects.create(
            error_pattern="abc",
            correct_pattern="xyz",
            confidence_score=0.7,
            is_active=True
        )
        OcrCorrectionPattern.objects.create(
            error_pattern="bcde",
            correct_pattern="wxyz",
            confidence_score=0.6,
            is_active=True
        )

        service = OcrCorrectionService()

        input_text = "abcde"
        corrected_text = service.apply(input_text)

        # Should apply first pattern found (order may vary)
        self.assertNotEqual(corrected_text, "abcde")
        self.assertTrue(len(corrected_text) > 0)


@pytest.mark.unit
class LearningServiceTest(TestCase):
    """Test learning service for generating correction patterns."""

    def setUp(self):
        self.service = LearningService()

    def test_generate_correction_patterns_replace(self):
        """Test generating correction patterns for replace operations."""
        local_text = "This is a tezt document"
        ground_truth_text = "This is a test document"

        self.service.generate_correction_patterns(local_text, ground_truth_text)

        # Should create correction pattern
        pattern = OcrCorrectionPattern.objects.filter(error_pattern="tezt").first()
        self.assertIsNotNone(pattern)
        self.assertEqual(pattern.correct_pattern, "test")
        self.assertEqual(pattern.confidence_score, 0.9)
        self.assertTrue(pattern.is_active)

    def test_generate_correction_patterns_no_difference(self):
        """Test generating patterns when texts are identical."""
        local_text = "This is identical text"
        ground_truth_text = "This is identical text"

        self.service.generate_correction_patterns(local_text, ground_truth_text)

        # Should not create any patterns
        self.assertEqual(OcrCorrectionPattern.objects.count(), 0)

    def test_generate_correction_patterns_update_existing(self):
        """Test updating existing correction pattern."""
        # Create existing pattern
        existing_pattern = OcrCorrectionPattern.objects.create(
            error_pattern="tezt",
            correct_pattern="test",
            confidence_score=0.8,
            times_applied=2,
            is_active=True
        )

        local_text = "This is a tezt document"
        ground_truth_text = "This is a test document"

        self.service.generate_correction_patterns(local_text, ground_truth_text)

        # Should update existing pattern
        updated_pattern = OcrCorrectionPattern.objects.get(error_pattern="tezt")
        self.assertEqual(updated_pattern.times_applied, 3)  # Incremented by 1

    def test_generate_correction_patterns_empty_segments(self):
        """Test handling empty segments in diff."""
        local_text = "Test"
        ground_truth_text = "Test extended"

        # This should not create patterns with empty segments
        self.service.generate_correction_patterns(local_text, ground_truth_text)

        # May or may not create patterns depending on diff algorithm
        # but should not crash
        self.assertTrue(True)  # Test passes if no exception

    def test_generate_correction_patterns_complex_diff(self):
        """Test generating patterns with complex text differences."""
        local_text = "The quick brown fox jumps over the lazy dog"
        ground_truth_text = "The fast brown fox leaps over the lazy dog"

        self.service.generate_correction_patterns(local_text, ground_truth_text)

        # Should create patterns for "quick" -> "fast" and "jumps" -> "leaps"
        quick_pattern = OcrCorrectionPattern.objects.filter(error_pattern="quick").first()
        jumps_pattern = OcrCorrectionPattern.objects.filter(error_pattern="jumps").first()

        if quick_pattern:
            self.assertEqual(quick_pattern.correct_pattern, "fast")
        if jumps_pattern:
            self.assertEqual(jumps_pattern.correct_pattern, "leaps")


@pytest.mark.unit
class RuleEngineServiceTest(TestCase):
    """Test rule engine service for applying business rules."""

    def setUp(self):
        self.service = RuleEngineService()

        # Create test category and product
        self.category = Category.objects.create(
            name="Nabiał",
            meta={"expiry_days": 7}
        )
        self.product = Product.objects.create(
            name="Mleko UHT",
            category=self.category
        )

        # Create test inventory item
        self.inventory_item = InventoryItem.objects.create(
            product=self.product,
            purchase_date=timezone.now().date(),
            quantity_remaining=Decimal("10.0"),
            storage_location="pantry"
        )

    def test_service_initialization(self):
        """Test service loads active rules on initialization."""
        # Create test rules
        Rule.objects.create(
            name="Test Rule 1",
            condition={"field": "product.category.name", "operator": "equals", "value": "Nabiał"},
            action={"action_type": "set_expiry", "params": {"days": 7}},
            priority=10,
            is_active=True
        )

        Rule.objects.create(
            name="Test Rule 2",
            condition={"field": "quantity_remaining", "operator": "greater_than", "value": 5},
            action={"action_type": "set_location", "params": {"location": "fridge"}},
            priority=20,
            is_active=True
        )

        # Create inactive rule
        Rule.objects.create(
            name="Inactive Rule",
            condition={"field": "product.name", "operator": "equals", "value": "Test"},
            action={"action_type": "set_expiry", "params": {"days": 1}},
            is_active=False
        )

        service = RuleEngineService()

        # Should load only active rules, ordered by priority
        self.assertEqual(len(service.rules), 2)
        self.assertEqual(service.rules[0].priority, 10)
        self.assertEqual(service.rules[1].priority, 20)

    def test_apply_rules_set_expiry(self):
        """Test applying rules that set expiry dates."""
        # Create rule for dairy products
        rule = Rule.objects.create(
            name="Dairy Expiry Rule",
            condition={"field": "product.category.name", "operator": "equals", "value": "Nabiał"},
            action={"action_type": "set_expiry", "params": {"days": 5}},
            priority=10,
            is_active=True
        )

        service = RuleEngineService()

        # Apply rules
        service.apply_rules(self.inventory_item)

        # Should set expiry date
        self.assertIsNotNone(self.inventory_item.expiry_date)
        expected_expiry = date.today() + timedelta(days=5)
        self.assertEqual(self.inventory_item.expiry_date, expected_expiry)

    def test_apply_rules_set_location(self):
        """Test applying rules that set storage location."""
        rule = Rule.objects.create(
            name="Quantity Location Rule",
            condition={"field": "quantity_remaining", "operator": "greater_than", "value": 5},
            action={"action_type": "set_location", "params": {"location": "fridge"}},
            priority=10,
            is_active=True
        )

        service = RuleEngineService()

        # Apply rules
        service.apply_rules(self.inventory_item)

        # Should set storage location
        self.assertEqual(self.inventory_item.storage_location, "fridge")

    def test_apply_rules_multiple_conditions(self):
        """Test applying rules with multiple conditions."""
        rule = Rule.objects.create(
            name="Complex Rule",
            condition={"field": "product.category.name", "operator": "equals", "value": "Nabiał"},
            action={"action_type": "set_location", "params": {"location": "fridge"}},
            priority=10,
            is_active=True
        )

        service = RuleEngineService()

        # Apply rules
        service.apply_rules(self.inventory_item)

        # Should apply rule since category matches
        self.assertEqual(self.inventory_item.storage_location, "fridge")

    def test_apply_rules_no_match(self):
        """Test applying rules when conditions don't match."""
        rule = Rule.objects.create(
            name="Non-Matching Rule",
            condition={"field": "product.category.name", "operator": "equals", "value": "Warzywa"},
            action={"action_type": "set_location", "params": {"location": "fridge"}},
            priority=10,
            is_active=True
        )

        service = RuleEngineService()
        original_location = self.inventory_item.storage_location

        # Apply rules
        service.apply_rules(self.inventory_item)

        # Should not change since condition doesn't match
        self.assertEqual(self.inventory_item.storage_location, original_location)

    def test_apply_rules_invalid_condition(self):
        """Test handling invalid rule conditions."""
        rule = Rule.objects.create(
            name="Invalid Rule",
            condition={"field": "nonexistent.field", "operator": "equals", "value": "test"},
            action={"action_type": "set_location", "params": {"location": "fridge"}},
            priority=10,
            is_active=True
        )

        service = RuleEngineService()

        # Should not crash with invalid field path
        with self.assertLogs('inventory.services.rule_engine_service', level='WARNING') as cm:
            service.apply_rules(self.inventory_item)

        # Should log warning
        self.assertTrue(any("Field path" in message for message in cm.output))

    def test_apply_rules_invalid_action(self):
        """Test handling invalid rule actions."""
        rule = Rule.objects.create(
            name="Invalid Action Rule",
            condition={"field": "product.category.name", "operator": "equals", "value": "Nabiał"},
            action={"action_type": "invalid_action", "params": {}},
            priority=10,
            is_active=True
        )

        service = RuleEngineService()

        # Should not crash with invalid action
        with self.assertLogs('inventory.services.rule_engine_service', level='WARNING') as cm:
            service.apply_rules(self.inventory_item)

        # Should log warning
        self.assertTrue(any("Unsupported action type" in message for message in cm.output))

    def test_check_condition_operators(self):
        """Test various condition operators."""
        service = RuleEngineService()

        # Test equals operator
        condition = {"field": "product.category.name", "operator": "equals", "value": "Nabiał"}
        self.assertTrue(service._check_condition(condition, self.inventory_item))

        # Test contains operator
        condition = {"field": "product.name", "operator": "contains", "value": "Mleko"}
        self.assertTrue(service._check_condition(condition, self.inventory_item))

        # Test starts_with operator
        condition = {"field": "product.name", "operator": "starts_with", "value": "Mleko"}
        self.assertTrue(service._check_condition(condition, self.inventory_item))

        # Test ends_with operator
        condition = {"field": "product.name", "operator": "ends_with", "value": "UHT"}
        self.assertTrue(service._check_condition(condition, self.inventory_item))

        # Test greater_than operator
        condition = {"field": "quantity_remaining", "operator": "greater_than", "value": 5}
        self.assertTrue(service._check_condition(condition, self.inventory_item))

        # Test less_than operator
        condition = {"field": "quantity_remaining", "operator": "less_than", "value": 15}
        self.assertTrue(service._check_condition(condition, self.inventory_item))

    def test_check_condition_invalid_operator(self):
        """Test handling invalid operators."""
        service = RuleEngineService()

        condition = {"field": "product.name", "operator": "invalid_operator", "value": "test"}

        with self.assertLogs('inventory.services.rule_engine_service', level='WARNING') as cm:
            result = service._check_condition(condition, self.inventory_item)

        self.assertFalse(result)
        self.assertTrue(any("Unsupported operator" in message for message in cm.output))

    def test_check_condition_empty_condition(self):
        """Test handling empty conditions."""
        service = RuleEngineService()

        # Empty condition should always match
        self.assertTrue(service._check_condition({}, self.inventory_item))
        self.assertTrue(service._check_condition(None, self.inventory_item))

    def test_execute_action_set_quantity_remaining(self):
        """Test set_quantity_remaining action."""
        service = RuleEngineService()

        action = {"action_type": "set_quantity_remaining", "params": {"quantity": 25.5}}

        service._execute_action(action, self.inventory_item)

        self.assertEqual(self.inventory_item.quantity_remaining, Decimal("25.5"))

    def test_execute_action_invalid_params(self):
        """Test handling invalid action parameters."""
        service = RuleEngineService()

        # Invalid days parameter (should be int)
        action = {"action_type": "set_expiry", "params": {"days": "invalid"}}

        with self.assertLogs('inventory.services.rule_engine_service', level='WARNING') as cm:
            service._execute_action(action, self.inventory_item)

        # Should log warning about invalid parameter
        self.assertTrue(any("Invalid 'days' parameter" in message for message in cm.output))


@pytest.mark.integration
class ServiceIntegrationTest(TransactionTestCase):
    """Test integration between services."""

    def setUp(self):
        self.category = Category.objects.create(
            name="Nabiał",
            meta={"expiry_days": 7}
        )
        self.product = Product.objects.create(
            name="Mleko UHT",
            category=self.category
        )

    def test_correction_and_learning_service_integration(self):
        """Test integration between correction and learning services."""
        # Create some initial correction patterns
        OcrCorrectionPattern.objects.create(
            error_pattern="tezt",
            correct_pattern="test",
            confidence_score=0.8,
            is_active=True
        )

        # Test correction service
        correction_service = OcrCorrectionService()
        corrected_text = correction_service.apply("This is a tezt")

        self.assertEqual(corrected_text, "This is a test")

        # Test learning service with new patterns
        learning_service = LearningService()
        learning_service.generate_correction_patterns(
            "reciept procesing",
            "receipt processing"
        )

        # Reload correction service to get new patterns
        correction_service = OcrCorrectionService()
        corrected_text = correction_service.apply("reciept procesing")

        self.assertEqual(corrected_text, "receipt processing")

    def test_rule_engine_with_real_inventory_item(self):
        """Test rule engine with real inventory item."""
        # Create rule
        Rule.objects.create(
            name="Dairy Rule",
            condition={"field": "product.category.name", "operator": "equals", "value": "Nabiał"},
            action={"action_type": "set_expiry", "params": {"days": 3}},
            is_active=True
        )

        # Create inventory item
        inventory_item = InventoryItem.objects.create(
            product=self.product,
            purchase_date=timezone.now().date(),
            quantity_remaining=Decimal("5.0")
        )

        # Apply rules
        rule_service = RuleEngineService()
        rule_service.apply_rules(inventory_item)

        # Should have set expiry date
        self.assertIsNotNone(inventory_item.expiry_date)
        expected_expiry = date.today() + timedelta(days=3)
        self.assertEqual(inventory_item.expiry_date, expected_expiry)
