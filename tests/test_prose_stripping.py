# -*- coding: utf-8 -*-
import pytest
from src.engine.extractor import Extractor

def test_prose_stripping_yaml():
    """Verify that LLM prose is correctly stripped from YAML artifacts."""
    llm_response = """
Here is the requested Kubernetes manifest. It includes a Deployment and a Service.
I used the latest best practices for security.

### FILENAME: k8s/manifest.yaml
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  replicas: 2
```

I hope this helps! Let me know if you need any changes.
"""
    extracted = Extractor.extract_yaml(llm_response)
    
    assert "apiVersion: apps/v1" in extracted
    assert "I hope this helps" not in extracted
    assert "best practices" not in extracted
    # Should be valid YAML
    import yaml
    data = yaml.safe_load(extracted)
    assert data['kind'] == "Deployment"

def test_multiple_file_extraction():
    """Verify multiple files are extracted from a single response."""
    llm_response = """
### FILENAME: Dockerfile
```dockerfile
FROM node:20
```

### FILENAME: docker-compose.yml
```yaml
version: '3'
```
"""
    files = Extractor.extract_multiple_files(llm_response)
    assert len(files) == 2
    assert files[0]['path'] == "Dockerfile"
    assert "FROM node:20" in files[0]['content']
    assert files[1]['path'] == "docker-compose.yml"
