# SYSTEM INSTRUCTIONS: Secrets Requirement Document Generator

Identify and list all required secrets for the current microservice(s).

## OUTPUT FORMAT
FILENAME: docs/secrets-required.md
```markdown
# Required Secrets

| Secret Name | Description |
|---|---|
| DOCKERHUB_USERNAME | Docker Hub username |
| DOCKERHUB_TOKEN | Docker Hub entry token |
| GITOPS_TOKEN | Personal Access Token for GitOps repo |
| {{ service_name }}_DB_PASSWORD | Database password for this service |
...
```
