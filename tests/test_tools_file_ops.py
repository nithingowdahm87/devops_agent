import os
import pytest
from unittest.mock import patch
from src.tools.file_ops import _safe_path


class TestSafePath:
    def test_normal_path(self):
        """A normal relative path is resolved and returned."""
        result = _safe_path("/project", "sub/file.txt")
        assert result == os.path.abspath("/project/sub/file.txt")

    def test_path_traversal_blocked(self):
        """Path with .. escaping the root raises ValueError."""
        with pytest.raises(ValueError, match="Path escape"):
            _safe_path("/project", "../etc/passwd")

    def test_symlink_traversal_blocked(self):
        """Symlink that escapes root via .. is blocked."""
        with pytest.raises(ValueError, match="Path escape"):
            _safe_path("/project", "sub/../../etc/passwd")

    def test_absolute_path_outside_root(self):
        """An absolute path outside the project root raises ValueError."""
        with pytest.raises(ValueError, match="Path escape"):
            _safe_path("/project", "/etc/passwd")

    def test_absolute_path_inside_root(self):
        """An absolute path inside the root is allowed."""
        project = os.path.abspath("/project")
        result = _safe_path(project, f"{project}/ok.txt")
        assert result == f"{project}/ok.txt"

    def test_path_with_null_byte_rejected(self):
        """Path containing null byte is rejected."""
        with pytest.raises(ValueError, match="Path escape"):
            _safe_path("/project", "sub\0/file.txt")

    def test_empty_path_returns_root(self):
        """Empty path resolves to the project root itself."""
        result = _safe_path("/project", "")
        assert result == os.path.abspath("/project")