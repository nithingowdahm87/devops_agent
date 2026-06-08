import pytest
from src.decision_engine.generator.llm_generator import LLMGenerator


class TestCleanMarkdown:
    def _clean(self, info: str) -> str:
        """Helper that calls LLMGenerator._clean_markdown without a client."""
        gen = LLMGenerator(client=None, model_name="test")
        return gen._clean_markdown(info)

    def test_filname_prefix_strips_reasoning(self):
        """Input starting with FILENAME: preserves the directive and strips preamble."""
        raw = """The user wants me to create a Dockerfile for their Node app.
        I'll write a multi-stage build.

        FILENAME:Dockerfile
        FROM node:20-alpine
        RUN npm ci --production
        CMD ["node", "server.js"]"""
        result = self._clean(raw)
        assert result.startswith("FILENAME:Dockerfile")
        assert "The user wants" not in result

    def test_code_block_returns_largest(self):
        """When multiple ``` blocks exist, return the largest one."""
        raw = """Some preamble text.

        ```
        # Small block
        FROM python:3.9
        ```

        Here's the actual Dockerfile:

        ```
        # Larger block - more content here
        FROM python:3.11-slim
        WORKDIR /app
        COPY requirements.txt .
        RUN pip install -r requirements.txt
        COPY . .
        CMD ["python", "main.py"]
        ```

        Footer text."""
        result = self._clean(raw)
        assert "python:3.11-slim" in result
        assert "python:3.9" not in result

    def test_reasoning_text_stripped(self):
        """Reasoning phrases like "The user wants me to..." are stripped."""
        raw = """The user is asking me to create a Dockerfile.
        I need to use a multi-stage build approach.
        Let me write the correct content.

        FROM node:18-alpine
        WORKDIR /app
        COPY package*.json ./
        RUN npm install
        COPY . .
        CMD ["node", "index.js"]"""
        result = self._clean(raw)
        assert result.startswith("FROM node:18-alpine")
        assert "I need to" not in result
        assert "Let me write" not in result

    def test_real_dockerfile_passes_through(self):
        """Real Dockerfile content with no preamble passes through unchanged."""
        raw = """FROM nginx:alpine
        COPY dist /usr/share/nginx/html
        EXPOSE 80
        CMD ["nginx", "-g", "daemon off;"]"""
        result = self._clean(raw)
        assert result.strip() == raw.strip()

    def test_single_code_block_returned(self):
        """A single code block is extracted correctly."""
        raw = """Here's the Docker Compose file:

        ```yaml
        version: '3.8'
        services:
          web:
            image: nginx:alpine
            ports:
              - "80:80"
        ```

        Let me know if you need changes."""
        result = self._clean(raw)
        assert "version: '3.8'" in result
        assert "services:" in result
        assert "Here's the" not in result