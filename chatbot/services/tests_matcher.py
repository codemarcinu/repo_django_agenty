"""
Tests for product matcher service.
"""

from decimal import Decimal
from django.test import TestCase
from django.utils import timezone

from inventory.models import Product, Category
from .product_matcher import ProductMatcher, MatchResult, get_product_matcher
from .receipt_parser import ParsedProduct


class ProductMatcherTest(TestCase):
    """Test ProductMatcher functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.matcher = ProductMatcher()
        
        # Create test categories
        self.dairy_category = Category.objects.create(
            name='Dairy',
            meta={'expiry_days': 7}
        )
        
        self.meat_category = Category.objects.create(
            name='Meat',
            meta={'expiry_days': 3}
        )
        
        # Create test products
        self.milk_product = Product.objects.create(
            name='Mleko 3,2%',
            brand='Łaciate',
            category=self.dairy_category,
            aliases=['milk', 'mleko laciate']
        )
        
        self.bread_product = Product.objects.create(
            name='Chleb graham',
            brand='Kępno',
            aliases=['bread', 'chleb pełnoziarnisty']
        )
        
        self.butter_product = Product.objects.create(
            name='Masło extra',
            brand='Śmietankowe',
            category=self.dairy_category,
            aliases=['butter', 'masło śmietankowe']
        )
    
    def test_matcher_initialization(self):
        """Test matcher initialization."""
        self.assertIsInstance(self.matcher.weight_patterns, list)
        self.assertIsInstance(self.matcher.brand_patterns, list)
        self.assertIsInstance(self.matcher.category_keywords, dict)
        self.assertEqual(self.matcher.min_confidence, 0.6)
        self.assertEqual(self.matcher.exact_match_threshold, 0.95)
        self.assertEqual(self.matcher.fuzzy_match_threshold, 0.7)
    
    def test_normalize_product_name(self):
        """Test product name normalization."""
        # Test weight removal
        normalized = self.matcher.normalize_product_name("Mleko 3,2% 1L")
        self.assertEqual(normalized, "mleko 3,2%")
        
        # Test weight with different formats
        normalized = self.matcher.normalize_product_name("Chleb graham 500g")
        self.assertEqual(normalized, "chleb graham")
        
        # Test brand removal
        normalized = self.matcher.normalize_product_name("Tesco Milk Organic")
        self.assertEqual(normalized, "milk")
        
        # Test complex normalization
        normalized = self.matcher.normalize_product_name("Bio Masło extra 250g pack")
        self.assertEqual(normalized, "masło extra")
    
    def test_exact_match(self):
        """Test exact product matching."""
        parsed_product = ParsedProduct(
            name="Mleko 3,2%",
            total_price=Decimal('2.99')
        )
        
        result = self.matcher.match_product(parsed_product)
        
        # Should find exact match or fuzzy match with high confidence
        self.assertIn(result.match_type, ['exact', 'fuzzy'])
        self.assertEqual(result.product, self.milk_product)
        self.assertGreater(result.confidence, 0.7)
        if result.match_type == 'exact':
            self.assertEqual(result.confidence, 1.0)
            self.assertEqual(result.similarity_score, 1.0)
    
    def test_alias_match(self):
        """Test matching through product aliases."""
        parsed_product = ParsedProduct(
            name="milk",
            total_price=Decimal('2.99')
        )
        
        result = self.matcher.match_product(parsed_product)
        
        self.assertEqual(result.match_type, 'alias')
        self.assertEqual(result.product, self.milk_product)
        self.assertEqual(result.confidence, 0.9)
        self.assertEqual(result.matched_alias, 'milk')
    
    def test_fuzzy_match(self):
        """Test fuzzy matching."""
        parsed_product = ParsedProduct(
            name="Mleko Laciate 3.2%",
            total_price=Decimal('2.99')
        )
        
        result = self.matcher.match_product(parsed_product)
        
        self.assertIn(result.match_type, ['fuzzy', 'exact'])  # Could be either depending on similarity
        self.assertEqual(result.product, self.milk_product)
        self.assertGreater(result.confidence, 0.7)
    
    def test_ghost_product_creation(self):
        """Test creation of ghost product for unmatched items."""
        parsed_product = ParsedProduct(
            name="Unknown Product XYZ",
            total_price=Decimal('5.99')
        )
        
        result = self.matcher.match_product(parsed_product)
        
        self.assertEqual(result.match_type, 'created')
        self.assertIsNotNone(result.product)
        self.assertFalse(result.product.is_active)  # Ghost product
        self.assertEqual(result.confidence, 0.5)
        self.assertEqual(result.product.name, "Unknown Product Xyz")
        self.assertIn("Unknown Product XYZ", result.product.aliases)
    
    def test_category_guessing(self):
        """Test automatic category guessing."""
        # Test dairy category
        dairy_name = "yogurt natural"
        category = self.matcher._guess_category(dairy_name)
        self.assertIsNotNone(category)
        self.assertEqual(category.name, "Dairy")
        
        # Test meat category
        meat_name = "chicken breast"
        category = self.matcher._guess_category(meat_name)
        self.assertIsNotNone(category)
        self.assertEqual(category.name, "Meat")
        
        # Test unknown category
        unknown_name = "mystery item xyz"
        category = self.matcher._guess_category(unknown_name)
        self.assertIsNone(category)
    
    def test_batch_matching(self):
        """Test batch product matching."""
        parsed_products = [
            ParsedProduct(name="Mleko 3,2%", total_price=Decimal('2.99')),
            ParsedProduct(name="Chleb graham", total_price=Decimal('3.50')),
            ParsedProduct(name="Unknown Item", total_price=Decimal('1.99'))
        ]
        
        results = self.matcher.batch_match_products(parsed_products)
        
        self.assertEqual(len(results), 3)
        
        # First should be exact or fuzzy match
        self.assertIn(results[0].match_type, ['exact', 'fuzzy'])
        self.assertEqual(results[0].product, self.milk_product)
        
        # Second should be exact or fuzzy match
        self.assertIn(results[1].match_type, ['exact', 'fuzzy'])
        self.assertEqual(results[1].product, self.bread_product)
        
        # Third should create ghost product
        self.assertEqual(results[2].match_type, 'created')
        self.assertFalse(results[2].product.is_active)
    
    def test_similarity_calculation(self):
        """Test string similarity calculation."""
        # Identical strings
        similarity = self.matcher._calculate_similarity("test", "test")
        self.assertEqual(similarity, 1.0)
        
        # Similar strings
        similarity = self.matcher._calculate_similarity("mleko", "mleko 3%")
        self.assertGreater(similarity, 0.5)
        
        # Different strings
        similarity = self.matcher._calculate_similarity("mleko", "chleb")
        self.assertLess(similarity, 0.3)
        
        # Word overlap bonus
        similarity = self.matcher._calculate_similarity("mleko fresh", "fresh mleko")
        self.assertGreater(similarity, 0.6)
    
    def test_update_product_aliases(self):
        """Test updating product aliases."""
        original_aliases_count = len(self.milk_product.aliases)
        
        # Add new alias
        result = self.matcher.update_product_aliases(self.milk_product, "new milk name")
        self.assertTrue(result)
        
        # Refresh from database
        self.milk_product.refresh_from_db()
        self.assertEqual(len(self.milk_product.aliases), original_aliases_count + 1)
        
        # Try to add similar alias (should not add)
        result = self.matcher.update_product_aliases(self.milk_product, "Mleko 3,2%")
        self.assertFalse(result)
        
        # Refresh and check count didn't change
        self.milk_product.refresh_from_db()
        self.assertEqual(len(self.milk_product.aliases), original_aliases_count + 1)
    
    def test_get_matching_statistics(self):
        """Test getting matching statistics."""
        stats = self.matcher.get_matching_statistics()
        
        self.assertIn('total_products', stats)
        self.assertIn('active_products', stats)
        self.assertIn('ghost_products', stats)
        self.assertIn('products_with_aliases', stats)
        self.assertIn('categories', stats)
        
        self.assertEqual(stats['total_products'], 3)  # Our test products
        self.assertEqual(stats['active_products'], 3)  # All are active
        self.assertEqual(stats['ghost_products'], 0)   # None are ghost yet
        self.assertGreater(stats['products_with_aliases'], 0)  # Some have aliases
        self.assertGreater(stats['categories'], 0)  # We created categories


class MatchResultTest(TestCase):
    """Test MatchResult dataclass."""
    
    def test_match_result_creation(self):
        """Test creating MatchResult instance."""
        product = Product.objects.create(name="Test Product")
        
        result = MatchResult(
            product=product,
            confidence=0.85,
            match_type='fuzzy',
            normalized_name='test product',
            similarity_score=0.82,
            matched_alias='test alias'
        )
        
        self.assertEqual(result.product, product)
        self.assertEqual(result.confidence, 0.85)
        self.assertEqual(result.match_type, 'fuzzy')
        self.assertEqual(result.normalized_name, 'test product')
        self.assertEqual(result.similarity_score, 0.82)
        self.assertEqual(result.matched_alias, 'test alias')
    
    def test_match_result_defaults(self):
        """Test MatchResult default values."""
        result = MatchResult()
        
        self.assertIsNone(result.product)
        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(result.match_type, 'none')
        self.assertEqual(result.normalized_name, '')
        self.assertEqual(result.similarity_score, 0.0)
        self.assertEqual(result.matched_alias, '')
        self.assertIsNone(result.category_guess)


class ProductMatcherFactoryTest(TestCase):
    """Test product matcher factory function."""
    
    def test_get_product_matcher(self):
        """Test getting default matcher instance."""
        matcher = get_product_matcher()
        
        self.assertIsInstance(matcher, ProductMatcher)
        self.assertIsNotNone(matcher.weight_patterns)
        self.assertIsNotNone(matcher.category_keywords)


class ProductMatcherIntegrationTest(TestCase):
    """Integration tests for ProductMatcher with real data scenarios."""
    
    def setUp(self):
        """Set up test data with realistic products."""
        self.matcher = ProductMatcher()
        
        # Create categories
        self.dairy = Category.objects.create(name='Dairy')
        self.bread = Category.objects.create(name='Bread & Bakery')
        
        # Create realistic products
        self.products = [
            Product.objects.create(
                name='Mleko UHT 2%',
                brand='Łaciate',
                category=self.dairy,
                aliases=['mleko laciate', 'milk 2%', 'mleko 2%']
            ),
            Product.objects.create(
                name='Chleb żytni',
                brand='Putka',
                category=self.bread,
                aliases=['chleb razowy', 'żytni chleb', 'rye bread']
            ),
            Product.objects.create(
                name='Jogurt naturalny',
                brand='Danone',
                category=self.dairy,
                aliases=['yogurt natural', 'jogurt grecki']
            )
        ]
    
    def test_realistic_receipt_matching(self):
        """Test matching with realistic receipt data."""
        # Realistic receipt products with weights and variations
        receipt_products = [
            ParsedProduct(name="Mleko UHT Łaciate 2% 1L", total_price=Decimal('3.49')),
            ParsedProduct(name="Chleb żytni Putka 500g", total_price=Decimal('4.20')),
            ParsedProduct(name="Jogurt nat. Danone 4x125g", total_price=Decimal('5.99')),
            ParsedProduct(name="Banan kg", total_price=Decimal('6.80')),  # Should create ghost
            ParsedProduct(name="MLEKO 2%", total_price=Decimal('3.29')),  # Case variation
        ]
        
        results = self.matcher.batch_match_products(receipt_products)
        
        self.assertEqual(len(results), 5)
        
        # Check first product (should match milk)
        self.assertIn(results[0].match_type, ['exact', 'fuzzy'])
        self.assertEqual(results[0].product.name, 'Mleko UHT 2%')
        
        # Check second product (should match bread)
        self.assertIn(results[1].match_type, ['exact', 'fuzzy'])
        self.assertEqual(results[1].product.name, 'Chleb żytni')
        
        # Check third product (should match yogurt)
        self.assertIn(results[2].match_type, ['exact', 'fuzzy', 'created'])
        if results[2].match_type != 'created':
            self.assertEqual(results[2].product.name, 'Jogurt naturalny')
        
        # Check fourth product (should create ghost - banana)
        self.assertEqual(results[3].match_type, 'created')
        self.assertFalse(results[3].product.is_active)
        
        # Check fifth product (should match milk through normalization)
        self.assertIn(results[4].match_type, ['exact', 'fuzzy', 'alias'])
        self.assertEqual(results[4].product.name, 'Mleko UHT 2%')
    
    def test_edge_cases(self):
        """Test edge cases in product matching."""
        edge_cases = [
            ParsedProduct(name="", total_price=Decimal('1.00')),  # Empty name
            ParsedProduct(name="123456", total_price=Decimal('1.00')),  # Only numbers
            ParsedProduct(name="A", total_price=Decimal('1.00')),  # Very short
            ParsedProduct(name="X" * 500, total_price=Decimal('1.00')),  # Very long
        ]
        
        results = self.matcher.batch_match_products(edge_cases)
        
        self.assertEqual(len(results), 4)
        
        # All should either create ghost products or return valid results
        for result in results:
            self.assertIn(result.match_type, ['created', 'exact', 'fuzzy', 'alias', 'none'])
            if result.match_type == 'created':
                self.assertIsNotNone(result.product)
    
    def test_performance_with_many_products(self):
        """Test performance with larger product catalog."""
        # Create many products
        for i in range(100):
            Product.objects.create(
                name=f'Product {i}',
                aliases=[f'prod {i}', f'item {i}']
            )
        
        # Test matching with multiple products
        test_products = [
            ParsedProduct(name="Product 50", total_price=Decimal('1.00')),
            ParsedProduct(name="prod 25", total_price=Decimal('2.00')),
            ParsedProduct(name="Unknown Item", total_price=Decimal('3.00')),
        ]
        
        import time
        start_time = time.time()
        results = self.matcher.batch_match_products(test_products)
        end_time = time.time()
        
        # Should complete reasonably quickly (under 5 seconds for this test size)
        self.assertLess(end_time - start_time, 5.0)
        self.assertEqual(len(results), 3)
        
        # Check that matches were found
        self.assertEqual(results[0].match_type, 'exact')
        self.assertEqual(results[1].match_type, 'alias')
        self.assertEqual(results[2].match_type, 'created')