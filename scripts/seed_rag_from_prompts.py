# scripts/seed_rag_from_prompts.py
import glob, os
from src.engine.rag import save_to_rag, RAGStore
from src.engine.chunker import simple_markdown_chunks

ROOT = os.path.dirname(os.path.dirname(__file__))

def main():
    store = RAGStore()
    if store.collection.count() > 3:
        print("RAG store already has prompts seeded, skipping.")
        return

    # 1) Existing golden paths
    store.seed_initial_knowledge()

    # 2) Prompt files
    prompt_paths = glob.glob(os.path.join(ROOT, "configs", "prompts", "**", "*.md"), recursive=True)
    for path in prompt_paths:
        rel = os.path.relpath(path, ROOT)
        # artifact_type: 'docker', 'k8s', 'ci', etc. derived from subdir name
        parts = rel.split(os.sep)
        if len(parts) < 3:
            continue
        artifact_type = parts[2]      # e.g. prompts/docker/docker_production.md -> 'docker'
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for chunk in simple_markdown_chunks(text):
            save_to_rag(artifact_type=artifact_type, content=chunk, source=f"prompt_file:{rel}")
    print("RAG prompt seeding complete.")

if __name__ == "__main__":
    main()
