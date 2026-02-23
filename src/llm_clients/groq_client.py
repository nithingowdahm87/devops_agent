import os
import requests
from src.utils.secrets import get_secret
from tenacity import retry, stop_after_attempt, wait_exponential

class GroqClient:
    def __init__(self, model: str = "llama-3.3-70b-versatile", temperature: float = 0.1):
        self.api_key = get_secret("GROQ_API_KEY")
        self.model = model
        self.temperature = temperature
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=10, max=60))
    def call(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
        }
        # First attempt with primary model
        resp = requests.post(self.base_url, headers=headers, json=data, timeout=60)
        
        # If rate limited (429) or other errors, let's immediately try fallback if it was the primary model
        if resp.status_code == 429 and self.model == "llama-3.3-70b-versatile":
            print("  [⚠️] Rate limited on 70b. Falling back to llama-3.1-8b-instant...")
            data["model"] = "llama-3.1-8b-instant"
            resp = requests.post(self.base_url, headers=headers, json=data, timeout=60)

        if resp.status_code != 200:
            print(f"  [!] Groq API Error: {resp.status_code} - {resp.text}")

        # Let tenacity handle other persistent HTTP errors
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
