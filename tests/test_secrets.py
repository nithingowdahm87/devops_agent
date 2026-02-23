"""Tests for src/utils/secrets.py — env-var fallback, missing keys, aliases."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestGetSecretFromEnv:
    """Verify the env-var fallback path (no AWS/Vault)."""

    def test_returns_env_value(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "my-test-key")
        from src.utils.secrets import get_secret
        assert get_secret("GOOGLE_API_KEY") == "my-test-key"

        from src.utils.secrets import get_secret

    def test_unknown_key_falls_back_to_env_name(self, monkeypatch):
        monkeypatch.setenv("CUSTOM_KEY", "custom-val")
        from src.utils.secrets import get_secret
        assert get_secret("CUSTOM_KEY") == "custom-val"


class TestGetSecretMissing:
    """Verify RuntimeError on missing secrets."""

    def test_raises_runtime_error(self, clean_env):
        from src.utils.secrets import get_secret
        with pytest.raises(RuntimeError, match="not found"):
            get_secret("GOOGLE_API_KEY")

    def test_error_message_includes_env_name(self, clean_env):
        from src.utils.secrets import get_secret
        with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
            get_secret("GOOGLE_API_KEY")
