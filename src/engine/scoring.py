# -*- coding: utf-8 -*-
import logging
from typing import Dict, Any, List
import yaml

logger = logging.getLogger("devops-agent")

class ScoringEngine:
    """
    Evaluates artifact completeness and quality.
    Penalizes probabilistic 'Namespace-only' fakeouts.
    """
    
    @staticmethod
    def score_k8s(content: str) -> float:
        """
        Calculates a score from 0-100 for a Kubernetes manifest.
        Mandatory: Deployment, Service.
        """
        score = 0.0
        try:
            docs = list(yaml.safe_load_all(content))
            kinds = {doc.get("kind") for doc in docs if doc and isinstance(doc, dict)}
            
            # 1. Base components (Mandatory: -25 penalty per missing kind)
            has_deployment = "Deployment" in kinds
            has_service = "Service" in kinds
            has_namespace = "Namespace" in kinds
            
            if has_deployment: score += 50
            if has_service: score += 30
            if has_namespace: score += 10
            
            # Penalties: If only Namespace or missing both D+S
            if not has_deployment and not has_service:
                score -= 50
                
            # 2. Quality checks
            low_content = content.lower()
            if "resources:" in low_content: score += 5
            if "readinessprobe:" in low_content: score += 5
            
            # Cap at 0-100
            return max(0.0, min(100.0, score))
            
        except Exception as e:
            logger.warning(f"K8s scoring failed: {e}")
            return 0.0

    @staticmethod
    def is_acceptable(score: float, threshold: float = 60.0) -> bool:
        return score >= threshold
