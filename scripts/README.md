# Local Development Scripts

These scripts are **NOT** part of the devops_agent tool API.
They are convenience utilities for local development only and are not
imported or called by the main pipeline.

## run_one.py

Runs devops_agent against a single target directory with preset flags.

```bash
python scripts/run_one.py [project_path]
```

## git_commit.py

Auto-commits generated artifacts to a branch.

> **WARNING**: Review all generated artifacts before using this script.
> It will commit everything in the output directory to the specified branch.

```bash
python scripts/git_commit.py [output_dir] [branch_name]
```
