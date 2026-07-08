"""
Safe Prompt Loader — Jinja2-based template rendering with security controls.

Replaces naive string replacement with a proper template engine that:
- Validates all context variables
- Auto-escapes content by default
- Prevents template injection via sandboxed environment
- Supports explicit variable allowlisting
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from jinja2 import Environment, SandboxedEnvironment, meta, select_autoescape
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False


class PromptTemplateError(Exception):
    """Raised when template loading or rendering fails."""
    pass


class PromptInjectionError(Exception):
    """Raised when potential prompt injection is detected."""
    pass


# Allowlisted template variables that can be safely substituted
ALLOWED_TEMPLATE_VARS = frozenset([
    "context",
    "plan_summary",
    "project_name",
    "service_name",
    "svc_name",
    "service_path",
    "language",
    "resources",
    "rag_best_practices",
])

# Variables that should never contain user-controlled content
CONTROL_VARS = frozenset([
    "context",
    "plan_summary",
    "rag_best_practices",
])

# Maximum sizes for context variables (prevents context stuffing)
MAX_VAR_SIZES = {
    "context": 15000,
    "plan_summary": 2000,
    "rag_best_practices": 3000,
    "project_name": 100,
    "service_name": 100,
    "svc_name": 100,
    "service_path": 200,
    "language": 50,
    "resources": 500,
}


class PromptRenderer:
    """
    Safe prompt template renderer using Jinja2 sandboxed environment.

    Usage:
        renderer = PromptRenderer()
        template = renderer.load_template("docker", "docker_production")
        rendered = renderer.render(template, context_dict)
    """

    def __init__(self, prompts_root: Optional[str] = None):
        self.prompts_root = Path(prompts_root or "configs/prompts")

        if JINJA2_AVAILABLE:
            # Sandboxed environment - no arbitrary Python execution
            self.env = SandboxedEnvironment(
                autoescape=select_autoescape(enabled_extensions=()),
                trim_blocks=True,
                lstrip_blocks=True,
                keep_trailing_newline=True,
            )
            # Disable dangerous builtins
            self.env.globals.clear()
            self.env.filters.clear()
        else:
            self.env = None
            # Fallback to basic string replacement (less safe)
            pass

    def load_template(self, stage: str, role: str) -> str:
        """
        Load prompt template from configs/prompts/{stage}/{role}.md

        Args:
            stage: Pipeline stage (dockerfile, kubernetes, etc.)
            role: Template variant (docker_production, k8s_production, etc.)

        Returns:
            Raw template string

        Raises:
            PromptTemplateError: If template file not found
        """
        prompt_path = self.prompts_root / stage / f"{role}.md"
        if not prompt_path.exists():
            raise PromptTemplateError(f"Prompt not found: {prompt_path}")
        return prompt_path.read_text(encoding="utf-8")

    def render(self, template: str, context: Dict[str, Any]) -> str:
        """
        Render template with context using safe substitution.

        Args:
            template: Raw template string
            context: Dictionary of template variables

        Returns:
            Rendered template string

        Raises:
            PromptTemplateError: If rendering fails
            PromptInjectionError: If injection attempt detected
        """
        # Validate and sanitize context
        safe_context = self._validate_context(context)

        if self.env and JINJA2_AVAILABLE:
            return self._render_jinja2(template, safe_context)
        else:
            return self._render_basic(template, safe_context)

    def _validate_context(self, context: Dict[str, Any]) -> Dict[str, str]:
        """
        Validate context variables against allowlist and size limits.

        Returns sanitized dict with only allowed keys and size-limited values.
        """
        safe = {}
        for key in ALLOWED_TEMPLATE_VARS:
            if key in context:
                value = str(context[key])
                max_size = MAX_VAR_SIZES.get(key, 1000)
                if len(value) > max_size:
                    # Truncate with clear marker
                    value = value[:max_size] + "\n...[TRUNCATED: EXCEEDS LIMIT]..."
                safe[key] = value
            else:
                safe[key] = ""  # Empty string for missing allowed keys

        # Detect extra keys not in allowlist
        extra_keys = set(context.keys()) - ALLOWED_TEMPLATE_VARS
        if extra_keys:
            raise PromptInjectionError(
                f"Template context contains disallowed keys: {extra_keys}. "
                f"Allowed keys: {sorted(ALLOWED_TEMPLATE_VARS)}"
            )

        return safe

    def _render_jinja2(self, template: str, context: Dict[str, str]) -> str:
        """Render using Jinja2 sandboxed environment."""
        try:
            # Parse template to check for suspicious constructs
            ast = self.env.parse(template)
            # Check for undefined variables that might indicate injection
            undeclared = meta.find_undeclared_variables(ast)
            suspicious = undeclared - ALLOWED_TEMPLATE_VARS
            if suspicious:
                raise PromptInjectionError(
                    f"Template references undeclared variables: {suspicious}"
                )

            # Render with autoescaping
            rendered = self.env.from_string(template).render(**context)
            return rendered
        except PromptInjectionError:
            raise
        except Exception as e:
            raise PromptTemplateError(f"Jinja2 template rendering failed: {e}")

    def _render_basic(self, template: str, context: Dict[str, str]) -> str:
        """
        Fallback basic renderer using string replacement.
        Less safe but works without Jinja2.
        """
        result = template

        # Only replace allowed keys, with explicit patterns
        for key in ALLOWED_TEMPLATE_VARS:
            value = context.get(key, "")
            patterns = [
                "{" + key + "}",
                "{{ " + key + " }}",
                "{{" + key + "}}",
            ]
            for pattern in patterns:
                if pattern in result:
                    result = result.replace(pattern, value)

        return result

    def extract_variables(self, template: str) -> List[str]:
        """Extract all variable references from a template."""
        if self.env and JINJA2_AVAILABLE:
            try:
                ast = self.env.parse(template)
                return list(meta.find_undeclared_variables(ast))
            except Exception:
                pass

        # Fallback: regex-based extraction
        import re
        # Match {var}, {{ var }}, {{var}}
        vars_found = set()
        for pattern in [r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}"]:
            vars_found.update(re.findall(pattern, template))
        return list(vars_found)


# Global renderer instance
_renderer: Optional[PromptRenderer] = None


def get_renderer() -> PromptRenderer:
    """Get or create global prompt renderer."""
    global _renderer
    if _renderer is None:
        _renderer = PromptRenderer()
    return _renderer


def load_prompt(stage: str, role: str) -> str:
    """
    Load prompt template from configs/prompts/ (backward compatible).

    Args:
        stage: dockerfile, kubernetes, cicd, etc.
        role: writer_a_generalist, writer_b_security, etc.

    Returns:
        Prompt template string
    """
    return get_renderer().load_template(stage, role)


def render_prompt(template: str, context: Dict[str, Any]) -> str:
    """
    Render prompt template with context (backward compatible).

    Args:
        template: Raw template string
        context: Dictionary of template variables

    Returns:
        Rendered template string
    """
    return get_renderer().render(template, context)