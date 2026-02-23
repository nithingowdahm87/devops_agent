import os
import chromadb
from chromadb.config import Settings

class RAGStore:
    def __init__(self, db_path: str = ".chroma_db"):
        self.db_path = db_path
        self._ensure_db_dir()
        self.client = chromadb.PersistentClient(path=self.db_path, settings=Settings(allow_reset=True))
        
        # We use a single collection for simplicity, or we could separate by artifact_type
        self.collection = self.client.get_or_create_collection(
            name="devops_knowledge_base",
            metadata={"hnsw:space": "cosine"}
        )

    def _ensure_db_dir(self):
        if not os.path.exists(self.db_path):
            os.makedirs(self.db_path)

    def add_knowledge(self, artifact_type: str, content: str, source: str = "innovation_layer"):
        """Adds a piece of knowledge to the vector store."""
        # Generate a simple ID based on content hash or UUID
        import hashlib
        doc_id = hashlib.sha256(content.encode()).hexdigest()[:16]
        
        self.collection.add(
            documents=[content],
            metadatas=[{"artifact_type": artifact_type, "source": source}],
            ids=[f"{artifact_type}_{doc_id}"]
        )
        print(f"  [+] Added knowledge to RAG store for {artifact_type} ({source})")

    def retrieve(self, query: str, artifact_type: str, k: int = 1) -> str:
        """Retrieves top-k relevant knowledge chunks."""
        
        # Optional: we can filter by artifact type, but for now we just do a text query
        results = self.collection.query(
            query_texts=[query],
            n_results=k,
            where={"artifact_type": artifact_type}
        )
        
        if not results['documents'] or not results['documents'][0]:
            return "No specific best practices found in RAG store. Follow general industry standards."
            
        # Combine the retrieved documents
        combined = "\n\n---\n\n".join(results['documents'][0])
        return combined

    def seed_initial_knowledge(self):
        """Seeds the DB with initial, hardcoded golden paths if empty."""
        count = self.collection.count()
        if count > 0:
            return  # Already seeded
        
        # Docker Golden Path
        self.add_knowledge("docker", 
                           "Docker Best Practices 2026:\n- Use multi-stage builds to minimize image size.\n- Do not run containers as root; USER nonroot.\n- Avoid :latest tags; pin strict SHA or explicit version.\n- Order commands to leverage caching (COPY requirements first).\n- No hardcoded secrets.",
                           "initial_seed")
        
        # K8s Golden Path
        self.add_knowledge("k8s",
                           "Kubernetes Best Practices 2026:\n- Always configure requests and limits for CPU and memory.\n- Use readOnlyRootFilesystem where applicable.\n- Set runAsNonRoot: true and allowPrivilegeEscalation: false.\n- Define liveness and readiness probes.\n- Use namespaces; never deploy to 'default' implicitly.",
                           "initial_seed")

        # CI/CD Golden Path
        self.add_knowledge("ci",
                           "GitHub Actions CI/CD Best Practices 2026:\n- Use granular permissions: `contents: read` at minimum.\n- Pin actions to full commit SHA, not tags.\n- Avoid passing secrets directly to run commands if possible, use environment variables bounding.\n- Ensure workflow triggers are restricted (e.g., branches: [main]).",
                           "initial_seed")

def get_rag_context(query: str, artifact_type: str) -> str:
    store = RAGStore()
    store.seed_initial_knowledge()
    return store.retrieve(query, artifact_type)

def save_to_rag(artifact_type: str, content: str, source: str = "innovation_layer"):
    store = RAGStore()
    store.add_knowledge(artifact_type, content, source)

