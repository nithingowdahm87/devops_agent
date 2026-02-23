import os
import requests
from src.utils.secrets import get_secret
from tenacity import retry, stop_after_attempt, wait_exponential

class NvidiaClient:
    """LLM Client for NVIDIA NIM (OpenAI-compatible)."""
    
    def __init__(self, model: str = "meta/llama-3.1-405b-instruct", temperature: float = 0.2):
        self.api_key = get_secret("NVIDIA_API_KEY")
        self.model = model
        self.temperature = temperature
        self.base_url = "https://integrate.api.nvidia.com/v1/chat/completions"

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
            "max_tokens": 4096,
            "top_p": 0.7
        }
        
        try:
            resp = requests.post(self.base_url, headers=headers, json=data, timeout=120)
            
            if resp.status_code != 200:
                print(f"  [!] NVIDIA API Error: {resp.status_code} - {resp.text}")
            
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  [!] NVIDIA Call Failed: {e}")
            raise e
