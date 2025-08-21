#!/usr/bin/env python3
"""
Model performance benchmark script for RTX 3060 optimization.
Tests tokens/second performance across different models.
"""

import asyncio
import json
import logging
import time
from typing import Any

import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLLAMA_URL = "http://127.0.0.1:11434"
TEST_PROMPT = "Opowiedz mi krótko o historii Polski w 3 zdaniach."

MODELS_TO_TEST = [
    "qwen2:7b",
    "mistral:7b",
    "jobautomation/OpenEuroLLM-Polish",
    "qwen2.5-vl:7b"
]

async def test_model_performance(model: str, test_runs: int = 3) -> dict[str, Any]:
    """Test model performance with multiple runs."""
    logger.info(f"🔄 Testing model: {model}")

    results = []

    for run in range(test_runs):
        try:
            start_time = time.time()

            payload = {
                "model": model,
                "messages": [{"role": "user", "content": TEST_PROMPT}],
                "stream": False,
                "options": {
                    "num_predict": 100,  # Limit tokens for consistent testing
                    "temperature": 0.7
                }
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
                response.raise_for_status()
                result = response.json()

            end_time = time.time()
            duration = end_time - start_time

            # Extract response stats
            response_text = result.get("message", {}).get("content", "")
            token_count = len(response_text.split())  # Rough token estimate
            tokens_per_second = token_count / duration if duration > 0 else 0

            run_result = {
                "run": run + 1,
                "duration": duration,
                "tokens": token_count,
                "tokens_per_second": tokens_per_second,
                "response_length": len(response_text)
            }

            results.append(run_result)
            logger.info(f"  Run {run + 1}: {tokens_per_second:.2f} tok/s ({duration:.2f}s)")

            # Short delay between runs
            await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"❌ Run {run + 1} failed for {model}: {e}")
            results.append({
                "run": run + 1,
                "error": str(e),
                "duration": None,
                "tokens": 0,
                "tokens_per_second": 0
            })

    # Calculate averages
    successful_runs = [r for r in results if "error" not in r]
    if successful_runs:
        avg_duration = sum(r["duration"] for r in successful_runs) / len(successful_runs)
        avg_tokens_per_second = sum(r["tokens_per_second"] for r in successful_runs) / len(successful_runs)
        avg_tokens = sum(r["tokens"] for r in successful_runs) / len(successful_runs)
    else:
        avg_duration = 0
        avg_tokens_per_second = 0
        avg_tokens = 0

    return {
        "model": model,
        "test_runs": test_runs,
        "successful_runs": len(successful_runs),
        "failed_runs": test_runs - len(successful_runs),
        "results": results,
        "averages": {
            "duration": avg_duration,
            "tokens": avg_tokens,
            "tokens_per_second": avg_tokens_per_second
        }
    }

async def check_model_availability() -> list[str]:
    """Check which models are available in Ollama."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags")
            response.raise_for_status()
            data = response.json()

            available_models = [model["name"] for model in data.get("models", [])]
            logger.info(f"✅ Available models: {available_models}")
            return available_models

    except Exception as e:
        logger.error(f"❌ Failed to check model availability: {e}")
        return []

async def run_benchmark():
    """Run complete benchmark suite."""
    logger.info("🚀 Starting model performance benchmark")

    # Check available models
    available_models = await check_model_availability()
    if not available_models:
        logger.error("❌ No models available. Make sure Ollama is running.")
        return

    # Filter models to test
    models_to_test = [model for model in MODELS_TO_TEST if model in available_models]
    missing_models = [model for model in MODELS_TO_TEST if model not in available_models]

    if missing_models:
        logger.warning(f"⚠️ Missing models: {missing_models}")

    if not models_to_test:
        logger.error("❌ No target models available for testing")
        return

    logger.info(f"📊 Testing models: {models_to_test}")

    # Run benchmarks
    all_results = []

    for model in models_to_test:
        result = await test_model_performance(model)
        all_results.append(result)

        # Log summary
        if result["successful_runs"] > 0:
            avg_perf = result["averages"]["tokens_per_second"]
            logger.info(f"✅ {model}: {avg_perf:.2f} tok/s average")
        else:
            logger.info(f"❌ {model}: All runs failed")

    # Generate summary report
    logger.info("\n" + "="*60)
    logger.info("📊 BENCHMARK RESULTS SUMMARY")
    logger.info("="*60)

    # Sort by performance
    successful_results = [r for r in all_results if r["successful_runs"] > 0]
    successful_results.sort(key=lambda x: x["averages"]["tokens_per_second"], reverse=True)

    for i, result in enumerate(successful_results, 1):
        model = result["model"]
        avg_perf = result["averages"]["tokens_per_second"]
        avg_duration = result["averages"]["duration"]
        success_rate = (result["successful_runs"] / result["test_runs"]) * 100

        logger.info(f"{i}. {model}")
        logger.info(f"   Performance: {avg_perf:.2f} tokens/second")
        logger.info(f"   Avg Duration: {avg_duration:.2f}s")
        logger.info(f"   Success Rate: {success_rate:.0f}%")
        logger.info("")

    # Save detailed results
    timestamp = int(time.time())
    results_file = f"benchmark_results_{timestamp}.json"

    with open(results_file, 'w') as f:
        json.dump({
            "timestamp": timestamp,
            "test_prompt": TEST_PROMPT,
            "models_tested": models_to_test,
            "results": all_results
        }, f, indent=2)

    logger.info(f"💾 Detailed results saved to: {results_file}")

    # Recommendations based on results
    if successful_results:
        best_model = successful_results[0]
        logger.info("🎯 RECOMMENDATIONS:")
        logger.info(f"   Best performer: {best_model['model']} ({best_model['averages']['tokens_per_second']:.2f} tok/s)")

        # Find good balance of speed/capability
        qwen2_result = next((r for r in successful_results if r["model"] == "qwen2:7b"), None)
        if qwen2_result:
            logger.info(f"   Recommended default: qwen2:7b ({qwen2_result['averages']['tokens_per_second']:.2f} tok/s)")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
