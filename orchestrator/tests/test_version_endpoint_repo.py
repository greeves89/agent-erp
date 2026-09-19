"""Issue #30: the version/changelog endpoints must talk to THIS repository.

The four GitHub URLs used to be hard-coded copies pointing at the upstream
project this repo was forked from, so the update banner and the changelog
belonged to a different product. They are now derived from one constant
(app.config.GITHUB_REPO). These tests pin the requested URLs at the call
site, not just the constant, so a stray literal cannot creep back in.
"""

from unittest.mock import patch

import pytest

from app import config
from app.api import downloads, version


class _Resp:
    def __init__(self, status_code=200, text="", json_data=None):
        self.status_code = status_code
        self.text = text
        self._json = json_data or {}

    def json(self):
        return self._json


class _Client:
    """Fake httpx.AsyncClient that records every requested URL."""

    calls: list[str] = []

    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, **kw):
        _Client.calls.append(url)
        return _Resp(status_code=404)


@pytest.fixture(autouse=True)
def _reset_calls():
    _Client.calls = []
    yield


def test_all_four_urls_derive_from_the_single_repo_constant():
    repo = config.GITHUB_REPO
    assert "/" in repo and " " not in repo
    assert version.GITHUB_API_URL == f"https://api.github.com/repos/{repo}/contents/VERSION"
    assert version.GITHUB_RAW_URL == f"https://raw.githubusercontent.com/{repo}/main/VERSION"
    assert version.GITHUB_COMMITS_URL == f"https://api.github.com/repos/{repo}/commits"
    assert version.GITHUB_CHANGELOG_URL == f"https://raw.githubusercontent.com/{repo}/main/CHANGELOG.md"
    # Bridge downloads share the same single source instead of a second default.
    assert downloads.GITHUB_REPO is config.GITHUB_REPO


def test_default_repo_is_this_project_not_the_upstream_fork_origin():
    # Default (no GITHUB_REPO env) must name this project; a fork remnant
    # pointing at the upstream repo would silently show a foreign changelog.
    assert config.GITHUB_REPO.endswith("/agent-erp")


@pytest.mark.asyncio
async def test_version_check_requests_this_repo():
    with patch.object(version.httpx, "AsyncClient", _Client), \
         patch.object(version, "_get_github_token", return_value=""):
        assert await version._fetch_latest_version() is None
    assert _Client.calls == [f"https://raw.githubusercontent.com/{config.GITHUB_REPO}/main/VERSION"]


@pytest.mark.asyncio
async def test_changelog_requests_this_repo_for_markdown_and_commit_fallback():
    with patch.object(version.httpx, "AsyncClient", _Client), \
         patch.object(version, "_get_github_token", return_value="tok"):
        out = await version.get_changelog()
    assert out["format"] == "commits"
    repo = config.GITHUB_REPO
    assert _Client.calls == [
        f"https://raw.githubusercontent.com/{repo}/main/CHANGELOG.md",
        f"https://api.github.com/repos/{repo}/commits",
    ]
