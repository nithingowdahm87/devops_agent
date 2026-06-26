"""Universal artifact generator.

Programmatically generates Dockerfiles, GitHub Actions CI workflows,
Kubernetes manifests, and docker-compose files from a
:class:`src.engine.language_detector.TechStack` instance.

The generator deliberately avoids hardcoded multi-line string templates.
Dockerfile instructions are accumulated as Python lists and joined, while
YAML artifacts (CI workflows, K8s manifests, docker-compose) are built as
plain Python dictionaries and serialized with :func:`yaml.safe_dump`.

Public API:
    * :meth:`ArtifactGenerator.generate_dockerfile`
    * :meth:`ArtifactGenerator.generate_ci`
    * :meth:`ArtifactGenerator.generate_k8s_manifests`
    * :meth:`ArtifactGenerator.generate_docker_compose`
"""

from __future__ import annotations

import json
import re
import shlex
from typing import Any, Callable, Dict, List, Tuple

import yaml

from src.engine.language_detector import TechStack


# Image registry placeholder used by K8s manifests. OWNER/REPO are
# intentional tokens so downstream tooling can post-process them.
_IMAGE_PLACEHOLDER = "ghcr.io/OWNER/REPO"

# Sensible default runtime versions when the TechStack did not specify one.
_DEFAULT_RUNTIME_VERSION: Dict[str, str] = {
    "python": "3.12",
    "node": "20",
    "rust": "1.75",
    "go": "1.22",
    "java": "21",
    "php": "8.3",
    "ruby": "3.3",
    "dotnet": "8.0",
    "elixir": "1.16",
    "html": "alpine",
}


class ArtifactGenerator:
    """Generate infrastructure artifacts from a detected TechStack."""

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def generate_dockerfile(self, stack: TechStack, service_name: str = "app") -> str:
        """Return a Dockerfile string tailored to the stack's language."""
        language = (stack.language or "").lower()
        dispatcher: Dict[str, Callable[[TechStack, str], str]] = {
            "python": self._dockerfile_python,
            "node": self._dockerfile_node,
            "rust": self._dockerfile_rust,
            "go": self._dockerfile_go,
            "java": self._dockerfile_java,
            "php": self._dockerfile_php,
            "ruby": self._dockerfile_ruby,
            "dotnet": self._dockerfile_dotnet,
            "elixir": self._dockerfile_elixir,
            "html": self._dockerfile_static,
        }
        handler = dispatcher.get(language, self._dockerfile_generic)
        return handler(stack, service_name)

    def generate_ci(self, stack: TechStack, service_name: str = "app") -> str:
        """Return a GitHub Actions workflow YAML string for the stack."""
        language = (stack.language or "").lower()
        dispatcher: Dict[str, Callable[[TechStack, str], Dict[str, Any]]] = {
            "python": self._ci_python,
            "node": self._ci_node,
            "rust": self._ci_rust,
            "go": self._ci_go,
            "java": self._ci_java,
            "php": self._ci_php,
            "ruby": self._ci_ruby,
            "dotnet": self._ci_dotnet,
            "elixir": self._ci_elixir,
            "html": self._ci_static,
        }
        handler = dispatcher.get(language, self._ci_generic)
        workflow = handler(stack, service_name)
        return yaml.safe_dump(workflow, default_flow_style=False, sort_keys=False)

    def generate_k8s_manifests(
        self,
        stack: TechStack,
        service_name: str = "app",
        namespace: str = "default",
    ) -> Dict[str, str]:
        """Return K8s manifests as ``{filename: yaml_content}``."""
        labels = self._labels(service_name)
        port = self._primary_port(stack)
        image = self._image_ref(service_name)

        builders: List[Tuple[str, Dict[str, Any]]] = [
            ("namespace.yaml", self._k8s_namespace(service_name, namespace)),
            ("configmap.yaml", self._k8s_configmap(service_name, namespace, labels)),
            ("secret.yaml", self._k8s_secret(service_name, namespace, labels)),
            (
                "deployment.yaml",
                self._k8s_deployment(stack, service_name, namespace, labels, port, image),
            ),
            ("service.yaml", self._k8s_service(service_name, namespace, labels, port)),
            ("ingress.yaml", self._k8s_ingress(service_name, namespace, labels, port)),
            ("hpa.yaml", self._k8s_hpa(service_name, namespace, labels)),
            ("pdb.yaml", self._k8s_pdb(service_name, namespace, labels)),
            (
                "networkpolicy.yaml",
                self._k8s_networkpolicy(service_name, namespace, labels, port),
            ),
        ]
        return {
            filename: yaml.safe_dump(body, default_flow_style=False, sort_keys=False)
            for filename, body in builders
        }

    def generate_docker_compose(
        self,
        stacks: List[TechStack],
        project_name: str = "app",
    ) -> str:
        """Return a docker-compose.yml string covering every supplied stack."""
        if not stacks:
            stacks = [TechStack()]

        services: Dict[str, Any] = {}
        names: List[str] = []
        for idx, stack in enumerate(stacks):
            svc_name = f"svc{idx}"
            names.append(svc_name)
            services[svc_name] = self._compose_service(stack, svc_name)

        # Chain each service onto the previous one for a soft startup order.
        for idx in range(1, len(names)):
            services[names[idx]]["depends_on"] = [names[idx - 1]]

        compose: Dict[str, Any] = {
            "version": "3.9",
            "name": project_name,
            "services": services,
        }
        return yaml.safe_dump(compose, default_flow_style=False, sort_keys=False)

    # ================================================================== #
    # Dockerfile builders (one per language family)
    # ================================================================== #

    def _dockerfile_python(self, stack: TechStack, service_name: str) -> str:
        port = self._primary_port(stack)
        requirements = self._python_requirements_files(stack)
        install_cmd = stack.package_install_cmd or "pip install --no-cache-dir -r requirements.txt"
        run_user = stack.run_user or "appuser"
        sections: List[str] = []

        builder: List[str] = [f"FROM {stack.base_image} AS builder"]
        builder += [
            "ENV PIP_NO_CACHE_DIR=1 \\",
            "    PIP_DISABLE_PIP_VERSION_CHECK=1 \\",
            "    PYTHONDONTWRITEBYTECODE=1",
            "WORKDIR /build",
        ]
        for req in requirements:
            builder.append(f"COPY {req} ./")
        builder.append(f"RUN {install_cmd} --prefix=/install")
        sections.append(self._join_lines(builder))

        runtime: List[str] = [f"FROM {stack.base_image} AS runtime"]
        runtime.append(self._create_user_block(run_user, stack.base_image))
        runtime += [
            "ENV PYTHONUNBUFFERED=1 \\",
            "    PYTHONDONTWRITEBYTECODE=1",
            "WORKDIR /app",
            "COPY --from=builder /install /usr/local",
            "COPY . /app/",
            f"EXPOSE {port}",
        ]
        runtime.append(self._python_healthcheck(port, stack.healthcheck_path))
        runtime.append(self._cmd_exec(self._cmd_for(stack)))
        sections.append(self._join_lines(runtime))

        return "\n".join(sections)

    def _dockerfile_node(self, stack: TechStack, service_name: str) -> str:
        port = self._primary_port(stack)
        framework = (stack.framework or "").lower()
        install_cmd = stack.package_install_cmd or "npm ci"
        run_user = stack.run_user or "appuser"
        needs_build = framework in ("nextjs", "nuxt")
        sections: List[str] = []

        deps: List[str] = [f"FROM {stack.base_image} AS deps"]
        deps += [
            "WORKDIR /app",
            "COPY package*.json ./",
            f"RUN {install_cmd}",
        ]
        sections.append(self._join_lines(deps))

        if needs_build:
            build: List[str] = ["FROM deps AS build", "COPY . .", "RUN npm run build"]
            sections.append(self._join_lines(build))

        runtime: List[str] = [f"FROM {stack.base_image} AS runtime"]
        runtime.append(self._install_packages(stack.base_image, ["tini", "wget"]))
        runtime.append(self._create_user_block(run_user, stack.base_image))
        runtime += [
            "ENV NODE_ENV=production",
            "WORKDIR /app",
            "COPY --from=deps /app/node_modules ./node_modules",
        ]
        if needs_build:
            runtime.append("COPY --from=build /app/.next ./.next")
            runtime.append("COPY --from=build /app/public ./public")
        runtime += [
            "COPY package*.json ./",
            "COPY . .",
            f"EXPOSE {port}",
        ]
        runtime.append(self._wget_healthcheck(port, stack.healthcheck_path))
        runtime.append(self._node_entrypoint(stack.command))
        sections.append(self._join_lines(runtime))

        return "\n".join(sections)

    def _dockerfile_rust(self, stack: TechStack, service_name: str) -> str:
        port = self._primary_port(stack)
        binary = service_name or "app"
        run_user = stack.run_user or "appuser"
        install_cmd = stack.package_install_cmd or "cargo build --release"
        sections: List[str] = []

        builder: List[str] = [f"FROM {stack.base_image} AS builder"]
        builder += [
            "RUN apt-get update && apt-get install -y --no-install-recommends \\",
            "        pkg-config libssl-dev ca-certificates \\",
            "    && rm -rf /var/lib/apt/lists/*",
            "WORKDIR /build",
            "COPY Cargo.toml Cargo.lock ./",
            "RUN mkdir -p src && echo 'fn main(){}' > src/main.rs \\",
            f"    && {install_cmd} \\",
            "    && rm -rf src",
            "COPY src ./src",
            "RUN touch src/main.rs && " + install_cmd,
        ]
        sections.append(self._join_lines(builder))

        runtime_base = self._runtime_image_for("rust")
        runtime: List[str] = [f"FROM {runtime_base} AS runtime"]
        runtime.append(self._install_packages(runtime_base, ["wget", "ca-certificates"]))
        runtime.append(self._create_user_block(run_user, runtime_base))
        runtime += [
            "WORKDIR /app",
            f"COPY --from=builder /build/target/release/{binary} /usr/local/bin/{binary}",
            f"EXPOSE {port}",
        ]
        runtime.append(self._wget_healthcheck(port, stack.healthcheck_path))
        runtime.append(self._cmd_exec(self._cmd_for(stack)))
        sections.append(self._join_lines(runtime))

        return "\n".join(sections)

    def _dockerfile_go(self, stack: TechStack, service_name: str) -> str:
        port = self._primary_port(stack)
        binary = service_name or "app"
        run_user = stack.run_user or "appuser"
        install_cmd = stack.package_install_cmd or "go mod download"
        sections: List[str] = []

        builder: List[str] = [f"FROM {stack.base_image} AS builder"]
        builder += [
            "WORKDIR /build",
            "COPY go.mod go.sum* ./",
            f"RUN {install_cmd}",
            "COPY . .",
            f"RUN CGO_ENABLED=0 GOOS=linux go build -ldflags=\"-s -w\" -o /out/{binary} .",
        ]
        sections.append(self._join_lines(builder))

        runtime_base = self._runtime_image_for("go")
        runtime: List[str] = [f"FROM {runtime_base} AS runtime"]
        if "distroless" in runtime_base:
            runtime += [
                f"COPY --from=builder /out/{binary} /usr/local/bin/{binary}",
                "USER nonroot",
            ]
        else:
            runtime.append(self._install_packages(runtime_base, ["wget", "ca-certificates"]))
            runtime.append(self._create_user_block(run_user, runtime_base))
            runtime.append(f"COPY --from=builder /out/{binary} /usr/local/bin/{binary}")
            runtime.append(f"USER {run_user}")
        runtime += [
            f"EXPOSE {port}",
        ]
        runtime.append(self._wget_healthcheck(port, stack.healthcheck_path))
        runtime.append(self._cmd_exec(self._cmd_for(stack)))
        sections.append(self._join_lines(runtime))

        return "\n".join(sections)

    def _dockerfile_java(self, stack: TechStack, service_name: str) -> str:
        port = self._primary_port(stack)
        run_user = stack.run_user or "appuser"
        pm = (stack.package_manager or "maven").lower()
        runtime_base = self._java_runtime_image(stack.base_image)

        if pm == "gradle":
            builder_files = [
                "settings.gradle*",
                "build.gradle*",
                "gradle/",
                "gradlew",
                "gradlew.bat",
            ]
            offline_cmd = "./gradlew dependencies --no-daemon"
            build_cmd = "./gradlew bootJar -x test --no-daemon"
            artifact_glob = "build/libs/*.jar"
        else:
            builder_files = ["pom.xml"]
            offline_cmd = "mvn -B -q dependency:go-offline"
            build_cmd = "mvn -B -q package -DskipTests"
            artifact_glob = "target/*.jar"

        sections: List[str] = []

        builder: List[str] = [f"FROM {stack.base_image} AS builder"]
        builder += ["WORKDIR /build"]
        for f in builder_files:
            builder.append(f"COPY {f} ./")
        builder += [f"RUN {offline_cmd}", "COPY . .", f"RUN {build_cmd}"]
        sections.append(self._join_lines(builder))

        runtime: List[str] = [f"FROM {runtime_base} AS runtime"]
        runtime.append(self._install_packages(runtime_base, ["wget"]))
        runtime.append(self._create_user_block(run_user, runtime_base))
        runtime += [
            "WORKDIR /app",
            f"COPY --from=builder /build/{artifact_glob} app.jar",
            f"EXPOSE {port}",
        ]
        runtime.append(self._wget_healthcheck(port, stack.healthcheck_path))
        runtime.append(self._cmd_exec(self._cmd_for(stack)))
        sections.append(self._join_lines(runtime))

        return "\n".join(sections)

    def _dockerfile_php(self, stack: TechStack, service_name: str) -> str:
        port = self._primary_port(stack)
        run_user = stack.run_user or "appuser"
        install_cmd = (
            stack.package_install_cmd
            or "composer install --no-dev --optimize-autoloader --no-scripts"
        )
        sections: List[str] = []

        builder: List[str] = ["FROM composer:2 AS builder"]
        builder += [
            "WORKDIR /app",
            "COPY composer.json composer.lock* ./",
            f"RUN {install_cmd}",
            "COPY . .",
            "RUN composer dump-autoload --optimize --no-scripts --classmap-authoritative || true",
        ]
        sections.append(self._join_lines(builder))

        runtime: List[str] = [f"FROM {stack.base_image} AS runtime"]
        if "apache" in stack.base_image:
            runtime.append(self._install_packages(stack.base_image, ["libpq-dev", "git"]))
        runtime.append(self._create_user_block(run_user, stack.base_image))
        runtime += [
            "WORKDIR /var/www/html",
            "COPY --from=builder /app/vendor ./vendor",
            "COPY . .",
        ]
        if "apache" in stack.base_image:
            runtime.append("RUN chown -R www-data:www-data /var/www/html")
        runtime += [f"EXPOSE {port}"]
        runtime.append(self._wget_healthcheck(port, stack.healthcheck_path))
        runtime.append(self._cmd_exec(self._cmd_for(stack)))
        sections.append(self._join_lines(runtime))

        return "\n".join(sections)

    def _dockerfile_ruby(self, stack: TechStack, service_name: str) -> str:
        port = self._primary_port(stack)
        run_user = stack.run_user or "appuser"
        install_cmd = (
            stack.package_install_cmd
            or "bundle config set --local without 'development test' && bundle install --jobs 4 --retry 3"
        )
        sections: List[str] = []

        builder: List[str] = [f"FROM {stack.base_image} AS builder"]
        builder += [
            "WORKDIR /build",
            "RUN apt-get update && apt-get install -y --no-install-recommends \\",
            "        build-essential libffi-dev libyaml-dev \\",
            "    && rm -rf /var/lib/apt/lists/*",
            "COPY Gemfile Gemfile.lock* ./",
            f"RUN {install_cmd}",
            "COPY . .",
        ]
        sections.append(self._join_lines(builder))

        runtime: List[str] = [f"FROM {stack.base_image} AS runtime"]
        runtime.append(
            self._install_packages(stack.base_image, ["wget", "libffi8", "libyaml-0-2"])
        )
        runtime.append(self._create_user_block(run_user, stack.base_image))
        runtime += [
            "WORKDIR /app",
            "COPY --from=builder /build /app",
            "COPY --from=builder /usr/local/bundle /usr/local/bundle",
            "ENV GEM_HOME=/usr/local/bundle \\",
            "    BUNDLE_PATH=/usr/local/bundle",
            f"EXPOSE {port}",
        ]
        runtime.append(self._wget_healthcheck(port, stack.healthcheck_path))
        runtime.append(self._cmd_exec(self._cmd_for(stack)))
        sections.append(self._join_lines(runtime))

        return "\n".join(sections)

    def _dockerfile_dotnet(self, stack: TechStack, service_name: str) -> str:
        port = self._primary_port(stack)
        run_user = stack.run_user or "appuser"
        runtime_base = self._dotnet_runtime_image(stack.base_image)
        sections: List[str] = []

        builder: List[str] = [f"FROM {stack.base_image} AS builder"]
        builder += [
            "WORKDIR /src",
            "COPY . .",
            "RUN dotnet restore && dotnet publish -c Release -o /app /p:UseAppHost=false",
        ]
        sections.append(self._join_lines(builder))

        runtime: List[str] = [f"FROM {runtime_base} AS runtime"]
        runtime.append(self._create_user_block(run_user, runtime_base))
        runtime += [
            "WORKDIR /app",
            "COPY --from=builder /app ./",
            f"EXPOSE {port}",
        ]
        runtime.append(self._wget_healthcheck(port, stack.healthcheck_path))
        runtime.append(self._cmd_exec(self._cmd_for(stack)))
        sections.append(self._join_lines(runtime))

        return "\n".join(sections)

    def _dockerfile_elixir(self, stack: TechStack, service_name: str) -> str:
        port = self._primary_port(stack)
        run_user = stack.run_user or "appuser"
        install_cmd = (
            stack.package_install_cmd
            or "mix local.hex --force && mix local.rebar --force && mix deps.get"
        )
        sections: List[str] = []

        builder: List[str] = [f"FROM {stack.base_image} AS builder"]
        builder += [
            "WORKDIR /build",
            "ENV MIX_ENV=prod",
            "COPY mix.exs mix.lock* ./",
            "COPY config ./config",
            f"RUN {install_cmd}",
            "COPY . .",
            "RUN mix release",
        ]
        sections.append(self._join_lines(builder))

        release_dir = f"/build/_build/prod/rel/{service_name}"
        runtime: List[str] = [f"FROM {stack.base_image} AS runtime"]
        runtime.append(self._install_packages(stack.base_image, ["wget"]))
        runtime.append(self._create_user_block(run_user, stack.base_image))
        runtime += [
            "WORKDIR /app",
            f"COPY --from=builder {release_dir} ./",
            f"EXPOSE {port}",
        ]
        runtime.append(self._wget_healthcheck(port, stack.healthcheck_path))
        runtime.append(self._cmd_exec(self._cmd_for(stack)))
        sections.append(self._join_lines(runtime))

        return "\n".join(sections)

    def _dockerfile_static(self, stack: TechStack, service_name: str) -> str:
        port = self._primary_port(stack)
        lines: List[str] = [f"FROM {stack.base_image} AS runtime"]
        if port and port != 80 and "nginx" in (stack.base_image or "").lower():
            lines.append(
                f"RUN sed -i 's/listen       80;/listen       {port};/' "
                "/etc/nginx/conf.d/default.conf"
            )
        lines += [
            "COPY . /usr/share/nginx/html/",
            f"EXPOSE {port}",
        ]
        lines.append(self._wget_healthcheck(port, stack.healthcheck_path))
        lines.append('CMD ["nginx", "-g", "daemon off;"]')
        return self._join_lines(lines)

    def _dockerfile_generic(self, stack: TechStack, service_name: str) -> str:
        """Single-stage fallback for unknown languages."""
        port = self._primary_port(stack)
        run_user = stack.run_user or "appuser"
        lines: List[str] = [f"FROM {stack.base_image} AS runtime"]
        lines.append(self._create_user_block(run_user, stack.base_image))
        lines += [
            "WORKDIR /app",
        ]
        if stack.package_install_cmd:
            lines.append(f"RUN {stack.package_install_cmd}")
        lines += [
            "COPY . /app/",
            f"EXPOSE {port}",
        ]
        lines.append(self._wget_healthcheck(port, stack.healthcheck_path))
        lines.append(self._cmd_exec(self._cmd_for(stack)))
        return self._join_lines(lines)

    # ================================================================== #
    # CI workflow builders
    # ================================================================== #

    def _ci_python(self, stack: TechStack, service_name: str) -> Dict[str, Any]:
        version = stack.runtime_version or _DEFAULT_RUNTIME_VERSION["python"]
        port = self._primary_port(stack)
        install_cmd = stack.package_install_cmd or "pip install -r requirements.txt"
        return self._ci_workflow(
            service_name,
            [
                ("test", self._steps([
                    {"uses": "actions/checkout@v4"},
                    {"uses": "actions/setup-python@v5",
                     "with": {"python-version": version, "cache": "pip"}},
                    {"run": install_cmd},
                    {"run": "pytest --maxfail=1 --disable-warnings -q"},
                ])),
                ("lint", self._steps([
                    {"uses": "actions/checkout@v4"},
                    {"uses": "hadolint/hadolint-action@v3.1.0",
                     "with": {"dockerfile": "Dockerfile"}},
                ])),
                ("build-smoke", self._ci_smoke_steps(service_name, port, stack.healthcheck_path)),
            ],
        )

    def _ci_node(self, stack: TechStack, service_name: str) -> Dict[str, Any]:
        version = stack.runtime_version or _DEFAULT_RUNTIME_VERSION["node"]
        port = self._primary_port(stack)
        framework = (stack.framework or "").lower()
        install_cmd = stack.package_install_cmd or "npm ci"
        if framework == "nextjs":
            lint_cmd = "npx --yes next lint || true"
        else:
            lint_cmd = "npx --yes eslint . --ext .js,.jsx,.ts,.tsx --max-warnings=0 || true"
        return self._ci_workflow(
            service_name,
            [
                ("test", self._steps([
                    {"uses": "actions/checkout@v4"},
                    {"uses": "actions/setup-node@v4",
                     "with": {"node-version": version, "cache": "npm"}},
                    {"run": install_cmd},
                    {"run": lint_cmd},
                    {"run": "npm test -- --watch=false --if-present"},
                ])),
                ("lint", self._steps([
                    {"uses": "actions/checkout@v4"},
                    {"uses": "hadolint/hadolint-action@v3.1.0",
                     "with": {"dockerfile": "Dockerfile"}},
                ])),
                ("build-smoke", self._ci_smoke_steps(service_name, port, stack.healthcheck_path)),
            ],
        )

    def _ci_rust(self, stack: TechStack, service_name: str) -> Dict[str, Any]:
        version = stack.runtime_version or _DEFAULT_RUNTIME_VERSION["rust"]
        port = self._primary_port(stack)
        return self._ci_workflow(
            service_name,
            [
                ("test", self._steps([
                    {"uses": "actions/checkout@v4"},
                    {"uses": "dtolnay/rust-toolchain@stable",
                     "with": {"toolchain": version, "components": "rustfmt, clippy"}},
                    {"uses": "Swatinem/rust-cache@v2",
                     "with": {"shared-key": service_name}},
                    {"run": "cargo fmt --all -- --check || true"},
                    {"run": "cargo clippy --all-targets -- -D warnings || true"},
                    {"run": "cargo test --all"},
                    {"run": "cargo build --release"},
                ])),
                ("lint", self._steps([
                    {"uses": "actions/checkout@v4"},
                    {"uses": "hadolint/hadolint-action@v3.1.0",
                     "with": {"dockerfile": "Dockerfile"}},
                ])),
                ("build-smoke", self._ci_smoke_steps(service_name, port, stack.healthcheck_path)),
            ],
        )

    def _ci_go(self, stack: TechStack, service_name: str) -> Dict[str, Any]:
        version = stack.runtime_version or _DEFAULT_RUNTIME_VERSION["go"]
        port = self._primary_port(stack)
        return self._ci_workflow(
            service_name,
            [
                ("test", self._steps([
                    {"uses": "actions/checkout@v4"},
                    {"uses": "actions/setup-go@v5",
                     "with": {"go-version": version, "cache": True}},
                    {"run": "go vet ./..."},
                    {"run": "go test ./..."},
                    {"run": "go build ./..."},
                ])),
                ("lint", self._steps([
                    {"uses": "actions/checkout@v4"},
                    {"uses": "hadolint/hadolint-action@v3.1.0",
                     "with": {"dockerfile": "Dockerfile"}},
                ])),
                ("build-smoke", self._ci_smoke_steps(service_name, port, stack.healthcheck_path)),
            ],
        )

    def _ci_java(self, stack: TechStack, service_name: str) -> Dict[str, Any]:
        version = stack.runtime_version or _DEFAULT_RUNTIME_VERSION["java"]
        pm = (stack.package_manager or "maven").lower()
        distribution = "temurin"
        if pm == "gradle":
            test_cmd = "./gradlew test --no-daemon"
            build_cmd = "./gradlew bootJar -x test --no-daemon"
        else:
            test_cmd = "mvn -B test"
            build_cmd = "mvn -B package -DskipTests"
        port = self._primary_port(stack)
        return self._ci_workflow(
            service_name,
            [
                ("test", self._steps([
                    {"uses": "actions/checkout@v4"},
                    {"uses": "actions/setup-java@v4",
                     "with": {
                         "distribution": distribution,
                         "java-version": version,
                         "cache": pm,
                     }},
                    {"run": test_cmd},
                    {"run": build_cmd},
                ])),
                ("lint", self._steps([
                    {"uses": "actions/checkout@v4"},
                    {"uses": "hadolint/hadolint-action@v3.1.0",
                     "with": {"dockerfile": "Dockerfile"}},
                ])),
                ("build-smoke", self._ci_smoke_steps(service_name, port, stack.healthcheck_path)),
            ],
        )

    def _ci_php(self, stack: TechStack, service_name: str) -> Dict[str, Any]:
        version = stack.runtime_version or _DEFAULT_RUNTIME_VERSION["php"]
        port = self._primary_port(stack)
        return self._ci_workflow(
            service_name,
            [
                ("test", self._steps([
                    {"uses": "actions/checkout@v4"},
                    {"uses": "shivammathur/setup-php@v2",
                     "with": {"php-version": version, "tools": "composer"}},
                    {"run": "composer install --prefer-dist --no-progress"},
                    {"run": "php artisan test || true"},
                ])),
                ("lint", self._steps([
                    {"uses": "actions/checkout@v4"},
                    {"uses": "hadolint/hadolint-action@v3.1.0",
                     "with": {"dockerfile": "Dockerfile"}},
                ])),
                ("build-smoke", self._ci_smoke_steps(service_name, port, stack.healthcheck_path)),
            ],
        )

    def _ci_ruby(self, stack: TechStack, service_name: str) -> Dict[str, Any]:
        version = stack.runtime_version or _DEFAULT_RUNTIME_VERSION["ruby"]
        port = self._primary_port(stack)
        return self._ci_workflow(
            service_name,
            [
                ("test", self._steps([
                    {"uses": "actions/checkout@v4"},
                    {"uses": "ruby/setup-ruby@v1",
                     "with": {"ruby-version": version, "bundler-cache": True}},
                    {"run": "bundle exec rake test || true"},
                ])),
                ("lint", self._steps([
                    {"uses": "actions/checkout@v4"},
                    {"uses": "hadolint/hadolint-action@v3.1.0",
                     "with": {"dockerfile": "Dockerfile"}},
                ])),
                ("build-smoke", self._ci_smoke_steps(service_name, port, stack.healthcheck_path)),
            ],
        )

    def _ci_dotnet(self, stack: TechStack, service_name: str) -> Dict[str, Any]:
        version = stack.runtime_version or _DEFAULT_RUNTIME_VERSION["dotnet"]
        port = self._primary_port(stack)
        return self._ci_workflow(
            service_name,
            [
                ("test", self._steps([
                    {"uses": "actions/checkout@v4"},
                    {"uses": "actions/setup-dotnet@v4",
                     "with": {"dotnet-version": version}},
                    {"run": "dotnet restore"},
                    {"run": "dotnet test --no-build --verbosity normal"},
                    {"run": "dotnet publish -c Release -o out"},
                ])),
                ("lint", self._steps([
                    {"uses": "actions/checkout@v4"},
                    {"uses": "hadolint/hadolint-action@v3.1.0",
                     "with": {"dockerfile": "Dockerfile"}},
                ])),
                ("build-smoke", self._ci_smoke_steps(service_name, port, stack.healthcheck_path)),
            ],
        )

    def _ci_elixir(self, stack: TechStack, service_name: str) -> Dict[str, Any]:
        version = stack.runtime_version or _DEFAULT_RUNTIME_VERSION["elixir"]
        otp = "26"
        port = self._primary_port(stack)
        return self._ci_workflow(
            service_name,
            [
                ("test", self._steps([
                    {"uses": "actions/checkout@v4"},
                    {"uses": "erlef/setup-beam@v1",
                     "with": {
                         "version-file": ".tool-versions",
                         "version": version,
                         "otp-version": otp,
                     }},
                    {"run": "mix local.hex --force"},
                    {"run": "mix local.rebar --force"},
                    {"run": "mix deps.get"},
                    {"run": "mix test"},
                ])),
                ("lint", self._steps([
                    {"uses": "actions/checkout@v4"},
                    {"uses": "hadolint/hadolint-action@v3.1.0",
                     "with": {"dockerfile": "Dockerfile"}},
                ])),
                ("build-smoke", self._ci_smoke_steps(service_name, port, stack.healthcheck_path)),
            ],
        )

    def _ci_static(self, stack: TechStack, service_name: str) -> Dict[str, Any]:
        port = self._primary_port(stack)
        return self._ci_workflow(
            service_name,
            [
                ("test", self._steps([
                    {"uses": "actions/checkout@v4"},
                    {"run": "echo 'static site — no test step'"},
                ])),
                ("lint", self._steps([
                    {"uses": "actions/checkout@v4"},
                    {"uses": "hadolint/hadolint-action@v3.1.0",
                     "with": {"dockerfile": "Dockerfile"}},
                ])),
                ("build-smoke", self._ci_smoke_steps(service_name, port, stack.healthcheck_path)),
            ],
        )

    def _ci_generic(self, stack: TechStack, service_name: str) -> Dict[str, Any]:
        port = self._primary_port(stack)
        return self._ci_workflow(
            service_name,
            [
                ("test", self._steps([
                    {"uses": "actions/checkout@v4"},
                    {"run": stack.package_install_cmd or "echo 'no install command'"},
                ])),
                ("lint", self._steps([
                    {"uses": "actions/checkout@v4"},
                    {"uses": "hadolint/hadolint-action@v3.1.0",
                     "with": {"dockerfile": "Dockerfile"}},
                ])),
                ("build-smoke", self._ci_smoke_steps(service_name, port, stack.healthcheck_path)),
            ],
        )

    # ================================================================== #
    # Kubernetes manifest builders
    # ================================================================== #

    def _k8s_namespace(self, service_name: str, namespace: str) -> Dict[str, Any]:
        return {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": namespace,
                "labels": {
                    "name": namespace,
                    "managed-by": "artifact-generator",
                },
            },
        }

    def _k8s_configmap(
        self, service_name: str, namespace: str, labels: Dict[str, str]
    ) -> Dict[str, Any]:
        return {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": f"{service_name}-config",
                "namespace": namespace,
                "labels": labels,
            },
            "data": {
                "APP_NAME": service_name,
                "LOG_LEVEL": "info",
                "ENVIRONMENT": namespace,
            },
        }

    def _k8s_secret(
        self, service_name: str, namespace: str, labels: Dict[str, str]
    ) -> Dict[str, Any]:
        return {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": f"{service_name}-secret",
                "namespace": namespace,
                "labels": labels,
            },
            "type": "Opaque",
            "stringData": {
                # Placeholders — replace with real values before applying.
                "API_KEY": "REPLACE_ME",
                "DB_PASSWORD": "REPLACE_ME",
            },
        }

    def _k8s_deployment(
        self,
        stack: TechStack,
        service_name: str,
        namespace: str,
        labels: Dict[str, str],
        port: int,
        image: str,
    ) -> Dict[str, Any]:
        health_path = stack.healthcheck_path or "/health"
        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": service_name,
                "namespace": namespace,
                "labels": labels,
            },
            "spec": {
                "replicas": 3,
                "selector": {"matchLabels": labels},
                "strategy": {
                    "type": "RollingUpdate",
                    "rollingUpdate": {"maxSurge": 1, "maxUnavailable": 0},
                },
                "template": {
                    "metadata": {
                        "labels": labels,
                        "annotations": {
                            "prometheus.io/scrape": "true",
                            "prometheus.io/port": str(port),
                            "prometheus.io/path": "/metrics",
                        },
                    },
                    "spec": {
                        "securityContext": {
                            "runAsNonRoot": True,
                            "runAsUser": 1000,
                            "runAsGroup": 1000,
                            "fsGroup": 1000,
                            "seccompProfile": {"type": "RuntimeDefault"},
                        },
                        "affinity": {
                            "podAntiAffinity": {
                                "preferredDuringSchedulingIgnoredDuringExecution": [
                                    {
                                        "weight": 100,
                                        "podAffinityTerm": {
                                            "topologyKey": "kubernetes.io/hostname",
                                            "labelSelector": {"matchLabels": labels},
                                        },
                                    }
                                ]
                            }
                        },
                        "topologySpreadConstraints": [
                            {
                                "maxSkew": 1,
                                "topologyKey": "topology.kubernetes.io/zone",
                                "whenUnsatisfiable": "ScheduleAnyway",
                                "labelSelector": {"matchLabels": labels},
                            },
                            {
                                "maxSkew": 1,
                                "topologyKey": "kubernetes.io/hostname",
                                "whenUnsatisfiable": "ScheduleAnyway",
                                "labelSelector": {"matchLabels": labels},
                            },
                        ],
                        "containers": [
                            {
                                "name": service_name,
                                "image": image,
                                "imagePullPolicy": "IfNotPresent",
                                "ports": [
                                    {
                                        "containerPort": port,
                                        "name": "http",
                                        "protocol": "TCP",
                                    }
                                ],
                                "envFrom": [
                                    {
                                        "configMapRef": {
                                            "name": f"{service_name}-config"
                                        }
                                    }
                                ],
                                "env": [
                                    {"name": "PORT", "value": str(port)},
                                    {"name": "SERVICE_NAME", "value": service_name},
                                ],
                                "resources": {
                                    "requests": {"cpu": "100m", "memory": "128Mi"},
                                    "limits": {"cpu": "500m", "memory": "512Mi"},
                                },
                                "securityContext": {
                                    "allowPrivilegeEscalation": False,
                                    "readOnlyRootFilesystem": True,
                                    "runAsNonRoot": True,
                                    "runAsUser": 1000,
                                    "capabilities": {"drop": ["ALL"]},
                                },
                                "livenessProbe": {
                                    "httpGet": {"path": health_path, "port": port},
                                    "initialDelaySeconds": 15,
                                    "periodSeconds": 20,
                                    "timeoutSeconds": 5,
                                    "failureThreshold": 3,
                                },
                                "readinessProbe": {
                                    "httpGet": {"path": health_path, "port": port},
                                    "initialDelaySeconds": 5,
                                    "periodSeconds": 10,
                                    "timeoutSeconds": 3,
                                    "failureThreshold": 3,
                                },
                                "volumeMounts": [
                                    {"name": "tmp", "mountPath": "/tmp"},
                                ],
                            }
                        ],
                        "volumes": [
                            {"name": "tmp", "emptyDir": {}},
                        ],
                    },
                },
            },
        }

    def _k8s_service(
        self,
        service_name: str,
        namespace: str,
        labels: Dict[str, str],
        port: int,
    ) -> Dict[str, Any]:
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": service_name,
                "namespace": namespace,
                "labels": labels,
            },
            "spec": {
                "type": "ClusterIP",
                "selector": labels,
                "ports": [
                    {
                        "name": "http",
                        "port": port,
                        "targetPort": port,
                        "protocol": "TCP",
                    }
                ],
            },
        }

    def _k8s_ingress(
        self,
        service_name: str,
        namespace: str,
        labels: Dict[str, str],
        port: int,
    ) -> Dict[str, Any]:
        host = f"{service_name}.example.com"
        return {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {
                "name": service_name,
                "namespace": namespace,
                "labels": labels,
                "annotations": {
                    "nginx.ingress.kubernetes.io/rewrite-target": "/",
                    "nginx.ingress.kubernetes.io/scheme": "internet-facing",
                },
            },
            "spec": {
                "ingressClassName": "nginx",
                "rules": [
                    {
                        "host": host,
                        "http": {
                            "paths": [
                                {
                                    "path": "/",
                                    "pathType": "Prefix",
                                    "backend": {
                                        "service": {
                                            "name": service_name,
                                            "port": {"number": port},
                                        }
                                    },
                                }
                            ]
                        },
                    }
                ],
                "tls": [
                    {
                        "hosts": [host],
                        "secretName": f"{service_name}-tls",
                    }
                ],
            },
        }

    def _k8s_hpa(
        self,
        service_name: str,
        namespace: str,
        labels: Dict[str, str],
    ) -> Dict[str, Any]:
        return {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {
                "name": service_name,
                "namespace": namespace,
                "labels": labels,
            },
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": service_name,
                },
                "minReplicas": 3,
                "maxReplicas": 10,
                "metrics": [
                    {
                        "type": "Resource",
                        "resource": {
                            "name": "cpu",
                            "target": {
                                "type": "Utilization",
                                "averageUtilization": 70,
                            },
                        },
                    },
                    {
                        "type": "Resource",
                        "resource": {
                            "name": "memory",
                            "target": {
                                "type": "Utilization",
                                "averageUtilization": 80,
                            },
                        },
                    },
                ],
            },
        }

    def _k8s_pdb(
        self,
        service_name: str,
        namespace: str,
        labels: Dict[str, str],
    ) -> Dict[str, Any]:
        return {
            "apiVersion": "policy/v1",
            "kind": "PodDisruptionBudget",
            "metadata": {
                "name": service_name,
                "namespace": namespace,
                "labels": labels,
            },
            "spec": {
                "minAvailable": 1,
                "selector": {"matchLabels": labels},
            },
        }

    def _k8s_networkpolicy(
        self,
        service_name: str,
        namespace: str,
        labels: Dict[str, str],
        port: int,
    ) -> Dict[str, Any]:
        return {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {
                "name": service_name,
                "namespace": namespace,
                "labels": labels,
            },
            "spec": {
                "podSelector": {"matchLabels": labels},
                "policyTypes": ["Ingress", "Egress"],
                "ingress": [
                    {
                        "from": [
                            {"podSelector": {}},
                            {"namespaceSelector": {}},
                        ],
                        "ports": [{"protocol": "TCP", "port": port}],
                    }
                ],
                "egress": [
                    {
                        "to": [
                            {
                                "ipBlock": {
                                    "cidr": "0.0.0.0/0",
                                    "except": ["169.254.0.0/16"],
                                }
                            }
                        ],
                        "ports": [
                            {"protocol": "TCP", "port": 443},
                            {"protocol": "TCP", "port": 80},
                            {"protocol": "TCP", "port": 5432},
                            {"protocol": "TCP", "port": 3306},
                            {"protocol": "TCP", "port": 6379},
                        ],
                    }
                ],
            },
        }

    # ================================================================== #
    # docker-compose helpers
    # ================================================================== #

    def _compose_service(self, stack: TechStack, service_name: str) -> Dict[str, Any]:
        port = self._primary_port(stack)
        language = (stack.language or "").lower()

        if language == "html":
            service: Dict[str, Any] = {
                "image": stack.base_image or "nginx:alpine",
                "ports": [f"{port}:80"],
                "volumes": ["./:/usr/share/nginx/html/:ro"],
                "restart": "unless-stopped",
            }
        else:
            service = {
                "build": {
                    "context": ".",
                    "dockerfile": "Dockerfile",
                },
                "ports": [f"{port}:{port}"],
                "restart": "unless-stopped",
            }

        service["environment"] = [
            f"PORT={port}",
            f"APP_NAME={service_name}",
        ]
        healthcheck = self._compose_healthcheck(language, port, stack.healthcheck_path)
        if healthcheck:
            service["healthcheck"] = healthcheck
        return service

    # ================================================================== #
    # Generic helpers
    # ================================================================== #

    def _primary_port(self, stack: TechStack) -> int:
        if stack.ports:
            try:
                return int(stack.ports[0])
            except (TypeError, ValueError):
                return 8080
        return 8080

    def _labels(self, service_name: str) -> Dict[str, str]:
        return {
            "app": service_name,
            "app.kubernetes.io/name": service_name,
            "app.kubernetes.io/managed-by": "artifact-generator",
        }

    def _image_ref(self, service_name: str) -> str:
        return f"{_IMAGE_PLACEHOLDER}:{service_name}-v1.0.0"

    def _join_lines(self, lines: List[str]) -> str:
        cleaned = [line for line in lines if line]
        return "\n".join(cleaned) + "\n"

    def _cmd_exec(self, command: str) -> str:
        parts = shlex.split(command or "")
        if not parts:
            parts = ["true"]
        return f"CMD {json.dumps(parts)}"

    def _cmd_for(self, stack: TechStack) -> str:
        """Return a sensible CMD for the stack.

        ``stack.command`` overrides the default when it looks intentional
        (i.e. it is not the dataclass-wide placeholder ``"python app.py"``).
        """
        default_placeholder = "python app.py"
        if stack.command and stack.command != default_placeholder:
            return stack.command
        language = (stack.language or "").lower()
        framework = (stack.framework or "").lower()
        if language == "python":
            entry = stack.entry_point or "app.py"
            return f"python {entry}"
        if language == "node":
            entry = stack.entry_point or "server.js"
            return f"node {entry}"
        if language == "rust":
            return f"./{framework or stack.entry_point or 'app'}"
        if language == "go":
            return f"./{framework or stack.entry_point or 'app'}"
        if language == "java":
            return "java -jar app.jar"
        if language == "php":
            return "apache2-foreground"
        if language == "ruby":
            return "bundle exec rails server -b 0.0.0.0 -p ${PORT}"
        if language == "dotnet":
            return f"dotnet {framework or stack.entry_point or 'app'}.dll"
        if language == "elixir":
            return f"./bin/{framework or stack.entry_point or 'app'} start"
        return "true"

    def _create_user_block(self, run_user: str, base_image: str = "") -> str:
        """Return a single RUN instruction that creates a non-root user.

        Generates Alpine-compatible syntax for ``alpine`` base images and
        Debian-style syntax otherwise. Errors from the create commands
        are swallowed (``|| true``) so re-builds remain idempotent.
        """
        user = run_user or "appuser"
        if "alpine" in (base_image or ""):
            return (
                f"RUN addgroup -g 1000 -S {user} 2>/dev/null || true; "
                f"adduser -u 1000 -S -G {user} {user} 2>/dev/null || true"
            )
        return (
            f"RUN groupadd --system --gid 1000 {user} 2>/dev/null || true; "
            f"useradd --system --uid 1000 --gid 1000 --create-home "
            f"--shell /sbin/nologin {user} 2>/dev/null || true"
        )

    def _install_packages(self, base_image: str, packages: List[str]) -> str:
        if not packages:
            return ""
        pkg_list = " ".join(packages)
        if "alpine" in (base_image or ""):
            return f"RUN apk add --no-cache {pkg_list}"
        if (
            "debian" in (base_image or "")
            or "slim" in (base_image or "")
            or "ubuntu" in (base_image or "")
            or "jdk" in (base_image or "")
            or "jre" in (base_image or "")
            or "elixir" in (base_image or "")
        ):
            return (
                "RUN apt-get update && apt-get install -y --no-install-recommends "
                f"{pkg_list} \\\n"
                "    && rm -rf /var/lib/apt/lists/*"
            )
        return ""

    def _wget_healthcheck(self, port: int, path: str) -> str:
        path = path or "/health"
        return (
            "HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \\\n"
            f"    CMD wget -qO- http://localhost:{port}{path} || exit 1"
        )

    def _python_healthcheck(self, port: int, path: str) -> str:
        path = path or "/health"
        return (
            "HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \\\n"
            f"    CMD python -c \"import urllib.request; urllib.request.urlopen("
            f"'http://localhost:{port}{path}')\" || exit 1"
        )

    def _node_entrypoint(self, command: str) -> str:
        parts = shlex.split(command or "")
        if not parts:
            parts = ["node", "server.js"]
        return f'CMD {json.dumps(["/sbin/tini", "--"] + parts)}'

    def _python_requirements_files(self, stack: TechStack) -> List[str]:
        cmd = stack.package_install_cmd or ""
        files: List[str] = []
        if "requirements" in cmd:
            # Pull any explicit -r targets first, fall back to a glob.
            for match in re.finditer(r"-r\s+(\S+)", cmd):
                files.append(match.group(1))
            if not files:
                files.append("requirements*.txt")
        if "pyproject.toml" in cmd or "pip install ." in cmd:
            files.append("pyproject.toml")
        if not files:
            files.append("requirements.txt")
        return files

    def _runtime_image_for(self, language: str) -> str:
        if language == "rust":
            return "debian:bookworm-slim"
        if language == "go":
            # base-debian12 ships busybox (wget) and a nonroot user.
            return "gcr.io/distroless/base-debian12:nonroot"
        return "debian:bookworm-slim"

    def _java_runtime_image(self, builder_image: str) -> str:
        if "jdk" in builder_image:
            return builder_image.replace("jdk", "jre")
        return "eclipse-temurin:21-jre"

    def _dotnet_runtime_image(self, builder_image: str) -> str:
        if "/sdk:" in builder_image:
            return builder_image.replace("/sdk:", "/aspnet:")
        return "mcr.microsoft.com/dotnet/aspnet:8.0"

    def _compose_healthcheck(
        self, language: str, port: int, path: str
    ) -> Dict[str, Any]:
        path = path or "/health"
        if language == "python":
            test = (
                f"python -c \"import urllib.request; urllib.request.urlopen("
                f"'http://localhost:{port}{path}')\""
            )
        else:
            test = f"wget -qO- http://localhost:{port}{path} || exit 1"
        return {
            "test": ["CMD-SHELL", test],
            "interval": "30s",
            "timeout": "5s",
            "retries": 3,
            "start_period": "10s",
        }

    # ------------------------------------------------------------------ #
    # CI workflow plumbing
    # ------------------------------------------------------------------ #

    @staticmethod
    def _steps(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Wrap a list of step dicts; kept as a method for clarity / future hooks."""
        return list(items)

    def _ci_smoke_steps(
        self, service_name: str, port: int, health_path: str
    ) -> List[Dict[str, Any]]:
        health_path = health_path or "/"
        return [
            {"uses": "actions/checkout@v4"},
            {"run": f"docker build -t {service_name}:smoke ."},
            {
                "run": (
                    f"docker run -d --name {service_name}-smoke "
                    f"-p {port}:{port} {service_name}:smoke"
                )
            },
            {
                "run": (
                    "sleep 10 && "
                    f"curl -fsS http://localhost:{port}{health_path} "
                    f"|| (docker logs {service_name}-smoke; exit 1)"
                )
            },
            {"run": f"docker rm -f {service_name}-smoke"},
        ]

    def _ci_workflow(
        self,
        service_name: str,
        jobs: List[Tuple[str, List[Dict[str, Any]]]],
    ) -> Dict[str, Any]:
        job_dict: Dict[str, Any] = {}
        for name, steps in jobs:
            job_dict[name] = {
                "runs-on": "ubuntu-latest",
                "steps": steps,
            }
        # Wire build-smoke to depend on test + lint when both are present.
        if "build-smoke" in job_dict:
            needs = [n for n in ("test", "lint") if n in job_dict]
            if needs:
                job_dict["build-smoke"]["needs"] = needs
        return {
            "name": f"CI - {service_name}",
            "on": {
                "push": {"branches": ["main"]},
                "pull_request": {"branches": ["main"]},
            },
            "jobs": job_dict,
        }
