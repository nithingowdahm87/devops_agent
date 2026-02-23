# -*- coding: utf-8 -*-
import os
import pytest
from src.tools.file_ops import write_file, read_file

def test_utf8_corruption(tmp_path):
    """Verify that special characters are not corrupted during write/read."""
    special_content = "🚀 DevOps AI Agent - UTF-8 Test: π, Ω, 中文, ✨"
    test_file = tmp_path / "encoding_test.txt"
    
    write_file(str(test_file), special_content)
    read_back = read_file(str(test_file))
    
    assert read_back == special_content
    # Check specifically for the rocket emoji and Pi
    assert "🚀" in read_back
    assert "π" in read_back
