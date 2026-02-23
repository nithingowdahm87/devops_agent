# -*- coding: utf-8 -*-
import pytest
from src.engine.scoring import ScoringEngine

def test_k8s_completeness_scoring():
    """Verify that ScoringEngine penalizes partial K8s manifests."""
    # 1. Complete manifest
    complete_k8s = """
apiVersion: v1
kind: Namespace
metadata:
  name: test
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
spec:
  replicas: 2
---
apiVersion: v1
kind: Service
metadata:
  name: app
"""
    score = ScoringEngine.score_k8s(complete_k8s)
    assert score >= 90
    
    # 2. Namespace only (Should be penalized)
    namespace_only = "apiVersion: v1\nkind: Namespace\nmetadata:\n  name: test"
    score_ns = ScoringEngine.score_k8s(namespace_only)
    assert score_ns < 40 # Mandatory -25 penalty per missing D/S
    
    # 3. Deployment only
    deploy_only = "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: app"
    score_dep = ScoringEngine.score_k8s(deploy_only)
    assert score_dep > score_ns
    assert score_dep < 60
