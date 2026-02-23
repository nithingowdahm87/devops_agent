# -*- coding: utf-8 -*-
import os

# Create fallback directory
FALLBACK_DIR = os.path.join(os.path.dirname(__file__), "templates/fallback")
os.makedirs(FALLBACK_DIR, exist_ok=True)

# 1. Dockerfile Fallback
DOCKERFILE_FALLBACK = """# Generated Fallback Dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
USER node
EXPOSE 3000
CMD ["npm", "start"]
"""

# 2. Docker Compose Fallback
COMPOSE_FALLBACK = """version: '3.8'
services:
  app:
    build: .
    ports:
      - "3000:3000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
"""

# 3. K8s Fallback
K8S_FALLBACK = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-fallback
spec:
  replicas: 2
  selector:
    matchLabels:
      app: fallback
  template:
    metadata:
      labels:
        app: fallback
    spec:
      containers:
      - name: app
        image: app:latest
        ports:
        - containerPort: 3000
        resources:
          limits:
            cpu: "500m"
            memory: "512Mi"
          requests:
            cpu: "200m"
            memory: "256Mi"
        securityContext:
          runAsNonRoot: true
          runAsUser: 1000
---
apiVersion: v1
kind: Service
metadata:
  name: app-fallback
spec:
  selector:
    app: fallback
  ports:
  - port: 80
    targetPort: 3000
"""

def write_fallbacks():
    with open(os.path.join(FALLBACK_DIR, "Dockerfile"), "w", encoding="utf-8") as f:
        f.write(DOCKERFILE_FALLBACK)
    with open(os.path.join(FALLBACK_DIR, "docker-compose.yml"), "w", encoding="utf-8") as f:
        f.write(COMPOSE_FALLBACK)
    with open(os.path.join(FALLBACK_DIR, "k8s-deployment.yaml"), "w", encoding="utf-8") as f:
        f.write(K8S_FALLBACK)

if __name__ == "__main__":
    write_fallbacks()
