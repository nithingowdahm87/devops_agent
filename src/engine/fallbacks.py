# -*- coding: utf-8 -*-
import os

# Create fallback directory
FALLBACK_DIR = os.path.join(os.path.dirname(__file__), "templates/fallback")
os.makedirs(FALLBACK_DIR, exist_ok=True)

# DOCKERFILE Fallback (Node.js / Express)
DOCKERFILE_FALLBACK = """
# syntax=docker/dockerfile:1.6

# ─── Dependencies Stage ─────────────────────────────────
FROM node:20-alpine AS deps
RUN apk add --no-cache tini=0.19.0-r1
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev && npm cache clean --force
RUN npm audit --audit-level=moderate || true

# ─── Production Stage ────────────────────────────────────
FROM node:20-alpine AS production
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /sbin/tini /sbin/tini
COPY package*.json ./
COPY .env.example .env.example
COPY server.js ./
ENV NODE_ENV=production
ENV PORT=3000
USER appuser
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:3000/health || exit 1
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["node", "server.js"]
LABEL org.opencontainers.image.source="https://github.com/OWNER/REPO"
LABEL org.opencontainers.image.description="Node.js Express API"

"""

# DOCKERFILE Fallback (Python / Flask)
DOCKERFILE_FALLBACK_PYTHON = """
# syntax=docker/dockerfile:1.6
# ─── Python Dependencies Stage ─────────────────────────────────
FROM python:3.12-slim AS deps
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ─── Production Stage ────────────────────────────────────
FROM python:3.12-slim AS production
RUN groupadd -r appgroup && useradd -r -g appgroup appuser
WORKDIR /app
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin
COPY . .
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=5000
USER appuser
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1
ENTRYPOINT ["python", "-m", "gunicorn"]
CMD ["-b", "0.0.0.0:5000", "app:app"]
LABEL org.opencontainers.image.source="https://github.com/OWNER/REPO"
LABEL org.opencontainers.image.description="Python Flask API"

"""

# DOCKERFILE Fallback (Static HTML / nginx)
DOCKERFILE_FALLBACK_STATIC = """
# syntax=docker/dockerfile:1.6
FROM nginx:alpine
COPY . /usr/share/nginx/html/
EXPOSE 8080
LABEL org.opencontainers.image.source="https://github.com/OWNER/REPO"
LABEL org.opencontainers.image.description="Static HTML Frontend"

"""

# COMPOSE Fallback (Node.js + MongoDB)
COMPOSE_FALLBACK = """
version: "3.9"

networks:
  sample-api:
    driver: bridge

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    env_file:
      - .env
    networks:
      - sample-api
    depends_on:
      mongo:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:3000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '0.50'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 128M

  mongo:
    image: mongo:7.0
    volumes:
      - mongodata:/data/db
    networks:
      - sample-api
    environment:
      MONGO_INITDB_ROOT_USERNAME: admin
      MONGO_INITDB_ROOT_PASSWORD_FILE: /run/secrets/mongo_root_password
    secrets:
      - mongo_root_password
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s
    deploy:
      resources:
        limits:
          memory: 512M
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    restart: unless-stopped

volumes:
  mongodata: {}

secrets:
  mongo_root_password:
    external: true

"""

# COMPOSE Fallback (Multi-service: backend + frontend)
COMPOSE_FALLBACK_MULTI = """
version: "3.9"

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "5000:5000"
    env_file:
      - .env
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "8080:8080"
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped

"""

# K8S Fallback
K8S_FALLBACK = """
FILENAME: k8s/namespace.yaml
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: sample-api
  labels:
    name: sample-api
    cost.allocation: sample-api
```

FILENAME: k8s/configmap.yaml
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: api-config
  namespace: sample-api
data:
  PORT: "3000"
  NODE_ENV: production
```

FILENAME: k8s/secret.yaml
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: api-secrets
  namespace: sample-api
type: Opaque
stringData:
  # PLACEHOLDER — Replace with Sealed Secrets, Vault, or external-secrets in production.
  MONGODB_URI: mongodb://mongo:27017/sampledb
  JWT_SECRET: change-me-in-production
```

FILENAME: k8s/deployment.yaml
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {service_name}
  namespace: sample-api
  labels:
    app: {service_name}
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: {service_name}
  template:
    metadata:
      labels:
        app: {service_name}
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "{port}"
        prometheus.io/path: "/metrics"
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      terminationGracePeriodSeconds: 30
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels:
              app: {service_name}
      containers:
        - name: {service_name}
          image: "ghcr.io/OWNER/REPO:v1.0.0"
          imagePullPolicy: IfNotPresent
          envFrom:
            - configMapRef:
                name: api-config
          env:
            - name: MONGODB_URI
              valueFrom:
                secretKeyRef:
                  name: api-secrets
                  key: MONGODB_URI
            - name: JWT_SECRET
              valueFrom:
                secretKeyRef:
                  name: api-secrets
                  key: JWT_SECRET
          ports:
            - containerPort: {port}
              protocol: TCP
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL
          livenessProbe:
            httpGet:
              path: /health
              port: "{port}"
            initialDelaySeconds: 10
            periodSeconds: 15
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health
              port: "{port}"
            initialDelaySeconds: 5
            periodSeconds: 10
            timeoutSeconds: 3
            failureThreshold: 3
          volumeMounts:
            - name: tmp
              mountPath: /tmp
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 15"]
      volumes:
        - name: tmp
          emptyDir: {}
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchExpressions:
                    - key: app
                      operator: In
                      values:
                        - {service_name}
                topologyKey: kubernetes.io/hostname
```

FILENAME: k8s/service.yaml
```yaml
apiVersion: v1
kind: Service
metadata:
  name: {service_name}
  namespace: sample-api
spec:
  type: ClusterIP
  selector:
    app: {service_name}
  ports:
    - port: 80
      targetPort: "{port}"
      protocol: TCP
      name: http
```

FILENAME: k8s/ingress.yaml
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {service_name}
  namespace: sample-api
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - api.example.com
      secretName: api-tls
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: {service_name}
                port:
                  number: 80
```

FILENAME: k8s/hpa.yaml
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {service_name}
  namespace: sample-api
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {service_name}
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 10
          periodSeconds: 60
```

FILENAME: k8s/pdb.yaml
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {service_name}
  namespace: sample-api
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: {service_name}
```

FILENAME: k8s/networkpolicy.yaml
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {service_name}-network-policy
  namespace: sample-api
spec:
  podSelector:
    matchLabels:
      app: {service_name}
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
      ports:
        - protocol: TCP
          port: "{port}"
  egress:
    - to:
        - namespaceSelector: {}
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
```

"""

# CI Fallback (Node.js)
CI_FALLBACK = """
name: CI Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

env:
  NODE_VERSION: "20"
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: "npm"
      - run: npm ci
      - run: npx eslint . --ext .js
      - run: npm test -- --coverage --ci
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        continue-on-error: true

  dockerfile-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hadolint/hadolint-action@v3.1.0
        with:
          dockerfile: Dockerfile
          failure-threshold: info

  security-scan:
    runs-on: ubuntu-latest
    needs: dockerfile-lint
    steps:
      - uses: actions/checkout@v4
      - name: Trivy FS scan
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: fs
          scan-ref: .
          severity: HIGH,CRITICAL
          exit-code: 1
      - name: Gitleaks
        uses: gitleaks/gitleaks-action@v2
        continue-on-error: true

  build-and-smoke:
    runs-on: ubuntu-latest
    needs: [lint-and-test, security-scan]
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Docker meta
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: ${{ github.ref == 'refs/heads/main' }}
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
      - name: Smoke test
        if: github.ref == 'refs/heads/main'
        run: docker run -d --name smoke -p 3001:3000 ${{ steps.meta.outputs.tags }} && sleep 5 && curl -sSf http://localhost:3001/health || exit 1 && curl -sSf http://localhost:3001/metrics || exit 1 && docker rm -f smoke

"""

# CI Fallback (Python / pytest)
CI_FALLBACK_PYTHON = """
name: CI Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

env:
  PYTHON_VERSION: "3.12"
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v --tb=short
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        continue-on-error: true

  dockerfile-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hadolint/hadolint-action@v3.1.0
        with:
          dockerfile: Dockerfile
          failure-threshold: info

  build-and-smoke:
    runs-on: ubuntu-latest
    needs: lint-and-test
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - name: Build
        run: docker build -t ${{ env.IMAGE_NAME }}:latest .
      - name: Smoke test
        run: docker run -d --name smoke -p 5001:5000 ${{ env.IMAGE_NAME }}:latest && sleep 5 && curl -sSf http://localhost:5001/health || exit 1 && docker rm -f smoke

"""

# CI Fallback (Static HTML)
CI_FALLBACK_STATIC = """
name: CI Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build-and-smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - name: Build
        run: docker build -t app:latest .
      - name: Smoke test
        run: docker run -d --name smoke -p 8081:8080 app:latest && sleep 3 && curl -sSf http://localhost:8081/ || exit 1 && docker rm -f smoke

"""


def write_fallbacks():
    """Write fallback templates from bundled constants to disk."""
    fallback_map = {
        "Dockerfile": DOCKERFILE_FALLBACK,
        "docker-compose.yml": COMPOSE_FALLBACK,
        "k8s-deployment.yaml": K8S_FALLBACK,
        "gha-ci.yml": CI_FALLBACK,
        "Dockerfile.python": DOCKERFILE_FALLBACK_PYTHON,
        "Dockerfile.static": DOCKERFILE_FALLBACK_STATIC,
        "docker-compose.multi.yml": COMPOSE_FALLBACK_MULTI,
        "gha-ci.python.yml": CI_FALLBACK_PYTHON,
        "gha-ci.static.yml": CI_FALLBACK_STATIC,
    }
    for filename, content in fallback_map.items():
        filepath = os.path.join(FALLBACK_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(content)


if __name__ == "__main__":
    write_fallbacks()
