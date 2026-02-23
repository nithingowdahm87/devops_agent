# -*- coding: utf-8 -*-
import os
import pytest
from src.engine.artifact_manager import ArtifactManager
from src.engine.severity import Severity

def test_write_gate_blocks_critical(tmp_path):
    """Verify CRITICAL failures prevent file writing."""
    mgr = ArtifactManager(str(tmp_path), "dev")
    rel_path = "test.yaml"
    content = "apiVersion: v1"
    
    # CRITICAL should block
    success = mgr.write_gate(rel_path, content, Severity.CRITICAL)
    assert success is False
    assert not (tmp_path / rel_path).exists()
    
    # Check history still has it for audit
    history_files = os.listdir(os.path.join(tmp_path, ".artifacts_history/dev", mgr.run_id))
    assert rel_path in history_files

def test_write_gate_saves_broken(tmp_path):
    """Verify HIGH failures save to .broken."""
    mgr = ArtifactManager(str(tmp_path), "dev")
    rel_path = "test.yaml"
    content = "apiVersion: v1"
    
    success = mgr.write_gate(rel_path, content, Severity.HIGH)
    assert success is False
    assert not (tmp_path / rel_path).exists()
    assert (tmp_path / (rel_path + ".broken")).exists()

def test_write_gate_allows_low(tmp_path):
    """Verify LOW failures are written to primary path."""
    mgr = ArtifactManager(str(tmp_path), "dev")
    rel_path = "test.yaml"
    content = "apiVersion: v1"
    
    success = mgr.write_gate(rel_path, content, Severity.LOW)
    assert success is True
    assert (tmp_path / rel_path).exists()
