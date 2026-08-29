"""
GitHub connector (read + write) — a proper tool set (not a generic JSON
manifest) because write operations need real logic: base64-encoding file
content, auto-fetching a file's current `sha` before updating it, and
building well-formed commit/PR/issue payloads.

Read actions work keylessly (rate-limited); write actions require a GitHub
Personal Access Token with `repo` scope, supplied either via the
`GITHUB_TOKEN` env var or per-user in Settings (stored as api_keys.github).
"""
from __future__ import annotations

import base64
import json
from typing import Any, Optional

import httpx

from .base import Tool

API_BASE = "https://api.github.com"


class _GitHubBase(Tool):
    def __init__(self, token_provider):
        self._token_provider = token_provider

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        token = self._token_provider()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        async with httpx.AsyncClient(timeout=30) as client:
            return await client.request(method, f"{API_BASE}{path}", headers=self._headers(), **kwargs)

    @staticmethod
    def _fmt(resp: httpx.Response, ok_summary_fn=None) -> str:
        if resp.status_code >= 400:
            return f"GitHub API error {resp.status_code}: {resp.text[:500]}"
        try:
            data = resp.json()
        except Exception:  # noqa: BLE001
            return resp.text[:4000]
        if ok_summary_fn:
            return ok_summary_fn(data)
        return json.dumps(data, indent=2)[:4000]


class GitHubSearchReposTool(_GitHubBase):
    name = "github_search_repos"
    description = "Search public GitHub repositories by keyword (e.g. 'language:python stars:>1000 llm agent')."
    parameters = {
        "type": "object",
        "properties": {"q": {"type": "string"}, "per_page": {"type": "integer", "default": 5}},
        "required": ["q"],
    }

    async def run(self, q: str, per_page: int = 5, **_: Any) -> str:
        resp = await self._request("GET", "/search/repositories", params={"q": q, "per_page": per_page})

        def summarize(data):
            items = data.get("items", [])
            return "\n".join(
                f"- {r['full_name']} ⭐{r['stargazers_count']} — {r.get('description') or ''}\n  {r['html_url']}"
                for r in items
            ) or "No repositories found."

        return self._fmt(resp, summarize)


class GitHubListFilesTool(_GitHubBase):
    name = "github_list_files"
    description = "List files/directories at a path in a GitHub repo (default: repo root)."
    parameters = {
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "path": {"type": "string", "default": ""},
            "ref": {"type": "string", "description": "branch/tag/commit, defaults to the repo's default branch"},
        },
        "required": ["owner", "repo"],
    }

    async def run(self, owner: str, repo: str, path: str = "", ref: Optional[str] = None, **_: Any) -> str:
        params = {"ref": ref} if ref else {}
        resp = await self._request("GET", f"/repos/{owner}/{repo}/contents/{path}", params=params)

        def summarize(data):
            if isinstance(data, list):
                return "\n".join(f"{'📁' if e['type'] == 'dir' else '📄'} {e['path']}" for e in data)
            return f"📄 {data.get('path')} ({data.get('size')} bytes)"

        return self._fmt(resp, summarize)


class GitHubReadFileTool(_GitHubBase):
    name = "github_read_file"
    description = "Read the text content of a single file from a GitHub repo."
    parameters = {
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "path": {"type": "string"},
            "ref": {"type": "string"},
        },
        "required": ["owner", "repo", "path"],
    }

    async def run(self, owner: str, repo: str, path: str, ref: Optional[str] = None, **_: Any) -> str:
        params = {"ref": ref} if ref else {}
        resp = await self._request("GET", f"/repos/{owner}/{repo}/contents/{path}", params=params)
        if resp.status_code >= 400:
            return self._fmt(resp)
        data = resp.json()
        if isinstance(data, list):
            return f"'{path}' is a directory, not a file. Use github_list_files instead."
        try:
            content = base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            return f"Failed to decode file content: {e}"
        return content[:8000]


class GitHubWriteFileTool(_GitHubBase):
    name = "github_write_file"
    description = (
        "Create or update a file in a GitHub repo (commits directly to the given branch). Requires a "
        "GitHub token with repo write access to be configured. Automatically fetches the current file SHA "
        "for updates so existing files are properly overwritten rather than conflicting."
    )
    parameters = {
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "path": {"type": "string"},
            "content": {"type": "string", "description": "Full new text content of the file"},
            "message": {"type": "string", "description": "Commit message"},
            "branch": {"type": "string", "description": "Branch to commit to, defaults to the repo default branch"},
        },
        "required": ["owner", "repo", "path", "content", "message"],
    }

    async def run(
        self, owner: str, repo: str, path: str, content: str, message: str, branch: Optional[str] = None, **_: Any
    ) -> str:
        if not self._token_provider():
            return (
                "Error: no GitHub token configured for write access. Ask the user to add a GitHub "
                "Personal Access Token (repo scope) in Settings → Connectors → GitHub."
            )
        params = {"ref": branch} if branch else {}
        existing = await self._request("GET", f"/repos/{owner}/{repo}/contents/{path}", params=params)
        sha = existing.json().get("sha") if existing.status_code == 200 else None

        payload: dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        }
        if branch:
            payload["branch"] = branch
        if sha:
            payload["sha"] = sha

        resp = await self._request("PUT", f"/repos/{owner}/{repo}/contents/{path}", json=payload)

        def summarize(data):
            commit = data.get("commit", {})
            action = "Updated" if sha else "Created"
            return f"{action} {path} in {owner}/{repo}. Commit: {commit.get('sha', '?')[:10]} — {commit.get('html_url', '')}"

        return self._fmt(resp, summarize)


class GitHubCreateIssueTool(_GitHubBase):
    name = "github_create_issue"
    description = "Create a new issue in a GitHub repo. Requires a GitHub token with repo access."
    parameters = {
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "title": {"type": "string"},
            "body": {"type": "string", "default": ""},
            "labels": {"type": "array", "items": {"type": "string"}, "default": []},
        },
        "required": ["owner", "repo", "title"],
    }

    async def run(self, owner: str, repo: str, title: str, body: str = "", labels: Optional[list[str]] = None, **_: Any) -> str:
        if not self._token_provider():
            return "Error: no GitHub token configured. Ask the user to add a GitHub PAT in Settings → Connectors."
        payload = {"title": title, "body": body, "labels": labels or []}
        resp = await self._request("POST", f"/repos/{owner}/{repo}/issues", json=payload)

        def summarize(data):
            return f"Created issue #{data.get('number')}: {data.get('html_url')}"

        return self._fmt(resp, summarize)


class GitHubCreatePRTool(_GitHubBase):
    name = "github_create_pull_request"
    description = (
        "Open a pull request in a GitHub repo from one branch into another (e.g. after committing changes "
        "with github_write_file to a feature branch). Requires a GitHub token with repo access."
    )
    parameters = {
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "title": {"type": "string"},
            "head": {"type": "string", "description": "Branch containing changes, e.g. 'feature-x' or 'username:feature-x'"},
            "base": {"type": "string", "description": "Branch to merge into, e.g. 'main'"},
            "body": {"type": "string", "default": ""},
        },
        "required": ["owner", "repo", "title", "head", "base"],
    }

    async def run(self, owner: str, repo: str, title: str, head: str, base: str, body: str = "", **_: Any) -> str:
        if not self._token_provider():
            return "Error: no GitHub token configured. Ask the user to add a GitHub PAT in Settings → Connectors."
        payload = {"title": title, "head": head, "base": base, "body": body}
        resp = await self._request("POST", f"/repos/{owner}/{repo}/pulls", json=payload)

        def summarize(data):
            return f"Opened PR #{data.get('number')}: {data.get('html_url')}"

        return self._fmt(resp, summarize)


class GitHubListIssuesTool(_GitHubBase):
    name = "github_list_issues"
    description = "List open issues (or PRs) in a GitHub repo."
    parameters = {
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "state": {"type": "string", "enum": ["open", "closed", "all"], "default": "open"},
            "per_page": {"type": "integer", "default": 10},
        },
        "required": ["owner", "repo"],
    }

    async def run(self, owner: str, repo: str, state: str = "open", per_page: int = 10, **_: Any) -> str:
        resp = await self._request("GET", f"/repos/{owner}/{repo}/issues", params={"state": state, "per_page": per_page})

        def summarize(data):
            return "\n".join(f"#{i['number']} {i['title']} ({i['state']}) — {i['html_url']}" for i in data) or "No issues found."

        return self._fmt(resp, summarize)


def build_github_tools(token_provider) -> list[Tool]:
    """token_provider: zero-arg callable returning the resolved GitHub PAT or None."""
    return [
        GitHubSearchReposTool(token_provider),
        GitHubListFilesTool(token_provider),
        GitHubReadFileTool(token_provider),
        GitHubWriteFileTool(token_provider),
        GitHubCreateIssueTool(token_provider),
        GitHubCreatePRTool(token_provider),
        GitHubListIssuesTool(token_provider),
    ]
