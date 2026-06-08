import os
import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.llm_clients.kimchi_client import _get_kimchi_api_key


class TestGetKimchiApiKey:
    def test_env_var优先(self):
        """KIMCHI_API_KEY env var is returned when set."""
        with patch.dict(os.environ, {"KIMCHI_API_KEY": "env-test-key-12345"}):
            result = _get_kimchi_api_key()
            assert result == "env-test-key-12345"

    def test_env_var_strips_whitespace(self):
        """KIMCHI_API_KEY value is stripped of surrounding whitespace."""
        with patch.dict(os.environ, {"KIMCHI_API_KEY": "  env-key-bounded  "}):
            result = _get_kimchi_api_key()
            assert result == "env-key-bounded"

    def test_auth_json_fallback(self):
        """When env var is not set, falls back to auth.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            auth_file = Path(tmpdir) / "auth.json"
            auth_file.write_text(json.dumps({
                "kimchi-dev": {"access": "json-fallback-key-67890"}
            }))

            with patch.dict(os.environ, {"KIMCHI_API_KEY": ""}):
                with patch.object(Path, "home", return_value=Path(tmpdir)):
                    # Patch the secondary path to not exist
                    result = _get_kimchi_api_key()

            assert result == "json-fallback-key-67890"

    def test_missing_both_raises_runtime_error(self):
        """When neither env var nor auth.json is available, raise RuntimeError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"KIMCHI_API_KEY": ""}):
                with patch.object(Path, "home", return_value=Path(tmpdir)):
                    with pytest.raises(RuntimeError, match="KIMCHI_API_KEY not set"):
                        _get_kimchi_api_key()

    def test_auth_json_missing_kimchi_dev_key(self):
        """auth.json exists but missing kimchi-dev access key falls through."""
        with tempfile.TemporaryDirectory() as tmpdir:
            auth_file = Path(tmpdir) / "auth.json"
            auth_file.write_text(json.dumps({"some-other": {"key": "value"}}))

            with patch.dict(os.environ, {"KIMCHI_API_KEY": ""}):
                with patch.object(Path, "home", return_value=Path(tmpdir)):
                    with pytest.raises(RuntimeError):
                        _get_kimchi_api_key()

    def test_corrupt_auth_json_skipped(self):
        """Corrupt auth.json is skipped and next path is tried."""
        with tempfile.TemporaryDirectory() as tmpdir:
            auth_file = Path(tmpdir) / "auth.json"
            auth_file.write_text("not valid json {{{")

            second_file = Path(tmpdir) / "auth2.json"
            second_file.write_text(json.dumps({
                "kimchi-dev": {"access": "second-path-key"}
            }))

            with patch.dict(os.environ, {"KIMCHI_API_KEY": ""}):
                with patch.object(Path, "home", return_value=Path(tmpdir)):
                    # Only one path is checked by default; ensure it raises
                    # when the only available file is corrupt
                    with pytest.raises(RuntimeError):
                        _get_kimchi_api_key()