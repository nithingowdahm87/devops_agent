import subprocess

# Stage files
result = subprocess.run(['git', 'add', 'Dockerfile', 'README.md', 'pyproject.toml'], capture_output=True, text=True, shell=False)
print("Add:", result.stdout, result.stderr)

# Commit
result = subprocess.run(['git', 'commit', '-m', 'fix: pin apt/pip versions in Dockerfile for hadolint, update Python deps for security, update README'], capture_output=True, text=True, shell=False)
print("Commit:", result.stdout, result.stderr)

# Push
result = subprocess.run(['git', 'push', 'origin', 'main'], capture_output=True, text=True, shell=False)
print("Push:", result.stdout, result.stderr)