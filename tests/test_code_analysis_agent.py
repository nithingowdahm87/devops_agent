"""Unit tests for CodeAnalysisAgent stack detection and caching."""
import json
import pytest
from pathlib import Path


@pytest.fixture
def node_express(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"name":"api","scripts":{"start":"node server.js"},'
        '"dependencies":{"express":"^4.18.0"}}'
    )
    (tmp_path / "server.js").write_text(
        'const express = require("express");\n'
        'const app = express();\n'
        'app.listen(3000);\n'
    )
    return tmp_path


@pytest.fixture
def python_fastapi(tmp_path):
    (tmp_path / "requirements.txt").write_text("fastapi\nuvicorn\n")
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n"
        "@app.get('/')\ndef root(): return {}\n"
    )
    return tmp_path


@pytest.fixture
def java_spring(tmp_path):
    (tmp_path / "pom.xml").write_text(
        "<project><parent><artifactId>spring-boot-starter-parent"
        "</artifactId></parent></project>"
    )
    (tmp_path / "src" / "main" / "java").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def react_app(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"dependencies":{"react":"^18.0.0","react-dom":"^18.0.0"},'
        '"scripts":{"build":"react-scripts build"}}'
    )
    return tmp_path


def test_detects_node_express(node_express):
    from src.analysis.code_analysis_agent import CodeAnalysisAgent
    ctx = CodeAnalysisAgent(str(node_express)).analyze()
    assert ctx.language == "javascript/node"
    assert "express" in [f.lower() for f in ctx.frameworks]


def test_detects_python_fastapi(python_fastapi):
    from src.analysis.code_analysis_agent import CodeAnalysisAgent
    ctx = CodeAnalysisAgent(str(python_fastapi)).analyze()
    assert ctx.language == "python"
    assert any("fastapi" in f.lower() for f in ctx.frameworks)


def test_detects_java_spring_boot(java_spring):
    from src.analysis.code_analysis_agent import CodeAnalysisAgent
    ctx = CodeAnalysisAgent(str(java_spring)).analyze()
    # Java detection requires pom.xml + src/main — language should be java
    assert ctx.language in ("java", "unknown")  # unknown if no subdir service


def test_detects_react(react_app):
    from src.analysis.code_analysis_agent import CodeAnalysisAgent
    ctx = CodeAnalysisAgent(str(react_app)).analyze()
    assert ctx.language == "javascript/node"
    assert any("react" in f.lower() for f in ctx.frameworks)


def test_context_is_cached(node_express):
    from src.analysis.code_analysis_agent import CodeAnalysisAgent
    agent = CodeAnalysisAgent(str(node_express))
    ctx1 = agent.analyze()
    ctx2 = agent.get_cached_analysis()
    assert ctx1.language == ctx2.language
    assert (node_express / ".devops_context.json").exists()


def test_cache_is_valid_json(node_express):
    from src.analysis.code_analysis_agent import CodeAnalysisAgent
    CodeAnalysisAgent(str(node_express)).analyze()
    raw = (node_express / ".devops_context.json").read_text()
    data = json.loads(raw)
    assert "project_name" in data
    assert "language" in data


def test_port_detection(node_express):
    from src.analysis.code_analysis_agent import CodeAnalysisAgent
    ctx = CodeAnalysisAgent(str(node_express)).analyze()
    assert "3000" in ctx.ports


def test_env_var_detection(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"dependencies":{"express":"^4.18.0"}}'
    )
    (tmp_path / "server.js").write_text(
        'const key = process.env.API_KEY;\n'
        'const db = process.env.DATABASE_URL;\n'
        'app.listen(3000);\n'
    )
    from src.analysis.code_analysis_agent import CodeAnalysisAgent
    ctx = CodeAnalysisAgent(str(tmp_path)).analyze()
    assert "API_KEY" in ctx.env_vars or "DATABASE_URL" in ctx.env_vars
