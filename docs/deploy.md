# Deployment Guide

## Docker Compose

```bash
docker compose up -d
```

The app will be available on port 8000.

## Kubernetes (kubectl)

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/networkpolicy.yaml
```

## Helm

```bash
helm install devops-agent ./helm/devops-agent --namespace devops-agent --create-namespace
```

## ArgoCD

```bash
kubectl apply -f argocd/application.yaml
```

## Secrets Management

Sensitive values (database URLs, API keys) should be injected via Kubernetes Secrets or an external secrets manager (e.g., Sealed Secrets, Vault). Never commit secrets to git.

## Scaling Tips

- Increase `replicas` in the Deployment or Helm `values.yaml`.
- Use HorizontalPodAutoscaler for CPU-based autoscaling.
- Run the database init job (`scripts/init_db.py`) as a Kubernetes Job before scaling up.
