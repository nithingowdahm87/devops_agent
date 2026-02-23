import os
import requests
from src.utils.secrets import get_secret
from tenacity import retry, stop_after_attempt, wait_exponential

class OpenRouterClient:
    """LLM Client for OpenRouter (OpenAI-compatible)."""
    
    def __init__(self, model: str = "deepseek/deepseek-r1-0528:free", temperature: float = 0.1):
        self.api_key = get_secret("OPENROUTER_API_KEY")
        self.model = model
        self.temperature = temperature
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=5, max=20))
    def call(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/nithingowdahm87/agent-langchain", # Recommended by OpenRouter
            "X-Title": "DevOps Agent",
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
            resp = requests.post(self.base_url, headers=headers, json=data, timeout=120)
            
            if resp.status_code != 200:
                print(f"  [!] OpenRouter API Error: {resp.status_code} - {resp.text}")
            
            resp.raise_for_status()
            res_json = resp.json()
            
            if "choices" in res_json and len(res_json["choices"]) > 0:
                return res_json["choices"][0]["message"]["content"]
            else:
                print(f"  [!] OpenRouter Unexpected Response: {res_json}")
                raise RuntimeError(f"No choices available in OpenRouter response: {res_json}")
        except Exception as e:
            print(f"  [!] OpenRouter Call Failed: {e}")
            raise e
