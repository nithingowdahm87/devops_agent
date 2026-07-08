import os
from openai import OpenAI
from src.utils.secrets import get_secret
from tenacity import retry, stop_after_attempt, wait_exponential

class NvidiaClient:
    """LLM Client for NVIDIA NIM (OpenAI-compatible)."""
    
    def __init__(self, model: str = "nvidia/nemotron-3-ultra-550b-a55b", temperature: float = 1):
        self.api_key = get_secret("NVIDIA_API_KEY")
        self.model = model
        self.temperature = temperature
        self.client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=self.api_key
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=5, max=20))
    def call(self, prompt: str) -> str:
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an elite DevOps Engineering Assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                top_p=0.95,
                max_tokens=16384,
                extra_body={"chat_template_kwargs":{"enable_thinking":True},"reasoning_budget":16384},
                stream=True
            )
            
            final_content = ""
            for chunk in completion:
                if not chunk.choices:
                    continue
                reasoning = getattr(chunk.choices[0].delta, "reasoning_content", None)
                if reasoning:
                    print(reasoning, end="")
                if chunk.choices[0].delta.content is not None:
                    final_content += chunk.choices[0].delta.content
                    
            return final_content.strip()
        except Exception as e:
            print(f"  [!] NVIDIA Call Failed: {e}")
            raise e
