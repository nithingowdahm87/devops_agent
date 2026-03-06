# Docker Guidelines

- NEVER use :latest — pin to major.minor minimum (node:20-alpine)
- Multi-stage builds mandatory for any compiled or transpiled application
- Non-root user required (UID >= 10001) — recreate in RUNTIME stage, not just builder
- HEALTHCHECK required in every production image
- WORKDIR must be set explicitly (/app) in all stages
- COPY must be explicit — NEVER COPY . . in any stage
- .dockerignore must be generated alongside every Dockerfile
- OCI labels (org.opencontainers.image.*) required with ARG-injected values
- No build tools, shells, or debug utilities in final stage
- CMD and ENTRYPOINT must use exec form (JSON array)
- Cache cleaning must happen in same RUN layer OR via BuildKit cache mount
- readOnlyRootFilesystem compatible: /tmp and /var/run must use emptyDir volumes
- Signal handling: tini required for Python; exec node directly for Node.js
- Layer order: FROM → user setup → manifests → install → config → source → build

## Language-Specific Requirements (CRITICAL)

### Java (Spring Boot)
- **Base Images:** builder = `maven:3.9-eclipse-temurin-21`, runtime = `eclipse-temurin:21-jre-alpine` (use digest pinning e.g., `@sha256:...` if possible).
- **User Setup:** Must explicitly run `adduser -u 10001 -D appuser` and use `USER 10001`.
- **Permissions:** Use `--chown=10001:10001` on the final `COPY`. Must be perfectly consistent across all Java services.
- **Dependency Caching:** `RUN mvn dependency:go-offline -B` before copying source code.
- **Build Command:** Use `RUN mvn clean package verify` (not skipTests for production builds).
- **Graceful Shutdown & Memory:** Split shell commands. Set JVM container support and memory limits:
  `ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75.0", "-XX:+UseContainerSupport", "-jar"]`
  `CMD ["app.jar"]`

### Python (FastAPI/Flask)
- **Base Images:** builder/runtime = `python:3.11-slim` or newer.
- **Two-Stage Pattern:**
  - Builder: `COPY requirements.txt .` → `RUN pip install --no-cache-dir --prefix=/install -r requirements.txt`
  - Runtime: `COPY --from=builder /install /usr/local` → `COPY app/ ./app/` (the entire source code must be explicitly copied into runtime!)
- **Worker Configuration:** Production servers (e.g., uvicorn, gunicorn) must include concurrency flags. Example: `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]`

### Frontend (React/Vue/Angular) with Nginx
- **Base Images:** builder = `node:20-alpine`, runtime = `nginx:1.27-alpine`.
- **User Setup:** Create and use non-root user `10001`.
- **Non-Root Port Binding:** Nginx cannot bind to port `80` if running as non-root. You MUST configure nginx and the Dockerfile to use an unprivileged port like `8080`.
  - `EXPOSE 8080` (Not 80)
  - Your `nginx.conf` must listen on `8080`.
  - The Kubernetes/Compose manifests must map targetPort `8080`.
- **Permissions:** Ensure the `nginx` unprivileged user owns `/usr/share/nginx/html`, `/var/cache/nginx`, `/var/run`, and `/var/log/nginx`.
