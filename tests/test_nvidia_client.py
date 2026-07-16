"""Unit tests for NvidiaClient — fail-fast key validation and retry behaviour."""
import pytest
from unittest.mock import MagicMock, patch


def test_raises_on_missing_api_key(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_NIM_API_KEY_NEMOTRON", raising=False)
    from src.llm_clients.nvidia_client import NvidiaClient
    with pytest.raises(RuntimeError, match="NVIDIA_API_KEY"):
        NvidiaClient(api_key=None)


def test_raises_on_empty_string_key(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_NIM_API_KEY_NEMOTRON", raising=False)
    from src.llm_clients.nvidia_client import NvidiaClient
    with pytest.raises(RuntimeError, match="NVIDIA_API_KEY"):
        NvidiaClient(api_key="")


def test_accepts_valid_key(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    from src.llm_clients.nvidia_client import NvidiaClient
    client = NvidiaClient(api_key="nvapi-test-key")
    assert client.api_key == "nvapi-test-key"


def test_picks_up_key_from_env(monkeypatch):
    monkeypatch.delenv("NVIDIA_NIM_API_KEY_NEMOTRON", raising=False)
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-from-env")
    # Instantiate directly — NvidiaClient reads env at __init__ time
    from src.llm_clients.nvidia_client import NvidiaClient
    client = NvidiaClient()  # no explicit api_key — should pick up from env
    assert client.api_key == "nvapi-from-env"


def test_call_returns_string(monkeypatch):
    from src.llm_clients.nvidia_client import NvidiaClient
    client = NvidiaClient(api_key="nvapi-test-key")

    fake_response = MagicMock()
    fake_response.choices = [MagicMock(message=MagicMock(content="FROM node:20-slim"))]
    monkeypatch.setattr(
        client._client.chat.completions, "create",
        lambda **kwargs: fake_response,
    )
    result = client.call("generate a dockerfile", stream=False)
    assert result == "FROM node:20-slim"


def test_raises_llm_error_after_max_retries(monkeypatch):
    from src.llm_clients.nvidia_client import NvidiaClient
    from src.utils.errors import LLMError

    client = NvidiaClient(api_key="nvapi-test-key")

    def always_fail(**kwargs):
        raise ConnectionError("network down")

    monkeypatch.setattr(client._client.chat.completions, "create", always_fail)

    with pytest.raises((LLMError, ConnectionError)):
        client.call("hello", stream=False)
