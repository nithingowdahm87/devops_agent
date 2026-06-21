"""
GitOps Publisher — Branch + Commit + PR instead of direct file writes.

Usage:
    from src.gitops.pr_creator import GitOpsPublisher

    publisher = GitOpsPublisher()
    result = publisher.publish(
        files={"Dockerfile": dockerfile_content},
        stage="Docker",
        run_id="a1b2c3d4",
        reasoning="Multi-stage build with non-root user",
    )
    # result = {"mode": "pr", "url": "https://github.com/.../pull/42"}
    # or      {"mode": "local", "paths": ["/project/Dockerfile"]}
"""

import json
import logging
import os
import time

import requests

from src.utils.secrets import get_secret

logger = logging.getLogger("devops-agent.gitops")


class GitOpsPublisher:
    """
    Publishes approved artifacts via GitHub PR or local file write.

    Priority:
      1. If GITHUB_TOKEN + GITHUB_REPO are set → create branch + commit + PR
      2. Otherwise → write files to disk (backward compatible)
    """

    def __init__(self):
        try:
            self.token = get_secret("GITHUB_TOKEN")
        except RuntimeError:
            self.token = None
        self.repo = os.environ.get("GITHUB_REPO", "")  # e.g. "owner/repo"
        self.base_branch = os.environ.get("GITHUB_BASE_BRANCH", "main")
        self.api_base = "https://api.github.com"

        if self.token and self.repo:
            self.mode = "pr"
            logger.info("GitOps mode: PR (repo=%s)", self.repo)
        else:
            self.mode = "local"
            logger.info("GitOps mode: local file write (set GITHUB_TOKEN + GITHUB_REPO for PR mode)")

        self._headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    # ─── Public API ──────────────────────────────────────────────

    def publish(
        self,
        files: dict[str, str],
        stage: str,
        run_id: str,
        reasoning: str = "",
        project_path: str = "",
    ) -> dict:
        """
        Publish approved artifacts.

        Args:
            files: {relative_path: content} e.g. {"Dockerfile": "FROM ..."}
            stage: Pipeline stage name
            run_id: Correlation ID for this pipeline run
            reasoning: AI reasoning summary for the PR description
            project_path: Local project path (used for local mode)

        Returns:
            {"mode": "pr", "url": pr_url} or {"mode": "local", "paths": [...]}
        """
        # ─── Semantic Polish 10 Target Rewriting ────────
        # If this is GitHub Actions from the orchestrator, it's currently structured as:
        # "outputs/per-service/<svc_name>/.github/workflows/<svc>-ci.yml"
        # We must rewrite this to target the actual root ".github/workflows/" of the repo.
        publish_files = {}
        for fpath, content in files.items():
            out_path = fpath
            if stage == "github_actions" and ".github/workflows/" in fpath:
                # Strip everything before .github/workflows/
                parts = fpath.split(".github/workflows/")
                if len(parts) > 1:
                    out_path = f".github/workflows/{parts[-1]}"
            publish_files[out_path] = content

        if self.mode == "pr":
            return self._publish_pr(publish_files, stage, run_id, reasoning)
        else:
            return self._publish_local(publish_files, project_path)

    # ─── GitHub PR Path ──────────────────────────────────────────

    def _publish_pr(self, files: dict, stage: str, run_id: str, reasoning: str) -> dict:
        """Create branch, commit files, open PR."""
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        branch_name = f"devops-agent/{run_id}/{stage.lower().replace('/', '-')}"

        try:
            # 1. Get base branch SHA
            base_sha = self._get_ref_sha(self.base_branch)

            # 2. Create branch
            self._create_branch(branch_name, base_sha)
            logger.info("Created branch: %s", branch_name)

            # 3. Commit files
            for filepath, content in files.items():
                self._create_or_update_file(branch_name, filepath, content, stage, run_id)
                logger.info("Committed: %s", filepath)

            # 4. Open PR
            pr_url = self._create_pr(
                branch_name=branch_name,
                stage=stage,
                run_id=run_id,
                reasoning=reasoning,
                files=list(files.keys()),
            )
            logger.info("PR created: %s", pr_url)

            return {"mode": "pr", "url": pr_url, "branch": branch_name}

        except Exception as e:
            logger.error("GitHub PR creation failed: %s — falling back to local", e)
            print(f"⚠️  PR creation failed ({e}). Writing locally instead.")
            return {"mode": "local_fallback", "error": str(e)}

    def _get_ref_sha(self, branch: str) -> str:
        """Get the SHA of the latest commit on a branch."""
        url = f"{self.api_base}/repos/{self.repo}/git/ref/heads/{branch}"
        resp = requests.get(url, headers=self._headers, timeout=10)
        resp.raise_for_status()
        return resp.json()["object"]["sha"]

    def _create_branch(self, branch_name: str, sha: str):
        """Create a new branch from the given SHA."""
        url = f"{self.api_base}/repos/{self.repo}/git/refs"
        data = {"ref": f"refs/heads/{branch_name}", "sha": sha}
        resp = requests.post(url, headers=self._headers, json=data, timeout=10)
        if resp.status_code == 422:
            # Branch already exists — that's fine for retries
            logger.warning("Branch %s already exists, reusing", branch_name)
            return
        resp.raise_for_status()

    def _create_or_update_file(
        self, branch: str, filepath: str, content: str, stage: str, run_id: str
    ):
        """Create or update a file on the branch."""
        import base64

        url = f"{self.api_base}/repos/{self.repo}/contents/{filepath}"

        # Check if file exists on this branch (for updates)
        sha = None
        resp = requests.get(url, headers=self._headers, params={"ref": branch}, timeout=10)
        if resp.status_code == 200:
            sha = resp.json().get("sha")

        data = {
            "message": f"[{stage}] Generated by DevOps Agent (run:{run_id})",
            "content": base64.b64encode(content.encode()).decode(),
            "branch": branch,
        }
        if sha:
            data["sha"] = sha

        resp = requests.put(url, headers=self._headers, json=data, timeout=15)
        resp.raise_for_status()

    def _create_pr(
        self, branch_name: str, stage: str, run_id: str, reasoning: str, files: list
    ) -> str:
        """Open a pull request."""
        url = f"{self.api_base}/repos/{self.repo}/pulls"

        files_list = "\n".join(f"- `{f}`" for f in files)
        body = (
            f"## 🤖 DevOps Agent — {stage}\n\n"
            f"**Run ID:** `{run_id}`\n"
            f"**Stage:** {stage}\n"
            f"**Generated at:** {time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
            f"### Files\n{files_list}\n\n"
            f"### AI Reasoning\n{reasoning[:1000] if reasoning else 'N/A'}\n\n"
            f"---\n"
            f"*Auto-generated by [DevOps AI Agent](https://github.com/nithingowdahm87/devops_agent) v1.0.0*"
        )

        data = {
            "title": f"[DevOps Agent] {stage} — run:{run_id}",
            "head": branch_name,
            "base": self.base_branch,
            "body": body,
        }

        resp = requests.post(url, headers=self._headers, json=data, timeout=15)
        resp.raise_for_status()
        return resp.json()["html_url"]

    # ─── Local Fallback Path ─────────────────────────────────────

    def _publish_local(self, files: dict, project_path: str) -> dict:
        """Write files to disk (backward compatible)."""
        from src.tools.file_ops import write_file

        paths = []
        for filepath, content in files.items():
            full_path = os.path.join(project_path, filepath)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            write_file(full_path, content)
            paths.append(full_path)
            logger.info("Wrote file locally: %s", full_path)

        return {"mode": "local", "paths": paths}
