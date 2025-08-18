"""
Product matching service for fuzzy matching receipt items to product catalog.
Implements normalization, similarity scoring, and automatic product creation.
"""

import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from django.db.models import Q

from inventory.models import Category, Product

from .receipt_parser import ParsedProduct

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Result of product matching operation."""

    product: Product | None = None
    confidence: float = 0.0
    match_type: str = "none"  # exact, fuzzy, alias, created
    normalized_name: str = ""
    similarity_score: float = 0.0
    matched_alias: str = ""
    category_guess: Category | None = None


class ProductMatcher:
    """Service for matching receipt products to catalog products."""

    def __init__(self):
        """Initialize matcher with normalization patterns."""

        # Weight/volume patterns to remove from product names
        self.weight_patterns = [
            r"\b\d+\s*(?:kg|g|gram|grams|kilogram|kilograms)\b",
            r"\b\d+\s*(?:l|litr|litry|litrów|ml|millilitr)\b",
            r"\b\d+(?:[.,]\d+)?\s*(?:kg|g|l|ml)\b",
            r"\b\d+\s*x\s*\d+\s*(?:g|ml|l|kg)\b",
        ]

        # Brand patterns that might prefix product names
        self.brand_patterns = [
            r"^(?:tesco|carrefour|biedronka|auchan|kaufland|lidl)\s+",
            r"^(?:organic|bio|eco)\s+",
        ]

        # Common category keywords for automatic categorization
        self.category_keywords = {
            "dairy": [
                "mleko",
                "milk",
                "jogurt",
                "yogurt",
                "ser",
                "cheese",
                "masło",
                "butter",
                "śmietana",
                "cream",
            ],
            "meat": [
                "mięso",
                "meat",
                "kiełbasa",
                "sausage",
                "wędlina",
                "szynka",
                "ham",
                "kurczak",
                "chicken",
            ],
            "vegetables": [
                "warzywa",
                "vegetables",
                "marchew",
                "carrot",
                "ziemniak",
                "potato",
                "cebula",
                "onion",
            ],
            "fruits": [
                "owoce",
                "fruits",
                "jabłko",
                "apple",
                "banan",
                "banana",
                "pomarańcza",
                "orange",
            ],
            "bread": ["chleb", "bread", "bułka", "roll", "bagietka", "baguette"],
            "beverages": [
                "napoje",
                "beverages",
                "woda",
                "water",
                "sok",
                "juice",
                "cola",
                "piwo",
                "beer",
            ],
            "cleaning": [
                "czyszczenie",
                "cleaning",
                "detergent",
                "mydło",
                "soap",
                "proszek",
            ],
            "household": ["dom", "household", "papier", "paper", "ręcznik", "towel"],
        }

        # Minimum confidence threshold for matches
        self.min_confidence = 0.6
        self.exact_match_threshold = 0.95
        self.fuzzy_match_threshold = 0.7

    def match_product(self, parsed_product: ParsedProduct) -> MatchResult:
        """
        Match a parsed product to existing catalog product.

        Args:
            parsed_product: Parsed product from receipt

        Returns:
            MatchResult with matched product and confidence
        """
        logger.debug(f"Matching product: {parsed_product.name}")

        # Normalize the product name
        normalized_name = self.normalize_product_name(parsed_product.name)

        # Try exact match first
        exact_match = self._find_exact_match(normalized_name)
        if exact_match:
            logger.info(f"Exact match found: {exact_match.name}")
            return MatchResult(
                product=exact_match,
                confidence=1.0,
                match_type="exact",
                normalized_name=normalized_name,
                similarity_score=1.0,
            )

        # Try alias match
        alias_match, matched_alias = self._find_alias_match(normalized_name)
        if alias_match:
            logger.info(
                f"Alias match found: {alias_match.name} (alias: {matched_alias})"
            )
            return MatchResult(
                product=alias_match,
                confidence=0.9,
                match_type="alias",
                normalized_name=normalized_name,
                similarity_score=0.9,
                matched_alias=matched_alias,
            )

        # Try fuzzy match
        fuzzy_match, similarity = self._find_fuzzy_match(normalized_name)
        if fuzzy_match and similarity >= self.fuzzy_match_threshold:
            logger.info(
                f"Fuzzy match found: {fuzzy_match.name} (similarity: {similarity:.2f})"
            )
            return MatchResult(
                product=fuzzy_match,
                confidence=similarity,
                match_type="fuzzy",
                normalized_name=normalized_name,
                similarity_score=similarity,
            )

        # No match found - create new ghost product
        logger.info(f"No match found for '{normalized_name}', creating ghost product")
        ghost_product = self._create_ghost_product(parsed_product, normalized_name)

        return MatchResult(
            product=ghost_product,
            confidence=0.5,
            match_type="created",
            normalized_name=normalized_name,
            similarity_score=0.0,
            category_guess=ghost_product.category,
        )

    def normalize_product_name(self, name: str) -> str:
        """
        Normalize product name by removing weights, volumes, and common variations.

        Args:
            name: Original product name

        Returns:
            Normalized product name
        """
        normalized = name.lower().strip()

        # Remove weight/volume information
        for pattern in self.weight_patterns:
            normalized = re.sub(pattern, "", normalized, flags=re.IGNORECASE)

        # Remove brand prefixes
        for pattern in self.brand_patterns:
            normalized = re.sub(pattern, "", normalized, flags=re.IGNORECASE)

        # Remove common suffixes and prefixes
        normalized = re.sub(r"\b(?:fresh|świeży|organic|bio|eco)\b", "", normalized)
        normalized = re.sub(r"\b(?:pack|opak|szt|pcs)\b", "", normalized)

        # Clean up whitespace but preserve some punctuation like % and ,
        normalized = re.sub(r"[^\w\s%,.]", " ", normalized)
        # Replace dots with commas for Polish decimal format
        normalized = re.sub(r"\.", ",", normalized)
        normalized = " ".join(normalized.split())

        return normalized.strip()

    def _find_exact_match(self, normalized_name: str) -> Product | None:
        """Find exact match by normalized name."""
        try:
            # Try exact match on normalized name
            products = Product.objects.filter(
                name__iexact=normalized_name, is_active=True
            )

            if products.exists():
                return products.first()

            # Try with original case variations
            products = Product.objects.filter(
                Q(name__iexact=normalized_name.title())
                | Q(name__iexact=normalized_name.upper())
                | Q(name__iexact=normalized_name.lower()),
                is_active=True,
            )

            return products.first()

        except Exception as e:
            logger.error(f"Error in exact match search: {e}")
            return None

    def _find_alias_match(self, normalized_name: str) -> tuple[Product | None, str]:
        """Find match through product aliases."""
        try:
            products = Product.objects.filter(
                aliases__icontains=normalized_name, is_active=True
            )

            for product in products:
                for alias in product.aliases:
                    if (
                        self._calculate_similarity(normalized_name, alias.lower())
                        >= self.exact_match_threshold
                    ):
                        return product, alias

            return None, ""

        except Exception as e:
            logger.error(f"Error in alias match search: {e}")
            return None, ""

    def _find_fuzzy_match(self, normalized_name: str) -> tuple[Product | None, float]:
        """Find fuzzy match using string similarity."""
        try:
            # Get all active products
            products = Product.objects.filter(is_active=True).only("name", "aliases")

            best_match = None
            best_similarity = 0.0

            for product in products:
                # Check similarity with product name
                name_similarity = self._calculate_similarity(
                    normalized_name, product.name.lower()
                )
                if name_similarity > best_similarity:
                    best_similarity = name_similarity
                    best_match = product

                # Check similarity with aliases
                for alias in product.aliases:
                    alias_similarity = self._calculate_similarity(
                        normalized_name, alias.lower()
                    )
                    if alias_similarity > best_similarity:
                        best_similarity = alias_similarity
                        best_match = product

            if best_similarity >= self.fuzzy_match_threshold:
                return best_match, best_similarity

            return None, 0.0

        except Exception as e:
            logger.error(f"Error in fuzzy match search: {e}")
            return None, 0.0

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings."""
        # Use SequenceMatcher for basic similarity
        basic_similarity = SequenceMatcher(None, str1, str2).ratio()

        # Bonus for word overlap
        words1 = set(str1.split())
        words2 = set(str2.split())
        if words1 and words2:
            word_overlap = len(words1.intersection(words2)) / len(words1.union(words2))
            # Weighted average
            return 0.7 * basic_similarity + 0.3 * word_overlap

        return basic_similarity

    def _create_ghost_product(
        self, parsed_product: ParsedProduct, normalized_name: str
    ) -> Product:
        """Create a new 'ghost' product for unmatched items."""
        try:
            # Guess category based on keywords
            category = self._guess_category(normalized_name)

            # Create ghost product
            ghost_product = Product.objects.create(
                name=normalized_name.title(),
                category=category,
                is_active=False,  # Mark as ghost product
                aliases=[parsed_product.name],  # Store original name as alias
            )

            logger.info(
                f"Created ghost product: {ghost_product.name} (category: {category})"
            )
            return ghost_product

        except Exception as e:
            logger.error(f"Error creating ghost product: {e}")
            # Return a minimal ghost product without category
            return Product.objects.create(
                name=normalized_name.title(),
                is_active=False,
                aliases=[parsed_product.name],
            )

    def _guess_category(self, normalized_name: str) -> Category | None:
        """Guess product category based on keywords."""
        try:
            name_words = set(normalized_name.lower().split())

            best_category = None
            best_score = 0

            for category_name, keywords in self.category_keywords.items():
                # Count keyword matches
                matches = sum(
                    1 for keyword in keywords if keyword in normalized_name.lower()
                )

                if matches > best_score:
                    best_score = matches
                    # Try to find or create category
                    category, created = Category.objects.get_or_create(
                        name=category_name.title(),
                        defaults={"meta": {"auto_created": True}},
                    )
                    if created:
                        logger.info(f"Auto-created category: {category.name}")
                    best_category = category

            return best_category

        except Exception as e:
            logger.error(f"Error guessing category: {e}")
            return None

    def batch_match_products(
        self, parsed_products: list[ParsedProduct]
    ) -> list[MatchResult]:
        """
        Match multiple products in batch for efficiency.

        Args:
            parsed_products: List of parsed products from receipt

        Returns:
            List of match results
        """
        logger.info(f"Batch matching {len(parsed_products)} products")

        results = []
        for parsed_product in parsed_products:
            try:
                result = self.match_product(parsed_product)
                results.append(result)
            except Exception as e:
                logger.error(f"Error matching product '{parsed_product.name}': {e}")
                # Create fallback result
                results.append(
                    MatchResult(
                        normalized_name=parsed_product.name,
                        confidence=0.0,
                        match_type="error",
                    )
                )

        logger.info(f"Batch matching completed: {len(results)} results")
        return results

    def update_product_aliases(self, product: Product, new_name: str) -> bool:
        """
        Add new alias to product for future matching.

        Args:
            product: Product to update
            new_name: New name to add as alias

        Returns:
            True if alias was added, False if it already existed
        """
        try:
            normalized_new_name = self.normalize_product_name(new_name)

            # Don't add if it's too similar to existing name
            if (
                self._calculate_similarity(normalized_new_name, product.name.lower())
                > 0.9
            ):
                return False

            # Don't add if alias already exists
            for alias in product.aliases:
                if self._calculate_similarity(normalized_new_name, alias.lower()) > 0.9:
                    return False

            # Add new alias
            product.add_alias(normalized_new_name)
            logger.info(
                f"Added alias '{normalized_new_name}' to product '{product.name}'"
            )
            return True

        except Exception as e:
            logger.error(f"Error updating product aliases: {e}")
            return False

    def get_matching_statistics(self) -> dict[str, int]:
        """Get statistics about product matching."""
        try:
            total_products = Product.objects.count()
            active_products = Product.objects.filter(is_active=True).count()
            ghost_products = Product.objects.filter(is_active=False).count()

            # Count products with aliases
            products_with_aliases = Product.objects.exclude(aliases=[]).count()

            return {
                "total_products": total_products,
                "active_products": active_products,
                "ghost_products": ghost_products,
                "products_with_aliases": products_with_aliases,
                "categories": Category.objects.count(),
            }

        except Exception as e:
            logger.error(f"Error getting matching statistics: {e}")
            return {}

    def search_products(self, query: str, limit: int = 10) -> list[Product]:
        """
        Search for products by name or alias.

        Args:
            query: The search query string.
            limit: Maximum number of results to return.

        Returns:
            A list of matching Product objects.
        """
        normalized_query = self.normalize_product_name(query)
        logger.debug(f"Searching products for normalized query: '{normalized_query}'")

        # Prioritize exact matches
        exact_matches = Product.objects.filter(
            Q(name__iexact=normalized_query) | Q(aliases__icontains=normalized_query),
            is_active=True,
        ).distinct()

        # Then partial matches
        partial_matches = Product.objects.filter(
            Q(name__icontains=normalized_query) | Q(aliases__icontains=normalized_query),
            is_active=True,
        ).exclude(id__in=exact_matches.values_list("id", flat=True)).distinct()

        # Combine and limit results
        results = list(exact_matches) + list(partial_matches)
        
        logger.debug(f"Found {len(results)} products for query '{query}'")
        return results[:limit]


def get_product_matcher() -> ProductMatcher:
    """Get default product matcher instance."""
    return ProductMatcher()
