# -*- coding: utf-8 -*-
import logging
from typing import List, Dict
from src.models.domain import ProjectModel, Service

logger = logging.getLogger("devops-agent")

class ArchitectureGraph:
    """
    Immutable dependency and topology graph. 
    Constructed once, then serves as the ground truth.
    """
    
    def __init__(self, model: ProjectModel):
        self._model = model
        self._nodes = {s.name: s for s in model.services}
        self._adj = {s.name: s.dependencies for s in model.services}
        self._ingress_node = self._find_ingress_node()
        
    def _find_ingress_node(self) -> str:
        # Simplistic: service marked public or first one
        for s in self._model.services:
            if s.is_public:
                return s.name
        return self._model.services[0].name if self._model.services else "none"

    @property
    def nodes(self) -> Dict[str, Service]:
        return self._nodes

    @property
    def dependencies(self) -> Dict[str, List[str]]:
        return self._adj

    @property
    def ingress_node(self) -> str:
        return self._ingress_node

    def get_service_topology(self) -> List[str]:
        """
        Returns a topological sort of services (dependencies first).
        """
        visited = set()
        stack = []
        
        def visit(node):
            if node not in visited:
                visited.add(node)
                for dep in self._adj.get(node, []):
                    if dep in self._nodes:
                        visit(dep)
                stack.append(node)
        
        for node in self._nodes:
            visit(node)
            
        return stack
