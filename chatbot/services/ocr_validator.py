"""
Intelligent OCR Validation implementing Phase 2.3 of the receipt pipeline improvement plan.
Validates OCR results for logical consistency and quality.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """Represents a validation issue found in OCR results."""

    severity: ValidationSeverity
    code: str
    message: str
    field: str | None = None
    suggested_fix: str | None = None
    confidence: float = 1.0


@dataclass
class ValidationResult:
    """Result of OCR validation process."""

    is_valid: bool
    confidence_score: float
    issues: list[ValidationIssue]
    corrected_data: dict[str, Any] | None = None

    def get_issues_by_severity(self, severity: ValidationSeverity) -> list[ValidationIssue]:
        """Get issues filtered by severity."""
        return [issue for issue in self.issues if issue.severity == severity]

    def has_critical_issues(self) -> bool:
        """Check if there are any critical issues."""
        return any(issue.severity == ValidationSeverity.CRITICAL for issue in self.issues)

    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return any(issue.severity == ValidationSeverity.ERROR for issue in self.issues)


class OCRValidator:
    """
    Intelligent validator for OCR results from receipt processing.
    Performs logical validation and suggests corrections.
    """

    def __init__(self):
        """Initialize the OCR validator with Polish retail patterns."""

        # Polish currency patterns
        self.currency_patterns = [
            r'\b(\d{1,4})[,.](\d{2})\s*(?:zł|PLN|pln)\b',
            r'\b(\d{1,4})[,.](\d{2})\b',
            r'(\d{1,4}),(\d{2})',
            r'(\d{1,4})\.(\d{2})'
        ]

        # Common Polish store chains
        self.known_stores = {
            'biedronka', 'lidl', 'kaufland', 'carrefour', 'auchan',
            'tesco', 'żabka', 'zabka', 'netto', 'polo market',
            'dino', 'intermarche', 'mila', 'lewiatan', 'groszek'
        }

        # Common receipt keywords in Polish
        self.receipt_keywords = {
            'total': ['razem', 'suma', 'łącznie', 'do zapłaty', 'total'],
            'tax': ['ptu', 'vat', 'podatek'],
            'payment': ['gotówka', 'karta', 'płatność', 'zapłacono'],
            'date': ['data', 'date', 'dnia'],
            'items': ['szt', 'kg', 'l', 'ml', 'g', 'opak']
        }

        # Validation thresholds
        self.min_total_amount = Decimal('0.01')
        self.max_total_amount = Decimal('9999.99')
        self.max_reasonable_unit_price = Decimal('999.99')
        self.calculation_tolerance = Decimal('0.05')  # 5 cent tolerance for calculations

    def validate_receipt_data(self, ocr_text: str, parsed_data: dict[str, Any]) -> ValidationResult:
        """
        Validate OCR results and parsed receipt data.
        
        Args:
            ocr_text: Raw OCR text
            parsed_data: Parsed structured data
            
        Returns:
            ValidationResult with issues and suggestions
        """
        issues = []
        corrected_data = parsed_data.copy()

        # Basic text quality validation
        text_issues = self._validate_text_quality(ocr_text)
        issues.extend(text_issues)

        # Store name validation
        store_issues = self._validate_store_name(parsed_data.get('store_name'))
        issues.extend(store_issues)

        # Total amount validation
        total_issues, corrected_total = self._validate_total_amount(
            parsed_data.get('total_amount'),
            parsed_data.get('products', [])
        )
        issues.extend(total_issues)
        if corrected_total is not None:
            corrected_data['total_amount'] = corrected_total

        # Products validation
        products_issues, corrected_products = self._validate_products(parsed_data.get('products', []))
        issues.extend(products_issues)
        if corrected_products:
            corrected_data['products'] = corrected_products

        # Date validation
        date_issues = self._validate_date(parsed_data.get('transaction_date'))
        issues.extend(date_issues)

        # Cross-validation between OCR text and parsed data
        consistency_issues = self._validate_consistency(ocr_text, parsed_data)
        issues.extend(consistency_issues)

        # Calculate overall confidence
        confidence_score = self._calculate_confidence_score(issues, ocr_text, parsed_data)

        # Determine if validation passed
        is_valid = not any(issue.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]
                          for issue in issues)

        logger.info(f"OCR validation completed. Issues: {len(issues)}, Valid: {is_valid}, Confidence: {confidence_score:.2f}")

        return ValidationResult(
            is_valid=is_valid,
            confidence_score=confidence_score,
            issues=issues,
            corrected_data=corrected_data if corrected_data != parsed_data else None
        )

    def _validate_text_quality(self, text: str) -> list[ValidationIssue]:
        """Validate basic text quality from OCR."""
        issues = []

        if not text or not text.strip():
            issues.append(ValidationIssue(
                severity=ValidationSeverity.CRITICAL,
                code="EMPTY_TEXT",
                message="OCR returned empty text"
            ))
            return issues

        # Check text length
        if len(text.strip()) < 20:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="SHORT_TEXT",
                message=f"OCR text is very short ({len(text)} characters)",
                suggested_fix="Consider re-scanning the image with better lighting"
            ))

        # Check for excessive garbage characters
        printable_chars = sum(1 for c in text if c.isprintable())
        garbage_ratio = 1 - (printable_chars / len(text))

        if garbage_ratio > 0.3:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="HIGH_GARBAGE_RATIO",
                message=f"High ratio of non-printable characters ({garbage_ratio:.1%})",
                suggested_fix="OCR quality is poor, consider image preprocessing"
            ))

        # Check for receipt-like content
        has_numbers = bool(re.search(r'\d', text))
        has_currency = any(re.search(pattern, text, re.IGNORECASE) for pattern in self.currency_patterns)

        if not has_numbers:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="NO_NUMBERS",
                message="No numbers found in OCR text",
                suggested_fix="Verify this is a receipt image"
            ))

        if not has_currency:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="NO_CURRENCY",
                message="No currency amounts detected",
                suggested_fix="Check if image contains prices"
            ))

        return issues

    def _validate_store_name(self, store_name: str | None) -> list[ValidationIssue]:
        """Validate store name."""
        issues = []

        if not store_name:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="MISSING_STORE_NAME",
                message="Store name not detected",
                field="store_name"
            ))
            return issues

        # Check if it's a known store
        store_lower = store_name.lower()
        is_known_store = any(known in store_lower for known in self.known_stores)

        if not is_known_store:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO,
                code="UNKNOWN_STORE",
                message=f"Store '{store_name}' is not in known stores database",
                field="store_name",
                suggested_fix="Consider adding to known stores if valid"
            ))

        # Check for suspicious patterns
        if len(store_name) < 2:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="SHORT_STORE_NAME",
                message=f"Store name is very short: '{store_name}'",
                field="store_name"
            ))

        return issues

    def _validate_total_amount(self, total_amount: Any, products: list[dict]) -> tuple[list[ValidationIssue], Decimal | None]:
        """Validate total amount and compare with product sum."""
        issues = []
        corrected_total = None

        # Convert to Decimal if needed
        if total_amount is None:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="MISSING_TOTAL",
                message="Total amount not detected",
                field="total_amount"
            ))
            return issues, None

        try:
            if isinstance(total_amount, str):
                # Clean the string
                clean_amount = re.sub(r'[^\d,.]', '', total_amount)
                clean_amount = clean_amount.replace(',', '.')
                total_decimal = Decimal(clean_amount)
            else:
                total_decimal = Decimal(str(total_amount))
        except (InvalidOperation, ValueError):
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="INVALID_TOTAL_FORMAT",
                message=f"Invalid total amount format: '{total_amount}'",
                field="total_amount",
                suggested_fix="Check OCR quality for price detection"
            ))
            return issues, None

        # Check reasonable range
        if total_decimal < self.min_total_amount:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="UNREASONABLY_LOW_TOTAL",
                message=f"Total amount is very low: {total_decimal}",
                field="total_amount"
            ))

        if total_decimal > self.max_total_amount:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="UNREASONABLY_HIGH_TOTAL",
                message=f"Total amount is very high: {total_decimal}",
                field="total_amount"
            ))

        # Validate against product sum
        if products:
            product_sum = self._calculate_products_sum(products)
            if product_sum is not None:
                difference = abs(total_decimal - product_sum)

                if difference > self.calculation_tolerance:
                    severity = ValidationSeverity.ERROR if difference > Decimal('1.00') else ValidationSeverity.WARNING
                    issues.append(ValidationIssue(
                        severity=severity,
                        code="TOTAL_MISMATCH",
                        message=f"Total ({total_decimal}) doesn't match product sum ({product_sum}), difference: {difference}",
                        field="total_amount",
                        suggested_fix=f"Consider using calculated sum: {product_sum}"
                    ))

                    # Suggest correction if difference is small
                    if difference <= Decimal('0.50'):
                        corrected_total = product_sum

        return issues, corrected_total

    def _validate_products(self, products: list[dict]) -> tuple[list[ValidationIssue], list[dict] | None]:
        """Validate individual products."""
        issues = []
        corrected_products = []

        if not products:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="NO_PRODUCTS",
                message="No products detected in receipt",
                suggested_fix="Check OCR quality for product detection"
            ))
            return issues, None

        for i, product in enumerate(products):
            product_issues, corrected_product = self._validate_single_product(product, i)
            issues.extend(product_issues)
            corrected_products.append(corrected_product if corrected_product else product)

        # Check for duplicate products
        names = [p.get('name', '').lower() for p in products]
        duplicates = set([name for name in names if names.count(name) > 1 and name])

        if duplicates:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="DUPLICATE_PRODUCTS",
                message=f"Potential duplicate products detected: {list(duplicates)}",
                suggested_fix="Review if these are actually different items"
            ))

        return issues, corrected_products if any(corrected_products[i] != products[i] for i in range(len(products))) else None

    def _validate_single_product(self, product: dict, index: int) -> tuple[list[ValidationIssue], dict | None]:
        """Validate a single product."""
        issues = []
        corrected_product = None

        name = product.get('name', '')
        quantity = product.get('quantity')
        unit_price = product.get('unit_price')
        total_price = product.get('total_price')

        # Validate name
        if not name or len(name.strip()) < 2:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="SHORT_PRODUCT_NAME",
                message=f"Product {index + 1} has very short name: '{name}'",
                field=f"products[{index}].name"
            ))

        # Validate prices
        if unit_price is not None:
            try:
                unit_price_decimal = Decimal(str(unit_price))
                if unit_price_decimal > self.max_reasonable_unit_price:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        code="HIGH_UNIT_PRICE",
                        message=f"Product '{name}' has high unit price: {unit_price_decimal}",
                        field=f"products[{index}].unit_price"
                    ))
            except (InvalidOperation, ValueError):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="INVALID_UNIT_PRICE",
                    message=f"Product '{name}' has invalid unit price: '{unit_price}'",
                    field=f"products[{index}].unit_price"
                ))

        # Validate quantity vs price calculation
        if all(x is not None for x in [quantity, unit_price, total_price]):
            try:
                quantity_decimal = Decimal(str(quantity))
                unit_price_decimal = Decimal(str(unit_price))
                total_price_decimal = Decimal(str(total_price))

                calculated_total = quantity_decimal * unit_price_decimal
                difference = abs(calculated_total - total_price_decimal)

                if difference > self.calculation_tolerance:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        code="PRICE_CALCULATION_MISMATCH",
                        message=f"Product '{name}': {quantity} × {unit_price} ≠ {total_price} (diff: {difference})",
                        field=f"products[{index}]",
                        suggested_fix=f"Calculated total should be {calculated_total}"
                    ))
            except (InvalidOperation, ValueError):
                pass  # Already handled in individual validations

        return issues, corrected_product

    def _validate_date(self, transaction_date: Any) -> list[ValidationIssue]:
        """Validate transaction date."""
        issues = []

        if transaction_date is None:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO,
                code="MISSING_DATE",
                message="Transaction date not detected",
                field="transaction_date"
            ))
            return issues

        # Parse date if string
        if isinstance(transaction_date, str):
            try:
                parsed_date = datetime.fromisoformat(transaction_date.replace('Z', '+00:00'))
            except ValueError:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    code="INVALID_DATE_FORMAT",
                    message=f"Invalid date format: '{transaction_date}'",
                    field="transaction_date"
                ))
                return issues
        elif isinstance(transaction_date, datetime):
            parsed_date = transaction_date
        else:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="UNKNOWN_DATE_TYPE",
                message=f"Unknown date type: {type(transaction_date)}",
                field="transaction_date"
            ))
            return issues

        # Check if date is reasonable
        today = datetime.now()
        days_diff = (today - parsed_date).days

        if days_diff < 0:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="FUTURE_DATE",
                message=f"Transaction date is in the future: {parsed_date.date()}",
                field="transaction_date"
            ))
        elif days_diff > 365:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="OLD_DATE",
                message=f"Transaction date is over a year old: {parsed_date.date()}",
                field="transaction_date"
            ))

        return issues

    def _validate_consistency(self, ocr_text: str, parsed_data: dict[str, Any]) -> list[ValidationIssue]:
        """Validate consistency between OCR text and parsed data."""
        issues = []

        # Check if total amount appears in OCR text
        total_amount = parsed_data.get('total_amount')
        if total_amount:
            total_str = str(total_amount).replace('.', '[,.]')
            if not re.search(total_str, ocr_text):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    code="TOTAL_NOT_IN_TEXT",
                    message=f"Total amount {total_amount} not found in OCR text",
                    suggested_fix="Verify parsing accuracy"
                ))

        # Check if store name appears in OCR text
        store_name = parsed_data.get('store_name')
        if store_name and len(store_name) > 3:
            if store_name.lower() not in ocr_text.lower():
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.INFO,
                    code="STORE_NOT_IN_TEXT",
                    message=f"Store name '{store_name}' not clearly found in OCR text",
                    suggested_fix="Verify store name detection"
                ))

        return issues

    def _calculate_products_sum(self, products: list[dict]) -> Decimal | None:
        """Calculate sum of product total prices."""
        try:
            total = Decimal('0')
            for product in products:
                total_price = product.get('total_price')
                if total_price is not None:
                    total += Decimal(str(total_price))
            return total
        except (InvalidOperation, ValueError):
            return None

    def _calculate_confidence_score(self, issues: list[ValidationIssue],
                                  ocr_text: str, parsed_data: dict[str, Any]) -> float:
        """Calculate overall confidence score based on validation results."""
        base_score = 1.0

        # Deduct points for issues
        for issue in issues:
            if issue.severity == ValidationSeverity.CRITICAL:
                base_score -= 0.4
            elif issue.severity == ValidationSeverity.ERROR:
                base_score -= 0.2
            elif issue.severity == ValidationSeverity.WARNING:
                base_score -= 0.1
            elif issue.severity == ValidationSeverity.INFO:
                base_score -= 0.05

        # Bonus for good indicators
        if parsed_data.get('store_name'):
            base_score += 0.1

        if parsed_data.get('total_amount'):
            base_score += 0.1

        if parsed_data.get('products') and len(parsed_data['products']) > 0:
            base_score += 0.1

        if len(ocr_text) > 100:  # Substantial OCR text
            base_score += 0.05

        return max(0.0, min(1.0, base_score))


def get_ocr_validator() -> OCRValidator:
    """Factory function to get OCR validator instance."""
    return OCRValidator()
