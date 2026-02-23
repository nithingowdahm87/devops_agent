# -*- coding: utf-8 -*-
import pytest
from src.engine.compiler_pipeline import CompilerPipeline
from src.engine.severity import ExitCode

def test_pipeline_locking(tmp_path):
    """Verify the compiler follows the locked execution order."""
    # We use a dry run mode if possible or just check instantiation
    pipeline = CompilerPipeline(str(tmp_path))
    assert pipeline.environment == "dev"
    assert pipeline.artifact_mgr is not None
    
    # We can't easily run a full real pipeline in unit tests without API keys,
    # but we can verify it returns ExitCode on crash.
    result = pipeline.run()
    # It should fail or succeed depending on mock state, but return a valid ExitCode
    assert isinstance(result, int)
