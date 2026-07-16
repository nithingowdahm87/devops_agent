"""
Stress test for RAG store concurrency.
Tests concurrent retrieval calls to ensure thread safety and no data corruption.
"""

import pytest
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import chromadb  # noqa: F401
    _RAG_AVAILABLE = True
except ImportError:
    _RAG_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _RAG_AVAILABLE,
    reason="chromadb not installed — install with: pip install devops-agent[rag]",
)

from src.engine.rag import get_rag_store, save_to_rag, get_rag_context


def test_rag_concurrency():
    """Test RAG store thread safety under concurrent access."""
    store = get_rag_store()

    # Ensure store is initialized
    assert store.is_ready(), "RAG store not initialized"

    # Seed some test data
    for i in range(20):
        artifact_type = "docker" if i % 2 == 0 else "k8s"
        content = f"Best practice #{i}: Use multi-stage builds for {artifact_type} containers. " * 10
        save_to_rag(artifact_type, content, f"test-source-{i}")

    # Verify data was saved
    assert store.get_count() >= 20, "Test data not saved correctly"

    results = []
    errors = []
    context_sizes = []

    def query_rag(worker_id: int, artifact_type: str):
        """Worker function to query RAG store."""
        try:
            # Vary queries slightly
            query = f"Best practices for {artifact_type} with Node.js service"
            result = get_rag_context(query, artifact_type)
            context_sizes.append(len(result))
            return {"worker": worker_id, "type": artifact_type, "success": True, "size": len(result)}
        except Exception as e:
            errors.append({"worker": worker_id, "error": str(e)})
            return {"worker": worker_id, "type": artifact_type, "success": False, "error": str(e)}

    # Run concurrent queries
    num_workers = 20
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = []
        for i in range(num_workers):
            artifact_type = "docker" if i % 2 == 0 else "k8s"
            futures.append(executor.submit(query_rag, i, artifact_type))

        for future in as_completed(futures):
            results.append(future.result())

    # Verify results
    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    print(f"Total queries: {len(results)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")
    print(f"Errors: {errors}")
    print(f"Context sizes: min={min(context_sizes) if context_sizes else 0}, max={max(context_sizes) if context_sizes else 0}")

    # Assertions
    assert len(failed) == 0, f"Some queries failed: {failed}"
    assert len(successful) == num_workers, f"Expected {num_workers} successful, got {len(successful)}"
    assert all(size <= 1200 for size in context_sizes), f"Context size cap violated: {context_sizes}"
    assert all(size > 0 for size in context_sizes), f"Some queries returned empty results: {context_sizes}"

    # Verify no data bleed - docker queries should return docker content, k8s queries should return k8s content
    for r in successful:
        if r["type"] == "docker":
            # Could add more specific content verification here
            pass

    print("✅ RAG concurrency stress test PASSED")


def test_rag_singleton():
    """Verify RAGStore is a true singleton."""
    from src.engine.rag import get_rag_store, RAGStore

    store1 = get_rag_store()
    store2 = get_rag_store()
    store3 = RAGStore()

    assert store1 is store2, "get_rag_store() should return singleton"
    assert store1 is store3, "RAGStore() should return same singleton"
    print("✅ RAG singleton test PASSED")


def test_concurrent_save_and_query():
    """Test concurrent save and query operations."""
    from src.engine.rag import save_to_rag, get_rag_context, get_rag_store

    store = get_rag_store()

    results = []
    errors = []

    def save_worker(worker_id: int):
        try:
            artifact_type = "docker" if worker_id % 2 == 0 else "k8s"
            content = f"Concurrent save test #{worker_id}: Use multi-stage builds. " * 5
            save_to_rag(artifact_type, content, f"concurrent-test-{worker_id}")
            return {"worker": worker_id, "success": True}
        except Exception as e:
            return {"worker": worker_id, "success": False, "error": str(e)}

    def query_worker(worker_id: int):
        try:
            artifact_type = "docker" if worker_id % 2 == 0 else "k8s"
            result = get_rag_context(f"Best practices for {artifact_type}", artifact_type)
            return {"worker": worker_id, "success": True, "size": len(result)}
        except Exception as e:
            return {"worker": worker_id, "success": False, "error": str(e)}

    # Run mixed save/query operations
    num_workers = 20
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = []
        for i in range(num_workers):
            if i % 2 == 0:
                futures.append(executor.submit(save_worker, i))
            else:
                futures.append(executor.submit(query_worker, i))

        for future in as_completed(futures):
            results.append(future.result())

    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    print(f"Concurrent save/query: {len(successful)} successful, {len(failed)} failed")
    assert len(failed) == 0, f"Some operations failed: {failed}"
    print("✅ Concurrent save/query test PASSED")


if __name__ == "__main__":
    print("Running RAG concurrency tests...")
    test_rag_singleton()
    test_concurrent_save_and_query()
    test_rag_concurrency()
    print("\n✅ All RAG concurrency tests PASSED")