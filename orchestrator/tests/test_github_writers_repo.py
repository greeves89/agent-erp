"""Issue #48: the two code paths that WRITE to GitHub must target THIS repository.

After #30 the read-only paths (version check, changelog, bridge downloads)
derive their URLs from app.config.GITHUB_REPO. Two writers still carried a
hard-coded copy of the upstream project's path: the self-test service (creates
and auto-closes "[Self-Test]" issues) and the feedback endpoint (turns a
feedback entry into an issue). With a token that has write access upstream,
operational findings of this deployment would land in a foreign tracker.

These tests pin the repository at the CALL SITE — the URL and the search query
actually handed to httpx — not just the constant, so a stray literal cannot
creep back in unnoticed. The GitHub token lookup is stubbed; the tests are
about where the request goes, not about how the token is obtained.
"""

import os
import subprocess
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app import config
from app.api import feedback as feedback_api
from app.models.feedback import FeedbackCategory, FeedbackStatus
from app.services import self_test_service
from app.services.self_test_service import SelfTestService
from app.services.self_test_service import TestResult as _TestResult  # noqa: N814 (pytest must not collect it)

UPSTREAM_LITERAL = "greeves89/AI-Employee"


class _Resp:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.text = text

    def json(self):
        return self._json


class _Client:
    """Fake httpx.AsyncClient recording every call as (method, url, params, json)."""

    calls: list[tuple] = []
    get_responses: list[_Resp] = []

    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, params=None, **kw):
        _Client.calls.append(("GET", url, params, None))
        if _Client.get_responses:
            return _Client.get_responses.pop(0)
        return _Resp(200, {"total_count": 0, "items": []})

    async def post(self, url, json=None, **kw):
        _Client.calls.append(("POST", url, None, json))
        return _Resp(201, {"html_url": f"https://example.invalid/{url.rsplit('/', 1)[-1]}/1", "number": 1})

    async def patch(self, url, json=None, **kw):
        _Client.calls.append(("PATCH", url, None, json))
        return _Resp(200, {})


class _Result:
    def __init__(self, obj):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj


class _Db:
    """Minimal AsyncSession stand-in: every SELECT yields the same object."""

    def __init__(self, obj):
        self._obj = obj

    async def execute(self, *a, **kw):
        return _Result(self._obj)

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass


@pytest.fixture(autouse=True)
def _reset_client():
    _Client.calls = []
    _Client.get_responses = []
    yield


@pytest.fixture
def _stub_selftest_token(monkeypatch):
    # The service resolves its token via ``app.security.encryption.decrypt_value``;
    # provide that name so the call reaches the GitHub request that we inspect.
    mod = types.ModuleType("app.security.encryption")
    mod.decrypt_value = lambda value: "tok"
    monkeypatch.setitem(sys.modules, "app.security.encryption", mod)
    return _Db(SimpleNamespace(access_token="enc"))


def _failed(name: str) -> _TestResult:
    r = _TestResult(name, "api")
    r.status = "failed"
    r.error = "boom"
    return r


def _passed(name: str) -> _TestResult:
    r = _TestResult(name, "api")
    r.status = "passed"
    return r


@pytest.mark.asyncio
async def test_self_test_issue_creation_targets_this_repo(_stub_selftest_token):
    repo = config.GITHUB_REPO
    with patch.object(self_test_service.httpx, "AsyncClient", _Client):
        created = await SelfTestService()._create_github_issues(
            _stub_selftest_token, [_failed("t_one")], test_run_id=7
        )
    assert created == 1
    methods_urls = [(m, u) for m, u, _, _ in _Client.calls]
    assert methods_urls == [
        ("GET", "https://api.github.com/search/issues"),
        ("POST", f"https://api.github.com/repos/{repo}/issues"),
    ]
    search_q = _Client.calls[0][2]["q"]
    assert search_q.startswith(f"repo:{repo} ")
    assert UPSTREAM_LITERAL not in search_q


@pytest.mark.asyncio
async def test_self_test_recurring_failure_comments_in_this_repo(_stub_selftest_token):
    repo = config.GITHUB_REPO
    _Client.get_responses = [_Resp(200, {"total_count": 1, "items": [{"number": 42}]})]
    with patch.object(self_test_service.httpx, "AsyncClient", _Client):
        created = await SelfTestService()._create_github_issues(
            _stub_selftest_token, [_failed("t_one")], test_run_id=8
        )
    assert created == 0  # existing issue -> comment, no new issue
    assert [(m, u) for m, u, _, _ in _Client.calls][1] == (
        "POST", f"https://api.github.com/repos/{repo}/issues/42/comments"
    )


@pytest.mark.asyncio
async def test_self_test_auto_close_targets_this_repo(_stub_selftest_token):
    repo = config.GITHUB_REPO
    _Client.get_responses = [
        _Resp(200, {"items": [{"title": "[Self-Test] t_one", "number": 5}]})
    ]
    with patch.object(self_test_service.httpx, "AsyncClient", _Client):
        closed = await SelfTestService()._auto_close_fixed_issues(
            _stub_selftest_token, [_passed("t_one")]
        )
    assert closed == 1
    assert _Client.calls[0][2]["q"].startswith(f"repo:{repo} ")
    assert [(m, u) for m, u, _, _ in _Client.calls][1:] == [
        ("POST", f"https://api.github.com/repos/{repo}/issues/5/comments"),
        ("PATCH", f"https://api.github.com/repos/{repo}/issues/5"),
    ]


class _OAuth:
    async def get_valid_token(self, provider):
        assert provider == "github"
        return "tok"


def _feedback_row():
    return SimpleNamespace(
        id=1, user_id="u1", user_name="m.mustermann", title="Knopf tut nichts",
        description="", category=FeedbackCategory.BUG, status=FeedbackStatus.PENDING,
        admin_notes=None, github_issue_url=None, created_at=None, updated_at=None,
    )


@pytest.mark.asyncio
async def test_feedback_issue_targets_this_repo_when_no_setting_is_present():
    repo = config.GITHUB_REPO
    # Settings carries no github_repo field today -> the fallback must be THIS repo.
    assert not getattr(config.settings, "github_repo", "")
    with patch("httpx.AsyncClient", _Client):
        out = await feedback_api.create_github_issue(
            1, user=None, db=_Db(_feedback_row()), service=_OAuth()
        )
    assert out["issue_number"] == 1
    assert [(m, u) for m, u, _, _ in _Client.calls] == [
        ("POST", f"https://api.github.com/repos/{repo}/issues")
    ]


@pytest.mark.asyncio
async def test_feedback_issue_honours_an_explicit_setting(monkeypatch):
    # Settings is a pydantic model without that field; swap the object the
    # endpoint imports at call time for one that carries an explicit value.
    monkeypatch.setattr(config, "settings", SimpleNamespace(github_repo="someone/elsewhere"))
    with patch("httpx.AsyncClient", _Client):
        await feedback_api.create_github_issue(
            1, user=None, db=_Db(_feedback_row()), service=_OAuth()
        )
    assert _Client.calls[0][1] == "https://api.github.com/repos/someone/elsewhere/issues"


def _github_repo_in_fresh_process(github_repo: str | None) -> str:
    """Read config.GITHUB_REPO in a clean interpreter with a controlled env.

    The value is fixed at import time, so within this test process it already
    reflects the caller's environment: a developer running the suite with
    GITHUB_REPO set would see the default test fail although the override
    works. Only a fresh process can observe default and override separately.
    """
    env = {k: v for k, v in os.environ.items() if k != "GITHUB_REPO"}
    if github_repo is not None:
        env["GITHUB_REPO"] = github_repo
    out = subprocess.run(
        [sys.executable, "-c", "from app import config; print(config.GITHUB_REPO)"],
        env=env, capture_output=True, text=True,
        cwd=str(Path(__file__).resolve().parent.parent), check=True,
    )
    return out.stdout.strip().splitlines()[-1]


def test_default_repo_is_this_project_not_the_upstream_fork_origin():
    repo = _github_repo_in_fresh_process(None)
    assert repo.endswith("/agent-erp")
    assert UPSTREAM_LITERAL not in repo


def test_env_override_replaces_the_default():
    # A fork sets GITHUB_REPO once; the writers above derive their URLs from
    # the imported constant, so the override must land there exactly.
    assert _github_repo_in_fresh_process("example/mirror") == "example/mirror"
