# -*- coding: utf-8 -*-
import pytest
from src.engine.severity import Severity, ExitCode, get_exit_code

def test_severity_exit_mapping():
    """Verify severity levels map to correct CLI exit codes."""
    assert get_exit_code(Severity.CRITICAL) == ExitCode.CRITICAL_ERROR
    assert get_exit_code(Severity.HIGH) == ExitCode.POLICY_VIOLATION
    assert get_exit_code(Severity.MEDIUM) == ExitCode.SUCCESS
    assert get_exit_code(Severity.LOW) == ExitCode.SUCCESS
