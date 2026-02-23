# -*- coding: utf-8 -*-
import os
import pytest
from src.agents.code_analysis_agent import CodeAnalysisAgent
from src.tools.file_ops import write_file

def test_db_discovery_scan(tmp_path):
    """Verify that CodeAnalysisAgent finds databases via file scanning."""
    agent = CodeAnalysisAgent(str(tmp_path))
    
    # Create a dummy SQL file
    write_file(os.path.join(tmp_path, "schema.sql"), "CREATE TABLE users; -- postgresql")
    # Create a dummy properties file
    write_file(os.path.join(tmp_path, "application.properties"), "spring.datasource.url=jdbc:postgresql://localhost:5432/db")
    
    analysis = {
        "databases": {"rdbms": {}, "cache": {}, "nosql": {}},
        "raw_context_summary": ""
    }
    
    agent._verify_db_detection(analysis)
    
    assert "PostgreSQL" in analysis["databases"]["rdbms"]
    assert analysis["databases"]["rdbms"]["PostgreSQL"] == ["detected_via_file_scan"]

def test_redis_discovery_scan(tmp_path):
    """Verify Redis discovery via .env."""
    agent = CodeAnalysisAgent(str(tmp_path))
    write_file(os.path.join(tmp_path, ".env"), "REDIS_URL=redis://localhost:6379")
    
    analysis = {
        "databases": {"rdbms": {}, "cache": {}, "nosql": {}},
        "raw_context_summary": ""
    }
    agent._verify_db_detection(analysis)
    assert "Redis" in analysis["databases"]["cache"]
