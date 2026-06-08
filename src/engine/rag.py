import os
import logging

log = logging.getLogger(__name__)

_CHROMADB_AVAILABLE = False

try:
    import chromadb
    from chromadb.config import Settings
    _CHROMADB_AVAILABLE = True
except ImportError:
    log.warning("chromadb not installed — RAG will use static fallback knowledge.")


class RAGStore:
    _docker_seed = (
        "Docker Best Practices 2026:\n"
        "- Use multi-stage builds to minimize image size.\n"
        "- Do not run containers as root; USER nonroot.\n"
        "- Avoid :latest tags; pin strict SHA or explicit version.\n"
        "- Order commands to leverage caching (COPY requirements first).\n"
        "- No hardcoded secrets."
    )
    _k8s_seed = (
        "Kubernetes Best Practices 2026:\n"
        "- Always configure requests and limits for CPU and memory.\n"
        "- Use readOnlyRootFilesystem where applicable.\n"
        "- Set runAsNonRoot: true and allowPrivilegeEscalation: false.\n"
        "- Define liveness and readiness probes.\n"
        "- Use namespaces; never deploy to 'default' implicitly."
    )
    _ci_seed = (
        "GitHub Actions CI/CD Best Practices 2026:\n"
        "- Use granular permissions: `contents: read` at minimum.\n"
        "- Pin actions to full commit SHA, not tags.\n"
        "- Avoid passing secrets directly to run commands if possible, use environment variables bounding.\n"
        "- Ensure workflow triggers are restricted (e.g., branches: [main])."
    )

    def __init__(self, db_path: str = ".chroma_db"):
        self.db_path = db_path
        self._client = None
        self._collection = None
        if _CHROMADB_AVAILABLE:
            self._init_chroma()

    @property
    def collection(self):
        return self._collection

    def _init_chroma(self):
        try:
            if not os.path.exists(self.db_path):
                os.makedirs(self.db_path)
            self._client = chromadb.PersistentClient(
                path=self.db_path,
                settings=Settings(allow_reset=True)
            )
            self._collection = self._client.get_or_create_collection(
                name="devops_knowledge_base",
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            log.warning("Failed to init ChromaDB: %s — using static fallback.", e)
            self._client = None
            self._collection = None

    def add_knowledge(self, artifact_type: str, content: str, source: str = "innovation_layer"):
        if not self._collection:
            return
        import hashlib
        doc_id = hashlib.sha256(content.encode()).hexdigest()[:16]
        self._collection.add(
            documents=[content],
            metadatas=[{"artifact_type": artifact_type, "source": source}],
            ids=[f"{artifact_type}_{doc_id}"]
        )
        log.info("Added knowledge to RAG store for %s (%s)", artifact_type, source)

    def retrieve(self, query: str, artifact_type: str, k: int = 1) -> str:
        if not self._collection:
            return self._static_fallback(artifact_type)
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=k,
                where={"artifact_type": artifact_type}
            )
            if not results["documents"] or not results["documents"][0]:
                return self._static_fallback(artifact_type)
            return "\n\n---\n\n".join(results["documents"][0])
        except Exception as e:
            log.warning("RAG query failed: %s — using static fallback.", e)
            return self._static_fallback(artifact_type)

    def _static_fallback(self, artifact_type: str) -> str:
        return {
            "docker": self._docker_seed,
            "k8s": self._k8s_seed,
            "ci": self._ci_seed,
        }.get(artifact_type, "No specific best practices found. Follow general industry standards.")

    def seed_initial_knowledge(self):
        if not self._collection:
            return
        count = self._collection.count()
        if count > 0:
            return
        self.add_knowledge("docker", self._docker_seed, "initial_seed")
        self.add_knowledge("k8s", self._k8s_seed, "initial_seed")
        self.add_knowledge("ci", self._ci_seed, "initial_seed")


def get_rag_context(query: str, artifact_type: str) -> str:
    store = RAGStore()
    store.seed_initial_knowledge()
    return store.retrieve(query, artifact_type)


def save_to_rag(artifact_type: str, content: str, source: str = "innovation_layer"):
    store = RAGStore()
    store.add_knowledge(artifact_type, content, source)

