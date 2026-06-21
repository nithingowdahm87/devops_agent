# -*- coding: utf-8 -*-
import os

# Create fallback directory
FALLBACK_DIR = os.path.join(os.path.dirname(__file__), "templates/fallback")
os.makedirs(FALLBACK_DIR, exist_ok=True)

# DOCKERFILE Fallback
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

# COMPOSE Fallback
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
  name: api
  namespace: sample-api
  labels:
    app: api
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "3000"
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
              app: api
      containers:
        - name: api
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
            - containerPort: 3000
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
              port: 3000
            initialDelaySeconds: 10
            periodSeconds: 15
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health
              port: 3000
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
                        - api
                topologyKey: kubernetes.io/hostname
```

FILENAME: k8s/service.yaml
```yaml
apiVersion: v1
kind: Service
metadata:
  name: api
  namespace: sample-api
spec:
  type: ClusterIP
  selector:
    app: api
  ports:
    - port: 80
      targetPort: 3000
      protocol: TCP
      name: http
```

FILENAME: k8s/ingress.yaml
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api
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
                name: api
                port:
                  number: 80
```

FILENAME: k8s/hpa.yaml
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api
  namespace: sample-api
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
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
  name: api
  namespace: sample-api
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: api
```

FILENAME: k8s/networkpolicy.yaml
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-network-policy
  namespace: sample-api
spec:
  podSelector:
    matchLabels:
      app: api
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
          port: 3000
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: mongo
      ports:
        - protocol: TCP
          port: 27017
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

# CI Fallback
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

def write_fallbacks():
    """Write fallback templates from bundled constants to disk."""
    fallback_map = {
        "Dockerfile": DOCKERFILE_FALLBACK,
        "docker-compose.yml": COMPOSE_FALLBACK,
        "k8s-deployment.yaml": K8S_FALLBACK,
        "gha-ci.yml": CI_FALLBACK,
    }
    for filename, content in fallback_map.items():
        filepath = os.path.join(FALLBACK_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(content)

if __name__ == "__main__":
    write_fallbacks()
