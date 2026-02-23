class MockClient:
    def __init__(self, name="MockAI"):
        self.name = name
    
    def call(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        print(f"  [MockClient:{self.name}] Received prompt length: {len(prompt)}")
        
        if "sonar-project.properties" in prompt_lower or ("opentelemetry" in prompt_lower and "tracing.js" in prompt_lower):
            return """
FILENAME: backend/sonar-project.properties
```properties
sonar.projectKey=backend
sonar.sources=src
sonar.exclusions=node_modules/**,tests/**
```

FILENAME: frontend/sonar-project.properties
```properties
sonar.projectKey=frontend
sonar.sources=src
sonar.exclusions=node_modules/**
```

FILENAME: backend/tracing.js
```javascript
const { NodeSDK } = require('@opentelemetry/sdk-node');
const { getNodeAutoInstrumentations } = require('@opentelemetry/auto-instrumentations-node');
const sdk = new NodeSDK({ instrumentations: [getNodeAutoInstrumentations()] });
sdk.start();
```

FILENAME: .gitleaks.toml
```toml
[allowlist]
description = "Global allowlist"
```
"""

        # SPECIFIC STAGES FIRST
        if "docker-compose" in prompt_lower or "docker compose" in prompt_lower:
            return """
FILENAME: docker-compose.yml
```yaml
version: '3.8'
services:
  backend:
    build: 
      context: ./backend
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
    depends_on:
      db:
        condition: service_healthy
  frontend:
    build:
      context: ./frontend
    ports:
      - "5173:5173"
    depends_on:
      - backend
  db:
    image: postgres:15-alpine
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
```
"""

        if "github actions" in prompt_lower or "ci" in prompt_lower:
            # Check if it was really asking for docker-compose instead
            if "docker-compose" not in prompt_lower:
                return """
FILENAME: .github/workflows/main.yml
```yaml
name: CI
on:
  push:
    branches: [main]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build
        run: echo "Mock build"
```
"""

        # "dockerfile" or "docker" but NOT "compose"
        if "dockerfile" in prompt_lower or ("docker" in prompt_lower and "build" in prompt_lower):
            # Check if it should be multi-file
            if "backend" in prompt_lower and "frontend" in prompt_lower:
                return """
FILENAME: backend/Dockerfile
```dockerfile
# Build stage
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

# Run stage
FROM node:20-alpine
WORKDIR /app
RUN adduser -D appuser && chown -R appuser:appuser /app
USER appuser
COPY --from=builder --chown=appuser:appuser /app .
ENV NODE_ENV=production
HEALTHCHECK --interval=30s --timeout=5s CMD node -e "process.exit(0)"
CMD ["node", "index.js"]
```

FILENAME: backend/.dockerignore
```
node_modules
.git
.env
```

FILENAME: frontend/Dockerfile
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

FROM node:20-alpine
WORKDIR /app
RUN adduser -D appuser && chown -R appuser:appuser /app
USER appuser
COPY --from=builder --chown=appuser:appuser /app .
EXPOSE 5173
HEALTHCHECK --interval=30s --timeout=5s CMD node -e "process.exit(0)"
CMD ["npm", "run", "dev"]
```
"""
            return """
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

FROM node:20-alpine
WORKDIR /app
RUN adduser -D appuser && chown -R appuser:appuser /app
USER appuser
COPY --from=builder --chown=appuser:appuser /app .
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s CMD node -e "process.exit(0)"
CMD ["node", "index.js"]
"""
        if "kubernetes" in prompt_lower and "review" not in prompt_lower:
            return """
FILENAME: k8s/deployment.yaml
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
      containers:
      - name: backend
        image: backend:1.0.0
        ports:
        - containerPort: 3000
        resources:
          limits:
            cpu: "500m"
            memory: "512Mi"
          requests:
            cpu: "100m"
            memory: "256Mi"
        livenessProbe:
          httpGet:
            path: /health
            port: 3000
```
"""
        if "helm" in prompt_lower or "observability" in prompt_lower:
            return """
apiVersion: v2
name: myapp-monitoring
version: 0.1.0
dependencies:
  - name: prometheus
    version: 15.0.0
"""

        # --- 3. DEBUG / ANALYSIS (Specific triggers) ---
        if "lead sre" in prompt_lower or "incident report" in prompt_lower:
             return """
REASONING:
- Primary issue is missing MongoDB connection configuration
- No security breach detected

REPORT:
## Incident Report
**Severity:** HIGH
**Root Cause:** Missing MONGO_URI environment variable
**Remediation:** Add MONGO_URI to environment
"""
        if "security" in prompt_lower and "engineer" in prompt_lower:
            return """
SECURITY_RISK: NO
ANALYSIS:
- No exposed secrets detected.
- Configuration issue only.
FIX:
```
Ensure MONGO_URI uses TLS.
```
"""

        # --- 4. GENERIC REVIEW (Last Resort) ---
        if "review" in prompt_lower:
            if "manifest" in prompt_lower or "kubernetes" in prompt_lower:
                return """
REASONING:
- Mock K8s review: valid structure
YAML:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: myapp
```
"""
            else:
                return """
REASONING:
- Mock Docker review: optimized layers
DOCKERFILE:
FROM node:alpine
"""
                
        return "Mock response"
