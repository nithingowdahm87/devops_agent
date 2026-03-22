# -*- coding: utf-8 -*-
"""
Tests for ArtifactManager.write_gate — environment-aware write behaviour.
"""
import os
import pytest
from src.engine.artifact_manager import ArtifactManager
from src.engine.severity import Severity


def test_write_gate_blocks_critical(tmp_path):
    """CRITICAL failures must prevent file writing (all environments)."""
    mgr = ArtifactManager(str(tmp_path), "dev")
    rel_path = "test.yaml"
    content = "apiVersion: v1"

    success = mgr.write_gate(rel_path, content, Severity.CRITICAL)
    assert success is False
    assert not (tmp_path / rel_path).exists()

    # History entry should still exist for audit trail
    history_files = os.listdir(os.path.join(tmp_path, ".artifacts_history/dev", mgr.run_id))
    assert rel_path in history_files


def test_write_gate_saves_broken(tmp_path):
    """HIGH failures in non-dev (prod) environment are saved to .broken, not the primary path."""
    # Use "prod" so write_gate does NOT take the dev short-circuit path
    mgr = ArtifactManager(str(tmp_path), "prod")
    rel_path = "test.yaml"
    content = "apiVersion: v1"

    success = mgr.write_gate(rel_path, content, Severity.HIGH)
    assert success is False
    assert not (tmp_path / rel_path).exists()
    assert (tmp_path / (rel_path + ".broken")).exists()


def test_write_gate_allows_low(tmp_path):
    """LOW failures are written to the primary path (all environments)."""
    mgr = ArtifactManager(str(tmp_path), "dev")
    rel_path = "test.yaml"
    content = "apiVersion: v1"

    success = mgr.write_gate(rel_path, content, Severity.LOW)
    assert success is True
    assert (tmp_path / rel_path).exists()
