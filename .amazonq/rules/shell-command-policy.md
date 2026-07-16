# Shell Command Policy

You may run safe, project-local shell commands without asking for confirmation.

Allowed commands include:
- pwd, ls, find, grep, rg, cat, sed, head, tail
- git status, git diff, git log, git branch
- pytest, python3 -m pytest
- npm test, npm run *, npm install
- pip install -r requirements.txt
- docker compose build, docker compose up, docker compose down, docker compose ps, docker compose logs
- terraform fmt, terraform validate, terraform plan

Always ask before running:
- rm, sudo, chmod, chown
- git push, git reset --hard, git clean
- terraform apply, terraform destroy
- kubectl apply, kubectl delete
- AWS CLI commands that create, update, or delete resources
- Commands that access, print, rotate, or modify secrets, SSH keys, AWS credentials, or files outside this repository