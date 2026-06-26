"""Language and framework detection for tech stacks.

This module exposes the :class:`TechStack` dataclass that describes a
detected technology stack for a service, and the :class:`LanguageDetector`
class that inspects a project directory and produces a populated stack.
All fields on ``TechStack`` have sensible defaults so callers can
construct partial stacks (for example a static site that has no language
toolchain).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TechStack:
    """A detected technology stack used by a service in the repository.

    The fields are consumed by :class:`src.engine.artifact_generator.ArtifactGenerator`
    to produce Dockerfiles, CI workflows, Kubernetes manifests and
    docker-compose files. Defaults make the dataclass usable for static
    sites and other low-ceremony stacks while still allowing fully
    populated language stacks.
    """

    language: str = "python"
    framework: str = "static"
    runtime_version: str = "3.12"
    entry_point: str = "app.py"
    command: str = "python app.py"
    ports: List[int] = field(default_factory=lambda: [8080])
    package_manager: str = "pip"
    base_image: str = "python:3.12-slim"
    package_install_cmd: str = "pip install --no-cache-dir -r requirements.txt"
    healthcheck_path: str = "/health"
    run_user: str = "appuser"
    is_multi_stage: bool = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# Regex matches a package name as a standalone token. It must NOT be
# preceded or followed by characters that are valid inside a package name
# (alphanumerics, ``.``, ``_``, ``-``). This avoids false positives such as
# matching ``flask`` inside ``flask-cors`` or ``django`` inside
# ``django-cors-headers``.
_PACKAGE_NAME_RE = r"(?<![A-Za-z0-9_.-]){name}(?![A-Za-z0-9_.-])"


def _manifest_contains(manifest_text: str, package: str) -> bool:
    """Return ``True`` if *package* appears as a standalone token."""
    pattern = _PACKAGE_NAME_RE.format(name=re.escape(package))
    return re.search(pattern, manifest_text, re.IGNORECASE) is not None


def _empty_static_stack() -> TechStack:
    """Build a TechStack for "nothing was detected" cases."""
    return TechStack(
        language="unknown",
        framework="unknown",
        runtime_version="",
        entry_point="",
        command="",
        ports=[],
        package_manager="",
        base_image="",
        package_install_cmd="",
        healthcheck_path="/",
        is_multi_stage=False,
    )


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


class LanguageDetector:
    """Detect language, framework, and runtime from a project directory.

    The public entry point is :meth:`detect`. It runs each language
    detector in order and falls back to file-extension scanning when
    nothing matched.
    """

    # Candidate file names checked when looking for an entry point.
    PYTHON_ENTRY_CANDIDATES: tuple = ("app.py", "main.py", "server.py", "manage.py")
    NODE_ENTRY_CANDIDATES: tuple = ("server.js", "app.js", "index.js")

    # Directories ignored while scanning for file extensions.
    SKIP_DIRS: set = {
        "node_modules",
        "venv",
        ".venv",
        "env",
        "__pycache__",
        "target",
        "build",
        "dist",
        ".git",
        ".next",
        ".nuxt",
        "vendor",
        "out",
        ".gradle",
        ".idea",
        ".vscode",
    }

    # File extension to language mapping used by the extension-based fallback.
    EXTENSION_LANGUAGE_MAP: dict = {
        ".py": "python",
        ".pyx": "python",
        ".pyi": "python",
        ".js": "node",
        ".jsx": "node",
        ".ts": "node",
        ".tsx": "node",
        ".mjs": "node",
        ".cjs": "node",
        ".rs": "rust",
        ".go": "go",
        ".java": "java",
        ".kt": "java",
        ".kts": "java",
        ".scala": "java",
        ".groovy": "java",
        ".php": "php",
        ".rb": "ruby",
        ".erb": "ruby",
        ".cs": "dotnet",
        ".fs": "dotnet",
        ".vb": "dotnet",
        ".ex": "elixir",
        ".exs": "elixir",
    }

    # Framework/language -> default port mapping used by :meth:`_infer_ports`.
    _PORT_DEFAULTS: dict = {
        ("flask", "python"): [5000],
        ("fastapi", "python"): [8000],
        ("django", "python"): [8000],
        ("express", "node"): [3000],
        ("next", "node"): [3000],
        ("nuxt", "node"): [3000],
        ("nestjs", "node"): [3000],
        ("static", "node"): [80],
        ("static", "html"): [80],
        ("unknown", "rust"): [8080],
        ("unknown", "go"): [8080],
        ("maven", "java"): [8080],
        ("gradle", "java"): [8080],
        ("laravel", "php"): [8000],
        ("rails", "ruby"): [3000],
        ("unknown", "dotnet"): [5000],
        ("phoenix", "elixir"): [4000],
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, project_path: str) -> TechStack:
        """Inspect *project_path* and return a fully populated :class:`TechStack`.

        Tries each language-specific detector in order. Falls back to file
        extension scanning, then to a generic static stack.
        """
        if not project_path or not os.path.isdir(project_path):
            return _empty_static_stack()

        detectors = (
            self._detect_python,
            self._detect_node,
            self._detect_rust,
            self._detect_go,
            self._detect_java,
            self._detect_php,
            self._detect_ruby,
            self._detect_dotnet,
            self._detect_elixir,
        )
        for detector in detectors:
            try:
                stack = detector(project_path)
            except (OSError, ValueError, json.JSONDecodeError):
                stack = None
            if stack is not None:
                return stack

        # Static HTML fallback: no recognized manifest but index.html exists.
        if os.path.isfile(os.path.join(project_path, "index.html")):
            return TechStack(
                language="html",
                framework="static",
                runtime_version="",
                entry_point="index.html",
                command="nginx -g 'daemon off;'",
                ports=[8080],
                package_manager="",
                base_image="nginx:alpine",
                package_install_cmd="",
                healthcheck_path="/",
                is_multi_stage=False,
            )

        # Extension-based fallback.
        stack = self._detect_by_extensions(project_path)
        if stack is not None:
            return stack

        # Nothing matched - return a generic "unknown" stack.
        return _empty_static_stack()

    # ------------------------------------------------------------------
    # Language-specific detectors
    # ------------------------------------------------------------------

    def _detect_python(self, path: str) -> Optional[TechStack]:
        """Detect Python projects (Flask / Django / FastAPI / generic)."""
        requirements = os.path.join(path, "requirements.txt")
        pyproject = os.path.join(path, "pyproject.toml")
        pipfile = os.path.join(path, "Pipfile")
        setup_py = os.path.join(path, "setup.py")

        if not any(
            os.path.isfile(p)
            for p in (requirements, pyproject, pipfile, setup_py)
        ):
            return None

        # Combine text from every existing manifest so we can detect
        # frameworks mentioned anywhere (poetry/pyproject/requirements).
        manifest_text = ""
        for fname in (pyproject, requirements, pipfile, setup_py):
            if not os.path.isfile(fname):
                continue
            try:
                with open(fname, "r", encoding="utf-8", errors="ignore") as fh:
                    manifest_text += fh.read() + "\n"
            except OSError:
                continue

        if _manifest_contains(manifest_text, "django"):
            framework = "django"
        elif _manifest_contains(manifest_text, "flask"):
            framework = "flask"
        elif _manifest_contains(manifest_text, "fastapi"):
            framework = "fastapi"
        else:
            framework = "unknown"

        if framework == "flask":
            entry_point = self._find_entry_point(path, "flask")
            command = "gunicorn -b 0.0.0.0:5000 app:app"
        elif framework == "fastapi":
            entry_point = self._find_entry_point(path, "fastapi")
            command = "uvicorn main:app --host 0.0.0.0 --port 8000"
        elif framework == "django":
            entry_point = self._find_entry_point(path, "django")
            command = "gunicorn myproject.wsgi:application -b 0.0.0.0:8000"
        else:
            entry_point = self._find_entry_point(path, "python")
            command = (
                f"python {entry_point}" if entry_point else "python app.py"
            )

        ports = self._infer_ports(path, framework, "python") or [8000]

        return TechStack(
            language="python",
            framework=framework,
            runtime_version="3.12",
            entry_point=entry_point,
            command=command,
            ports=ports,
            package_manager="pip",
            base_image="python:3.12-slim",
            package_install_cmd="pip install --no-cache-dir -r requirements.txt",
            healthcheck_path="/health",
            is_multi_stage=True,
        )

    def _detect_node(self, path: str) -> Optional[TechStack]:
        """Detect Node.js projects (Express / Next / Nuxt / NestJS / generic)."""
        package_json = os.path.join(path, "package.json")
        if not os.path.isfile(package_json):
            return None

        try:
            with open(package_json, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return None

        if not isinstance(data, dict):
            return None

        deps = data.get("dependencies") or {}
        if not isinstance(deps, dict):
            deps = {}

        has_index_html = os.path.isfile(os.path.join(path, "index.html"))

        # No dependencies declared and a static index.html → static site.
        if not deps and has_index_html:
            return TechStack(
                language="html",
                framework="static",
                runtime_version="",
                entry_point="index.html",
                command="nginx -g 'daemon off;'",
                ports=[80],
                package_manager="",
                base_image="nginx:alpine",
                package_install_cmd="",
                healthcheck_path="/",
                is_multi_stage=False,
            )

        # Identify the framework from declared dependencies.
        if "express" in deps:
            framework = "express"
        elif "next" in deps:
            framework = "next"
        elif "@nuxt/schema" in deps or "nuxt" in deps:
            framework = "nuxt"
        elif "@nestjs/core" in deps:
            framework = "nestjs"
        else:
            framework = "unknown"

        if framework == "express":
            entry_point = self._find_entry_point(path, "express") or "server.js"
            command = f"node {entry_point}"
        elif framework == "next":
            entry_point = "next"
            command = "npm run start"
        elif framework == "nuxt":
            entry_point = ""
            command = "npm run start"
        elif framework == "nestjs":
            entry_point = self._find_entry_point(path, "node") or "main.js"
            command = f"node {entry_point}"
        else:
            entry_point = self._find_entry_point(path, "node")
            command = (
                f"node {entry_point}"
                if entry_point
                else "npm run start"
            )

        ports = self._infer_ports(path, framework, "node") or [3000]

        return TechStack(
            language="node",
            framework=framework,
            runtime_version="20",
            entry_point=entry_point,
            command=command,
            ports=ports,
            package_manager="npm",
            base_image="node:20-alpine",
            package_install_cmd="npm ci",
            healthcheck_path="/health",
            is_multi_stage=True,
        )

    def _detect_rust(self, path: str) -> Optional[TechStack]:
        """Detect Rust projects via ``Cargo.toml``."""
        cargo_toml = os.path.join(path, "Cargo.toml")
        if not os.path.isfile(cargo_toml):
            return None

        binary_name = "app"
        try:
            with open(cargo_toml, "r", encoding="utf-8") as fh:
                content = fh.read()
            match = re.search(
                r'^\s*name\s*=\s*"([^"]+)"',
                content,
                re.MULTILINE,
            )
            if match:
                binary_name = match.group(1).strip()
        except OSError:
            pass

        ports = self._infer_ports(path, "unknown", "rust") or [8080]

        return TechStack(
            language="rust",
            framework="unknown",
            runtime_version="1.75",
            entry_point=binary_name,
            command=f"./target/release/{binary_name}",
            ports=ports,
            package_manager="cargo",
            base_image="rust:1.75-slim",
            package_install_cmd="cargo build --release",
            healthcheck_path="/health",
            is_multi_stage=True,
        )

    def _detect_go(self, path: str) -> Optional[TechStack]:
        """Detect Go projects via ``go.mod``."""
        go_mod = os.path.join(path, "go.mod")
        if not os.path.isfile(go_mod):
            return None

        entry_point = self._find_entry_point(path, "go") or "main.go"
        ports = self._infer_ports(path, "unknown", "go") or [8080]

        return TechStack(
            language="go",
            framework="unknown",
            runtime_version="1.22",
            entry_point=entry_point,
            command="./app",
            ports=ports,
            package_manager="go",
            base_image="golang:1.22-alpine",
            package_install_cmd="go build -o app .",
            healthcheck_path="/health",
            is_multi_stage=True,
        )

    def _detect_java(self, path: str) -> Optional[TechStack]:
        """Detect Java projects via ``pom.xml`` (Maven) or ``build.gradle`` (Gradle)."""
        pom = os.path.join(path, "pom.xml")
        gradle = os.path.join(path, "build.gradle")
        gradle_kts = os.path.join(path, "build.gradle.kts")

        if not any(
            os.path.isfile(p) for p in (pom, gradle, gradle_kts)
        ):
            return None

        is_maven = os.path.isfile(pom)
        framework = "maven" if is_maven else "gradle"
        build_cmd = "mvn package" if is_maven else "gradle build"

        ports = self._infer_ports(path, framework, "java") or [8080]

        return TechStack(
            language="java",
            framework=framework,
            runtime_version="21",
            entry_point="app.jar",
            command="java -jar app.jar",
            ports=ports,
            package_manager=framework,
            base_image="eclipse-temurin:21-jre",
            package_install_cmd=build_cmd,
            healthcheck_path="/health",
            is_multi_stage=True,
        )

    def _detect_php(self, path: str) -> Optional[TechStack]:
        """Detect PHP projects via ``composer.json``."""
        composer = os.path.join(path, "composer.json")
        if not os.path.isfile(composer):
            return None

        framework = "unknown"
        try:
            with open(composer, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            data = None

        if isinstance(data, dict):
            require = data.get("require") or {}
            if isinstance(require, dict) and "laravel/framework" in require:
                framework = "laravel"

        if framework == "laravel":
            base_image = "php:8.3-fpm"
            command = "php-fpm"
            default_ports = [9000]
        else:
            base_image = "php:8.3-apache"
            command = "apache2-foreground"
            default_ports = [8000]

        ports = self._infer_ports(path, framework, "php") or default_ports

        return TechStack(
            language="php",
            framework=framework,
            runtime_version="8.3",
            entry_point="index.php",
            command=command,
            ports=ports,
            package_manager="composer",
            base_image=base_image,
            package_install_cmd="composer install --no-dev --optimize-autoloader",
            healthcheck_path="/",
            is_multi_stage=True,
        )

    def _detect_ruby(self, path: str) -> Optional[TechStack]:
        """Detect Ruby projects via ``Gemfile``."""
        gemfile = os.path.join(path, "Gemfile")
        if not os.path.isfile(gemfile):
            return None

        framework = "unknown"
        try:
            with open(gemfile, "r", encoding="utf-8") as fh:
                content = fh.read()
            if _manifest_contains(content, "rails"):
                framework = "rails"
        except OSError:
            pass

        if framework == "rails":
            command = "bundle exec rails server -b 0.0.0.0"
        else:
            command = "bundle exec ruby app.rb"

        ports = self._infer_ports(path, framework, "ruby") or [3000]

        return TechStack(
            language="ruby",
            framework=framework,
            runtime_version="3.3",
            entry_point="app.rb",
            command=command,
            ports=ports,
            package_manager="bundler",
            base_image="ruby:3.3-slim",
            package_install_cmd="bundle install",
            healthcheck_path="/health",
            is_multi_stage=True,
        )

    def _detect_dotnet(self, path: str) -> Optional[TechStack]:
        """Detect .NET projects via ``*.csproj`` or ``*.sln`` files."""
        try:
            entries = os.listdir(path)
        except OSError:
            return None

        if not any(
            f.endswith(".csproj") or f.endswith(".sln") for f in entries
        ):
            return None

        ports = self._infer_ports(path, "unknown", "dotnet") or [5000]

        return TechStack(
            language="dotnet",
            framework="unknown",
            runtime_version="8.0",
            entry_point="app.dll",
            command="dotnet app.dll",
            ports=ports,
            package_manager="dotnet",
            base_image="mcr.microsoft.com/dotnet/aspnet:8.0",
            package_install_cmd="dotnet publish -c Release",
            healthcheck_path="/health",
            is_multi_stage=True,
        )

    def _detect_elixir(self, path: str) -> Optional[TechStack]:
        """Detect Elixir projects via ``mix.exs``."""
        mix_exs = os.path.join(path, "mix.exs")
        if not os.path.isfile(mix_exs):
            return None

        framework = "unknown"
        try:
            with open(mix_exs, "r", encoding="utf-8") as fh:
                content = fh.read()
            if _manifest_contains(content, "phoenix"):
                framework = "phoenix"
        except OSError:
            pass

        if framework == "phoenix":
            command = "mix phx.server"
        else:
            command = "mix run --no-halt"

        ports = self._infer_ports(path, framework, "elixir") or [4000]

        return TechStack(
            language="elixir",
            framework=framework,
            runtime_version="1.16",
            entry_point="lib",
            command=command,
            ports=ports,
            package_manager="mix",
            base_image="elixir:1.16-slim",
            package_install_cmd="mix deps.get && mix compile",
            healthcheck_path="/health",
            is_multi_stage=True,
        )

    def _detect_by_extensions(self, path: str) -> Optional[TechStack]:
        """Fallback: count file extensions and pick the most common language.

        Returns ``None`` when no recognised extensions are present.
        """
        counts: dict = {}
        try:
            for root, dirs, files in os.walk(path):
                # Prune ignored directories in-place so os.walk skips them.
                dirs[:] = [
                    d
                    for d in dirs
                    if d not in self.SKIP_DIRS and not d.startswith(".")
                ]
                for fname in files:
                    ext = os.path.splitext(fname)[1].lower()
                    language = self.EXTENSION_LANGUAGE_MAP.get(ext)
                    if language:
                        counts[language] = counts.get(language, 0) + 1
        except OSError:
            pass

        if not counts:
            return None

        language = max(counts, key=counts.get)
        ports = self._infer_ports(path, "unknown", language) or [8080]

        return TechStack(
            language=language,
            framework="unknown",
            runtime_version="",
            entry_point="",
            command="",
            ports=ports,
            package_manager="",
            base_image="",
            package_install_cmd="",
            healthcheck_path="/",
            is_multi_stage=False,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_entry_point(self, path: str, framework: str) -> str:
        """Find the main entry file for *framework* in *path*."""
        if framework == "fastapi":
            # FastAPI entry point is conventionally ``main.py``.
            return "main.py"

        if framework == "django":
            return "manage.py"

        if framework in ("flask", "python"):
            for candidate in self.PYTHON_ENTRY_CANDIDATES:
                if os.path.isfile(os.path.join(path, candidate)):
                    return candidate
            return "app.py"

        if framework in ("express", "nestjs", "node"):
            for candidate in self.NODE_ENTRY_CANDIDATES:
                if os.path.isfile(os.path.join(path, candidate)):
                    return candidate
            # Fall back to the ``main`` field in package.json.
            package_json = os.path.join(path, "package.json")
            if os.path.isfile(package_json):
                try:
                    with open(package_json, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    if isinstance(data, dict):
                        main = data.get("main")
                        if isinstance(main, str) and main:
                            return main
                except (OSError, json.JSONDecodeError):
                    pass
            return "server.js"

        if framework == "rust":
            cargo_toml = os.path.join(path, "Cargo.toml")
            if os.path.isfile(cargo_toml):
                try:
                    with open(cargo_toml, "r", encoding="utf-8") as fh:
                        content = fh.read()
                    match = re.search(
                        r'^\s*name\s*=\s*"([^"]+)"',
                        content,
                        re.MULTILINE,
                    )
                    if match:
                        return match.group(1).strip()
                except OSError:
                    pass
            return "app"

        if framework == "go":
            for candidate in ("main.go", os.path.join("cmd", "main.go")):
                if os.path.isfile(os.path.join(path, candidate)):
                    return candidate
            go_mod = os.path.join(path, "go.mod")
            if os.path.isfile(go_mod):
                try:
                    with open(go_mod, "r", encoding="utf-8") as fh:
                        first_line = fh.readline().strip()
                    if first_line.startswith("module "):
                        return first_line.split(maxsplit=1)[1]
                except OSError:
                    pass
            return "main.go"

        return ""

    def _infer_ports(
        self, path: str, framework: str, language: str
    ) -> List[int]:
        """Infer the service ports.

        Checks the following sources, in order:

        1. ``docker-compose.yml`` / ``docker-compose.yaml`` port mappings
        2. ``Dockerfile`` ``EXPOSE`` directives or ``ENV PORT``
        3. ``package.json`` scripts (only when language is ``node``)
        4. Framework/language defaults
        """
        # 1. docker-compose files.
        for fname in ("docker-compose.yml", "docker-compose.yaml"):
            compose_path = os.path.join(path, fname)
            if not os.path.isfile(compose_path):
                continue
            try:
                with open(compose_path, "r", encoding="utf-8") as fh:
                    content = fh.read()
            except OSError:
                continue
            ports: List[int] = []
            for match in re.finditer(
                r'["\']?(\d{2,5}):(\d{2,5})["\']?', content
            ):
                try:
                    host = int(match.group(1))
                except ValueError:
                    continue
                if 1 <= host <= 65535:
                    ports.append(host)
            if ports:
                # Preserve order, drop duplicates.
                seen = set()
                deduped: List[int] = []
                for port in ports:
                    if port not in seen:
                        seen.add(port)
                        deduped.append(port)
                return deduped

        # 2. Dockerfile EXPOSE / ENV PORT.
        dockerfile = os.path.join(path, "Dockerfile")
        if os.path.isfile(dockerfile):
            try:
                with open(dockerfile, "r", encoding="utf-8") as fh:
                    content = fh.read()
            except OSError:
                content = ""

            if content:
                expose_ports: List[int] = []
                for match in re.finditer(
                    r"^\s*EXPOSE\s+(.+)$",
                    content,
                    re.MULTILINE | re.IGNORECASE,
                ):
                    for token in match.group(1).split():
                        try:
                            port = int(token)
                        except ValueError:
                            continue
                        if 1 <= port <= 65535:
                            expose_ports.append(port)
                if expose_ports:
                    return expose_ports

                env_match = re.search(
                    r"^\s*ENV\s+PORT[=\s]+(\d+)",
                    content,
                    re.MULTILINE | re.IGNORECASE,
                )
                if env_match:
                    try:
                        port = int(env_match.group(1))
                    except ValueError:
                        port = 0
                    if 1 <= port <= 65535:
                        return [port]

        # 3. package.json scripts (node only).
        if language == "node":
            package_json = os.path.join(path, "package.json")
            if os.path.isfile(package_json):
                try:
                    with open(package_json, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                except (OSError, json.JSONDecodeError):
                    data = None
                if isinstance(data, dict):
                    scripts = data.get("scripts") or {}
                    if isinstance(scripts, dict):
                        for script_value in scripts.values():
                            if not isinstance(script_value, str):
                                continue
                            for match in re.finditer(
                                r"(?:^|[\s:=])(\d{4,5})(?:[\s;\"']|$)",
                                script_value,
                            ):
                                try:
                                    port = int(match.group(1))
                                except ValueError:
                                    continue
                                if 1 <= port <= 65535:
                                    return [port]

        # 4. Framework defaults.
        return list(self._PORT_DEFAULTS.get((framework, language), [8080]))
