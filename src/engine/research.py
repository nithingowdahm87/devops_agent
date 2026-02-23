from src.llm_clients.nvidia_client import NvidiaClient

class Researcher:
    def __init__(self):
        # Using NVIDIA for elite 405B research
        self.planner_llm = NvidiaClient()
        self.research_llm = NvidiaClient()
        
    def generate_spec(self, user_request: str, artifact_type: str) -> str:
        prompt = f"""
You are an elite DevOps Planner.
Given the following user request, write a strict structural specification for the {artifact_type} that needs to be built.

Focus on:
- What this file must do (core requirements).
- What it must avoid.
- Security constraints that apply.

Do not write the actual configuration file yet. Write the specification (spec.md). Be extremely concise (max 150 words).

USER REQUEST:
{user_request}
"""
        self.planner_llm.temperature = 0.2
        return self.planner_llm.call(prompt)

    def conduct_research(self, user_request: str, artifact_type: str) -> str:
        prompt = f"""
You are a DevOps Researcher specializing in 2026 industry standards.
What are the latest best practices, security hardening patterns, and modern API usage recommendations for building a {artifact_type} for this specific request?

Provide concise actionable bullet points (research_notes.md). Be extremely concise (max 150 words).
Do not generate the actual file. 

USER REQUEST:
{user_request}
"""
        self.research_llm.temperature = 0.5
        return self.research_llm.call(prompt)

    def run(self, user_request: str, artifact_type: str) -> tuple[str, str]:
        """Returns (spec, research_notes)"""
        spec = self.generate_spec(user_request, artifact_type)
        research = self.conduct_research(user_request, artifact_type)
        return spec, research

def run_research(user_request: str, artifact_type: str) -> tuple[str, str]:
    return Researcher().run(user_request, artifact_type)
