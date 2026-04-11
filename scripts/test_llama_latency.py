import time
import os
from openai import OpenAI

start_time = time.time()
print("Connecting to llama-server at http://127.0.0.1:8080/v1...")

client = OpenAI(
    base_url="http://127.0.0.1:8080/v1",
    api_key="none"
)

try:
    response = client.chat.completions.create(
        model="qwen-coder-1.5b.gguf",
        messages=[{"role": "user", "content": "Say hello"}],
        max_tokens=64
    )
    elapsed = time.time() - start_time
    print(f"\nResponse: {response.choices[0].message.content}")
    print(f"Time taken: {elapsed:.2f} seconds")
except Exception as e:
    elapsed = time.time() - start_time
    print(f"\nFailed after {elapsed:.2f} seconds: {e}")
