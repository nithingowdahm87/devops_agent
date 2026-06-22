import warnings
warnings.warn(
    "src.engine.orchestrator is deprecated. Use src.decision_engine.orchestrator.V2Orchestrator instead.",
    DeprecationWarning,
    stacklevel=2,
)

import typing
import threading
import os
from src.engine.models import GeneratedFile
from src.engine.research import run_research
from src.engine.rag import get_rag_context
from src.engine.sampler import Sampler
from src.engine.constitution import critique_file
from src.engine.heal import Healer
from src.engine.validate import Validator
from src.engine.innovation import run_innovation_async
from src.engine.llm import call_llm                        # FIX 1: use router, not NvidiaClient
from src.engine.llm_generator import LLMGenerator          # FIX 2: import from correct module


class Orchestrator:
    def __init__(self):
        # FIX 3: Sampler now handles its own provider routing — no client needed
        self.sampler   = Sampler()
        self.validator = Validator()
        self.healer    = Healer()

    def _get_generator_prompt(self, task_type: str) -> str:
        prompt_map = {
            "docker":  "configs/prompts/docker/docker_production.md",
            "compose": "configs/prompts/docker/docker_compose.md",
            "k8s":     "configs/prompts/k8s/k8s_production.md",
            "ci":      "configs/prompts/cicd/cicd_production.md",
        }
        path = prompt_map.get(task_type.lower())
        if not path:
            return ""
        try:
            with open(path) as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def run_pipeline(
        self,
        user_request: str,
        artifact_type: str,
        build_context: dict,
        project_path: str,
    ) -> list[GeneratedFile]:

        # --- LAYER 0: Research & Spec ---
        spec_notes, research_notes = run_research(user_request, artifact_type)

        # --- LAYER 1: RAG Injection ---
        rag_context = get_rag_context(user_request, artifact_type)

        base_prompt  = self._get_generator_prompt(artifact_type)
        context_str  = "\n".join(f"{k}: {v}" for k, v in build_context.items())
        full_prompt  = f"""
{base_prompt}

APPLICATION CONTEXT:
{context_str}

USER REQUEST:
{user_request}

LAYER 0 (SPECIFICATION & CONSTRAINTS):
{spec_notes}

LAYER 0 (2026 BEST PRACTICES):
{research_notes}

LAYER 1 (RAG GOLDEN PATHS & CIS BENCHMARKS):
{rag_context}
"""

        # --- LAYER 2: Multi-provider consensus sampling ---
        print(f"\n🧠 Layer 2: Generating candidates via multi-provider consensus...")
        candidates = self.sampler.sample(full_prompt, task_type=artifact_type)
        if not candidates:
            print("❌ Failed to generate any valid candidates.")
            return []

        # Best-scored candidate is first (sampler sorts by rule coverage)
        winner_text = candidates[0]
        print(f"  [+] Layer 2 Complete: Consensus winner selected ({len(candidates)} candidate(s) scored).")

        # Parse into files using LLMGenerator's robust parser
        parser = LLMGenerator()
        files  = parser._parse_files(winner_text)
        if not files:
            print("❌ Failed to parse files out of the winning candidate.")
            return []

        final_artifacts = []
        for file in files:
            print(f"\n--- Processing File: {file.path} ---")

            # --- LAYER 3: Constitutional Critique ---
            print(f"  [>] Layer 3: Running Constitutional Critique...")
            critiqued_file = critique_file(file, artifact_type)

            # Resolve output path
            critiqued_file.path = os.path.normpath(
                os.path.join(project_path, critiqued_file.path)
            )

            # --- LAYER 4: Deterministic Validation ---
            print(f"  [>] Layer 4: Running Deterministic Validators...")
            val_result = self.validator.validate(critiqued_file)

            # --- LAYER 5: Surgical Heal Loop ---
            if not val_result.passed:
                print(f"  [!] Layer 5: Invoking Surgical Heal Loop...")
                healed_file = self.healer.heal(critiqued_file, val_result.errors)
                re_val      = self.validator.validate(healed_file)
                if not re_val.passed:
                    print("⚠️  Healer could not resolve all issues — escalate to human.")
                    final_artifacts.append(healed_file)
                else:
                    print("✅ Healer succeeded.")
                    final_artifacts.append(healed_file)
            else:
                print("✅ File passed validation directly.")
                final_artifacts.append(critiqued_file)

            self._write_to_disk(final_artifacts[-1])

            # --- LAYER 6: Innovation Flywheel ---
            print(f"  [>] Layer 6: Running Innovation Flywheel...")
            run_innovation_async(
                final_artifacts[-1].content, artifact_type, user_request
            )

        print(f"\n✅ Finished {artifact_type}: {len(final_artifacts)} file(s) processed.")
        return final_artifacts

    def _write_to_disk(self, file: GeneratedFile):
        os.makedirs(os.path.dirname(file.path), exist_ok=True)
        with open(file.path, "w") as f:
            f.write(file.content)
        print(f"💾 Saved to: {file.path}")


def run_feature_pipeline(
    user_request: str,
    artifact_type: str,
    build_context: dict,
    project_path: str,
) -> list[GeneratedFile]:
    return Orchestrator().run_pipeline(user_request, artifact_type, build_context, project_path)
