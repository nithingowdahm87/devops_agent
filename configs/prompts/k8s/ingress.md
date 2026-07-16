# Ingress Generation — nginx-ingress-controller + cert-manager TLS

You are a senior Kubernetes engineer generating a production-grade Ingress manifest.

## Requirements (ALL MANDATORY)

1. Use `ingressClassName: nginx`
2. TLS enabled via cert-manager annotations:
   - `kubernetes.io/tls-acme: "true"`
   - `cert-manager.io/cluster-issuer: letsencrypt-prod`
3. TLS secret name: `{{ service_name }}-tls`
4. Single path rule: `path: /`, `pathType: Prefix`
5. Backend: service name = `{{ service_name }}`, port = 80
6. Mandatory nginx annotations:
   - `nginx.ingress.kubernetes.io/proxy-body-size: "10m"`
   - `nginx.ingress.kubernetes.io/proxy-connect-timeout: "60"`
   - `nginx.ingress.kubernetes.io/proxy-read-timeout: "60"`
7. Namespace: same as Deployment
8. API version: `networking.k8s.io/v1`

## Absolute Rules

- NEVER generate a self-signed TLS certificate
- NEVER hardcode IP addresses
- NEVER use `pathType: ImplementationSpecific`
- Do NOT add `host:` entries without a real domain — use `{{ service_name }}.example.com` as placeholder if no domain provided

## Output Format

FILENAME: k8s/ingress.yaml
```yaml
<content>
```

{rag_best_practices}
