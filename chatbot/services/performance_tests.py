"""
Performance testing and benchmarking for receipt processing system.
Implements load testing from FAZA 5 of the plan.
"""

import logging
import statistics
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from django.db import connection
from django.utils import timezone

from inventory.models import Category, Product, Receipt

from .optimized_queries import get_dashboard_data, get_optimized_receipt_service
from .receipt_cache import get_cache_manager

logger = logging.getLogger(__name__)


@dataclass
class PerformanceResult:
    """Result of a performance test."""

    test_name: str
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    operations: int
    queries_count: int
    success_rate: float
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'test_name': self.test_name,
            'total_time': self.total_time,
            'avg_time': self.avg_time,
            'min_time': self.min_time,
            'max_time': self.max_time,
            'operations': self.operations,
            'queries_count': self.queries_count,
            'success_rate': self.success_rate,
            'errors': self.errors
        }


class PerformanceBenchmark:
    """
    Performance benchmarking suite for receipt processing system.
    """

    def __init__(self):
        self.results: list[PerformanceResult] = []

    def benchmark_function(self, func: Callable, name: str, iterations: int = 100) -> PerformanceResult:
        """
        Benchmark a function with multiple iterations.
        
        Args:
            func: Function to benchmark
            name: Test name
            iterations: Number of iterations
            
        Returns:
            PerformanceResult with timing statistics
        """
        times = []
        errors = []
        query_counts = []

        logger.info(f"Starting benchmark: {name} ({iterations} iterations)")

        for i in range(iterations):
            # Reset query count
            initial_queries = len(connection.queries)

            try:
                start_time = time.time()
                func()
                end_time = time.time()

                execution_time = end_time - start_time
                times.append(execution_time)

                query_count = len(connection.queries) - initial_queries
                query_counts.append(query_count)

            except Exception as e:
                errors.append(f"Iteration {i}: {str(e)}")
                logger.error(f"Error in iteration {i}: {e}")

        if not times:
            return PerformanceResult(
                test_name=name,
                total_time=0,
                avg_time=0,
                min_time=0,
                max_time=0,
                operations=0,
                queries_count=0,
                success_rate=0,
                errors=errors
            )

        total_time = sum(times)
        avg_time = statistics.mean(times)
        min_time = min(times)
        max_time = max(times)
        success_rate = (len(times) / iterations) * 100
        avg_queries = statistics.mean(query_counts) if query_counts else 0

        result = PerformanceResult(
            test_name=name,
            total_time=total_time,
            avg_time=avg_time,
            min_time=min_time,
            max_time=max_time,
            operations=len(times),
            queries_count=avg_queries,
            success_rate=success_rate,
            errors=errors
        )

        self.results.append(result)

        logger.info(
            f"Benchmark completed: {name} - "
            f"Avg: {avg_time:.3f}s, "
            f"Min: {min_time:.3f}s, "
            f"Max: {max_time:.3f}s, "
            f"Queries: {avg_queries:.1f}"
        )

        return result

    def benchmark_concurrent_load(self, func: Callable, name: str,
                                 concurrent_users: int = 10,
                                 operations_per_user: int = 10) -> PerformanceResult:
        """
        Benchmark function under concurrent load.
        
        Args:
            func: Function to benchmark
            name: Test name
            concurrent_users: Number of concurrent threads
            operations_per_user: Operations per thread
            
        Returns:
            PerformanceResult with concurrent load statistics
        """
        times = []
        errors = []

        logger.info(
            f"Starting concurrent load test: {name} "
            f"({concurrent_users} users, {operations_per_user} ops each)"
        )

        def user_operations():
            """Operations for a single user thread."""
            user_times = []
            user_errors = []

            for _ in range(operations_per_user):
                try:
                    start_time = time.time()
                    func()
                    end_time = time.time()
                    user_times.append(end_time - start_time)
                except Exception as e:
                    user_errors.append(str(e))

            return user_times, user_errors

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = [executor.submit(user_operations) for _ in range(concurrent_users)]

            for future in as_completed(futures):
                try:
                    user_times, user_errors = future.result()
                    times.extend(user_times)
                    errors.extend(user_errors)
                except Exception as e:
                    errors.append(f"Thread error: {str(e)}")

        total_time = time.time() - start_time

        if times:
            avg_time = statistics.mean(times)
            min_time = min(times)
            max_time = max(times)
        else:
            avg_time = min_time = max_time = 0

        total_operations = concurrent_users * operations_per_user
        success_rate = (len(times) / total_operations) * 100 if total_operations > 0 else 0

        result = PerformanceResult(
            test_name=f"{name}_concurrent",
            total_time=total_time,
            avg_time=avg_time,
            min_time=min_time,
            max_time=max_time,
            operations=len(times),
            queries_count=0,  # Difficult to measure accurately in concurrent scenario
            success_rate=success_rate,
            errors=errors
        )

        self.results.append(result)

        logger.info(
            f"Concurrent load test completed: {name} - "
            f"Success rate: {success_rate:.1f}%, "
            f"Avg response: {avg_time:.3f}s, "
            f"Total time: {total_time:.3f}s"
        )

        return result

    def run_receipt_processing_benchmarks(self) -> list[PerformanceResult]:
        """Run comprehensive benchmarks for receipt processing."""
        logger.info("Starting receipt processing benchmarks")

        # Setup test data
        self._setup_test_data()

        # Benchmark optimized queries
        receipt_service = get_optimized_receipt_service()

        self.benchmark_function(
            lambda: list(receipt_service.get_receipts_with_items(50)),
            "get_receipts_with_items",
            iterations=50
        )

        self.benchmark_function(
            lambda: list(receipt_service.get_inventory_summary()),
            "get_inventory_summary",
            iterations=50
        )

        self.benchmark_function(
            lambda: receipt_service.get_processing_analytics(days=7),
            "get_processing_analytics_7d",
            iterations=30
        )

        self.benchmark_function(
            lambda: receipt_service.get_processing_analytics(days=30),
            "get_processing_analytics_30d",
            iterations=20
        )

        # Benchmark dashboard data
        self.benchmark_function(
            get_dashboard_data,
            "get_dashboard_data",
            iterations=20
        )

        # Benchmark caching system
        cache_manager = get_cache_manager()

        self.benchmark_function(
            lambda: cache_manager.cache_ocr_result("test_hash", {"text": "test data"}),
            "cache_ocr_result",
            iterations=100
        )

        self.benchmark_function(
            lambda: cache_manager.get_cached_ocr_result("test_hash"),
            "get_cached_ocr_result",
            iterations=100
        )

        # Concurrent load tests
        self.benchmark_concurrent_load(
            lambda: list(receipt_service.get_receipts_with_items(10)),
            "get_receipts_concurrent",
            concurrent_users=5,
            operations_per_user=10
        )

        self.benchmark_concurrent_load(
            get_dashboard_data,
            "dashboard_data_concurrent",
            concurrent_users=3,
            operations_per_user=5
        )

        logger.info(f"Completed {len(self.results)} benchmarks")
        return self.results

    def _setup_test_data(self):
        """Setup test data for benchmarks."""
        try:
            # Create test categories if they don't exist
            category, _ = Category.objects.get_or_create(
                name="Test Category",
                defaults={'meta': {'expiry_days': 30}}
            )

            # Create test products
            for i in range(10):
                Product.objects.get_or_create(
                    name=f"Test Product {i}",
                    defaults={
                        'category': category,
                        'unit': 'szt.',
                        'minimum_stock': 5
                    }
                )

            # Create test receipts
            for i in range(20):
                Receipt.objects.get_or_create(
                    store_name=f"Test Store {i % 3}",
                    defaults={
                        'status': 'completed' if i % 2 == 0 else 'uploaded',
                        'total': 100.00 + i,
                        'currency': 'PLN'
                    }
                )

            logger.info("Test data setup completed")

        except Exception as e:
            logger.error(f"Error setting up test data: {e}")

    def generate_report(self) -> dict[str, Any]:
        """Generate comprehensive performance report."""
        if not self.results:
            return {'error': 'No benchmark results available'}

        # Overall statistics
        all_times = [r.avg_time for r in self.results if r.avg_time > 0]
        all_queries = [r.queries_count for r in self.results if r.queries_count > 0]

        report = {
            'summary': {
                'total_tests': len(self.results),
                'avg_response_time': statistics.mean(all_times) if all_times else 0,
                'median_response_time': statistics.median(all_times) if all_times else 0,
                'avg_queries_per_operation': statistics.mean(all_queries) if all_queries else 0,
                'fastest_operation': min(all_times) if all_times else 0,
                'slowest_operation': max(all_times) if all_times else 0,
            },
            'detailed_results': [r.to_dict() for r in self.results],
            'performance_issues': self._identify_performance_issues(),
            'recommendations': self._generate_recommendations(),
            'generated_at': timezone.now().isoformat()
        }

        return report

    def _identify_performance_issues(self) -> list[dict[str, Any]]:
        """Identify potential performance issues."""
        issues = []

        for result in self.results:
            # Check for slow operations (> 1 second)
            if result.avg_time > 1.0:
                issues.append({
                    'type': 'slow_operation',
                    'test': result.test_name,
                    'avg_time': result.avg_time,
                    'severity': 'high' if result.avg_time > 2.0 else 'medium'
                })

            # Check for high query count (> 10 queries)
            if result.queries_count > 10:
                issues.append({
                    'type': 'high_query_count',
                    'test': result.test_name,
                    'queries': result.queries_count,
                    'severity': 'high' if result.queries_count > 20 else 'medium'
                })

            # Check for low success rate (< 95%)
            if result.success_rate < 95:
                issues.append({
                    'type': 'low_success_rate',
                    'test': result.test_name,
                    'success_rate': result.success_rate,
                    'severity': 'critical' if result.success_rate < 80 else 'high'
                })

        return issues

    def _generate_recommendations(self) -> list[str]:
        """Generate performance improvement recommendations."""
        recommendations = []

        issues = self._identify_performance_issues()

        if any(issue['type'] == 'slow_operation' for issue in issues):
            recommendations.append(
                "Consider optimizing slow operations with better indexing or query optimization"
            )

        if any(issue['type'] == 'high_query_count' for issue in issues):
            recommendations.append(
                "Reduce database queries using select_related, prefetch_related, or caching"
            )

        if any(issue['type'] == 'low_success_rate' for issue in issues):
            recommendations.append(
                "Investigate and fix errors causing low success rates"
            )

        # General recommendations
        recommendations.extend([
            "Implement Redis caching for frequently accessed data",
            "Consider database connection pooling for high concurrency",
            "Add database indexes for commonly queried fields",
            "Monitor query performance in production with logging"
        ])

        return recommendations


def run_performance_tests() -> dict[str, Any]:
    """Run complete performance test suite."""
    benchmark = PerformanceBenchmark()
    benchmark.run_receipt_processing_benchmarks()
    return benchmark.generate_report()


def quick_performance_check() -> dict[str, Any]:
    """Run quick performance check for monitoring."""
    benchmark = PerformanceBenchmark()

    # Quick tests
    receipt_service = get_optimized_receipt_service()

    benchmark.benchmark_function(
        lambda: list(receipt_service.get_receipts_with_items(10)),
        "quick_receipts_check",
        iterations=5
    )

    benchmark.benchmark_function(
        get_dashboard_data,
        "quick_dashboard_check",
        iterations=3
    )

    return benchmark.generate_report()


# Performance monitoring for production
class PerformanceMonitor:
    """Monitor performance in production environment."""

    def __init__(self):
        self.slow_query_threshold = 1.0  # seconds
        self.slow_queries = []

    def monitor_query(self, query_func: Callable, operation_name: str) -> Any:
        """Monitor a database operation."""
        start_time = time.time()
        initial_queries = len(connection.queries)

        try:
            result = query_func()
            end_time = time.time()

            duration = end_time - start_time
            query_count = len(connection.queries) - initial_queries

            if duration > self.slow_query_threshold:
                self.slow_queries.append({
                    'operation': operation_name,
                    'duration': duration,
                    'query_count': query_count,
                    'timestamp': timezone.now().isoformat()
                })

                logger.warning(
                    f"Slow query detected: {operation_name} took {duration:.3f}s "
                    f"with {query_count} queries"
                )

            return result

        except Exception as e:
            logger.error(f"Error in monitored query {operation_name}: {e}")
            raise

    def get_slow_queries(self) -> list[dict[str, Any]]:
        """Get list of slow queries."""
        return self.slow_queries.copy()

    def reset_monitoring(self):
        """Reset monitoring data."""
        self.slow_queries.clear()


# Global performance monitor
_performance_monitor = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance."""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor
