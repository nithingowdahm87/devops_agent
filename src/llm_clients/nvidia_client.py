import os
import time
import logging
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.utils.errors import LLMError

log = logging.getLogger(__name__)

_BASE_URL = "https://integrate.api.nvidia.com/v1"
_DEFAULT_MODEL = os.environ.get("NVIDIA_MODEL", "meta/llama-3.1-405b-instruct")


class NvidiaClient:
    """NVIDIA NIM LLM client via OpenAI-compatible SDK. Fail-fast on missing key."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        resolved_key = api_key or os.environ.get("NVIDIA_API_KEY", "").strip()
        if not resolved_key:
            raise RuntimeError(
                "\n[devops-agent] NVIDIA_API_KEY is not set.\n"
                "  Export it:  export NVIDIA_API_KEY=nvapi-...\n"
                "  Or add it to your .env file.\n"
                "  Get a key:  https://build.nvidia.com\n"
            )
        self.api_key = resolved_key
        self.model = model or os.environ.get("NVIDIA_MODEL", _DEFAULT_MODEL)
        self._client = OpenAI(base_url=_BASE_URL, api_key=self.api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=20),
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        reraise=True,
    )
    def call(
        self,
        prompt: str,
        *,
        system_prompt: str = "You are an elite DevOps Engineering Assistant.",
        temperature: float = 0.1,
        max_tokens: int = 8192,
        stream: bool = False,
    ) -> str:
        t0 = time.perf_counter()
        try:
            completion = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                top_p=0.95,
                max_tokens=max_tokens,
                stream=stream,
            )

            if stream:
                content = ""
                for chunk in completion:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content += chunk.choices[0].delta.content
            else:
                content = completion.choices[0].message.content or ""

            log.info(
                "llm_call_ok",
                extra={"model": self.model, "latency_ms": round((time.perf_counter() - t0) * 1000, 1)},
            )
            return content.strip()

        except Exception as e:
            log.error(
                "llm_call_failed",
                extra={"model": self.model, "error": str(e), "latency_ms": round((time.perf_counter() - t0) * 1000, 1)},
            )
            raise LLMError(str(e), retryable=True) from e
