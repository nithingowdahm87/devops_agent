# -*- coding: utf-8 -*-
import logging
from typing import List, Dict, Optional
from src.models.domain import ProjectModel, Service

logger = logging.getLogger("devops-agent")


class ArchitectureGraph:
    """
    Immutable dependency and topology graph.
    Constructed once, then serves as the ground truth.

    Can be built either from a full ProjectModel OR incrementally via
    add_node() when no model is available (e.g. inside the orchestrator
    post-generation audit stage).
    """

    def __init__(self, model: Optional[ProjectModel] = None):
        if model is not None:
            self._model = model
            self._nodes: Dict[str, Service] = {s.name: s for s in model.services}
            self._adj: Dict[str, List[str]] = {
                s.name: s.dependencies for s in model.services
            }
            self._ports: Dict[str, str] = {
                s.name: str(getattr(s, "port", "8080")) for s in model.services
            }
            self._ingress_node = self._find_ingress_node()
        else:
            self._model = None
            self._nodes = {}
            self._adj = {}
            self._ports = {}
            self._ingress_node = "none"

    def add_node(self, name: str, port: str, dependencies: Optional[List[str]] = None):
        """Register a service node discovered at runtime."""
        self._nodes[name] = name          # type: ignore[assignment]
        self._adj[name] = dependencies or []
        self._ports[name] = str(port)
        if self._ingress_node == "none":
            self._ingress_node = name

    def _find_ingress_node(self) -> str:
        if self._model is None:
            return self._ingress_node
        for s in self._model.services:
            if getattr(s, "is_public", False):
                return s.name
        return self._model.services[0].name if self._model.services else "none"

    @property
    def nodes(self) -> Dict:
        return self._nodes

    @property
    def dependencies(self) -> Dict[str, List[str]]:
        return self._adj

    @property
    def ports(self) -> Dict[str, str]:
        return self._ports

    @property
    def ingress_node(self) -> str:
        return self._ingress_node

    def get_service_topology(self) -> List[str]:
        """Returns a topological sort of services (dependencies first)."""
        visited: set = set()
        stack: List[str] = []

        def visit(node: str):
            if node not in visited:
                visited.add(node)
                for dep in self._adj.get(node, []):
                    if dep in self._nodes:
                        visit(dep)
                stack.append(node)

        for node in list(self._nodes.keys()):
            visit(node)

        return stack
