"""
Thread-safe RAG (Retrieval-Augmented Generation) store using ChromaDB.

Provides a singleton RAGStore with thread-safe operations for concurrent access.
"""

from __future__ import annotations
import hashlib
import logging
import threading
from typing import Optional

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    chromadb = None

log = logging.getLogger(__name__)


class RAGStore:
    """
    Thread-safe singleton RAG store using ChromaDB.

    Uses double-checked locking pattern for thread-safe singleton initialization.
    All operations are protected by a reentrant lock for thread safety.
    """

    _instance: Optional['RAGStore'] = None
    _lock = threading.RLock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Only initialize once
        if hasattr(self, '_initialized'):
            return

        self._lock = threading.RLock()
        self._collection = None
        self._initialized = True
        self._init_chroma()

    def _init_chroma(self):
        """Initialize ChromaDB client and collection."""
        if not CHROMA_AVAILABLE:
            log.warning("ChromaDB not available - RAG disabled")
            self._collection = None
            return

        import shutil
        import os

        db_path = ".chroma_db"

        # Handle schema migration errors by cleaning up and retrying once
        for attempt in range(2):
            try:
                # Clean up corrupted DB on retry
                if attempt == 1 and os.path.exists(db_path):
                    log.warning("Retrying ChromaDB init after cleaning corrupted DB")
                    shutil.rmtree(db_path, ignore_errors=True)

                # Use persistent client with local directory
                self._client = chromadb.PersistentClient(
                    path=db_path,
                    settings=Settings(anonymized_telemetry=False)
                )
                self._collection = self._client.get_or_create_collection(
                    name="devops_rag",
                    metadata={"description": "DevOps best practices RAG store"}
                )
                log.info("RAG store initialized with ChromaDB")
                return
            except Exception as e:
                if attempt == 0 and ("no such column" in str(e) or "schema" in str(e).lower()):
                    log.warning(f"ChromaDB schema issue, will retry after cleanup: {e}")
                    continue
                log.warning(f"Failed to initialize ChromaDB: {e}. RAG disabled.")
                self._collection = None
                return

    def add(self, content: str, metadata: dict, doc_id: str) -> bool:
        """
        Add a document to the RAG store.

        Args:
            content: Document content
            metadata: Document metadata
            doc_id: Unique document ID

        Returns:
            True if added successfully, False otherwise
        """
        if not self._collection:
            return False

        with self._lock:
            try:
                self._collection.add(
                    documents=[content],
                    metadatas=[metadata],
                    ids=[doc_id]
                )
                return True
            except Exception as e:
                log.warning(f"Failed to add document to RAG store: {e}")
                return False

    def query(self, query: str, artifact_type: str, n_results: int = 3) -> str:
        """
        Query the RAG store for relevant snippets.

        Args:
            query: Query string
            artifact_type: Type of artifact (docker, k8s, ci)
            n_results: Maximum number of results

        Returns:
            Concatenated snippets or empty string if none found
        """
        if not self._collection:
            return ""

        with self._lock:
            try:
                results = self._collection.query(
                    query_texts=[query],
                    n_results=n_results,
                    where={"artifact_type": artifact_type} if artifact_type else None
                )

                if not results or not results.get('documents') or not results['documents'][0]:
                    return ""

                snippets = results['documents'][0]
                # Cap total response size
                total = "\n\n".join(snippets)
                return total[:1200] if len(total) > 1200 else total

            except Exception as e:
                log.warning(f"RAG query failed: {e}")
                return ""

    def get_count(self) -> int:
        """Get the number of documents in the store."""
        if not self._collection:
            return 0
        with self._lock:
            try:
                return self._collection.count()
            except Exception:
                return 0

    def is_ready(self) -> bool:
        """Check if the RAG store is initialized and ready."""
        return self._collection is not None


# Global singleton instance
_rag_store: Optional[RAGStore] = None
_rag_lock = threading.Lock()


def get_rag_store() -> RAGStore:
    """Get the global RAG store singleton."""
    global _rag_store
    if _rag_store is None:
        with _rag_lock:
            if _rag_store is None:
                _rag_store = RAGStore()
    return _rag_store


def get_rag_context(query: str, artifact_type: str) -> str:
    """
    Get RAG context for a query.

    Args:
        query: Query string
        artifact_type: Type of artifact (docker, k8s, ci)

    Returns:
        Relevant context snippets or empty string
    """
    store = get_rag_store()
    if not store.is_ready():
        return ""
    return store.query(query, artifact_type)


def save_to_rag(artifact_type: str, content: str, source: str) -> bool:
    """
    Save content to RAG store.

    Args:
        artifact_type: Type of artifact (docker, k8s, ci)
        content: Content to save
        source: Source identifier

    Returns:
        True if saved successfully
    """
    store = get_rag_store()
    if not store.is_ready():
        return False

    doc_id = hashlib.sha256(f"{artifact_type}:{content[:100]}".encode()).hexdigest()[:16]
    metadata = {
        "artifact_type": artifact_type,
        "source": source,
        "length": len(content)
    }
    return store.add(content, metadata, doc_id)