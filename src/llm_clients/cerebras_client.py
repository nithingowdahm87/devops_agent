import os
import requests
from src.utils.secrets import get_secret
from tenacity import retry, stop_after_attempt, wait_exponential

class CerebrasClient:
    """LLM Client for Cerebras (OpenAI-compatible)."""
    
    def __init__(self, model: str = "llama3.1-8b", temperature: float = 0.1):
        self.api_key = get_secret("CEREBRAS_API_KEY")
        self.model = model
        self.temperature = temperature
        self.base_url = "https://api.cerebras.ai/v1/chat/completions"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=5, max=20))
    def call(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are an elite DevOps Engineering Assistant."},
                {"role": "user", "content": prompt}
            ],
            "temperature": self.temperature,
        }
        
        try:
            resp = requests.post(self.base_url, headers=headers, json=data, timeout=60)
            
            if resp.status_code != 200:
                print(f"  [!] Cerebras API Error: {resp.status_code} - {resp.text}")
            
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  [!] Cerebras Call Failed: {e}")
            raise e
