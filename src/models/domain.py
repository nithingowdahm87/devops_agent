# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass(frozen=True)
class Service:
    name: str
    language: str
    runtime_version: str
    base_image: str
    port: int
    dependencies: List[str] = field(default_factory=list)
    is_public: bool = False
    requires_db: bool = False
    requires_cache: bool = False
    scaling_mode: str = "horizontal" # horizontal, stateful, serverless
    env_vars: Dict[str, str] = field(default_factory=dict)
    health_check_path: str = "/health"

@dataclass(frozen=True)
class ProjectModel:
    project_name: str
    services: List[Service]
    environment: str # dev, staging, prod
    security_profile: str = "standard" # standard, high, strict
    ingress_enabled: bool = True
    global_tags: Dict[str, str] = field(default_factory=dict)
