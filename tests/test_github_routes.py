from types import SimpleNamespace

import pytest

from api.routes import github as github_routes


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_list_repos_paginates_and_includes_org_memberships(monkeypatch):
    page_calls = []

    class FakePool:
        async def fetchrow(self, query, *args):
            return {"github_token": "encrypted"}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None, params=None):
            page_calls.append(params)
            page = params["page"]
            if page == 1:
                return _FakeResponse(
                    [
                        {
                            "id": i,
                            "name": f"repo-{i}",
                            "full_name": f"owner/repo-{i}",
                            "description": None,
                            "language": "Python",
                            "private": False,
                            "updated_at": f"2026-03-{(i % 28) + 1:02d}T00:00:00Z",
                            "html_url": f"https://github.com/owner/repo-{i}",
                            "default_branch": "main",
                            "stargazers_count": i,
                            "clone_url": f"https://github.com/owner/repo-{i}.git",
                        }
                        for i in range(1, 101)
                    ]
                )
            if page == 2:
                return _FakeResponse(
                    [
                        {
                            "id": 101,
                            "name": "repo-101",
                            "full_name": "org/repo-101",
                            "description": "org repo",
                            "language": "TypeScript",
                            "private": True,
                            "updated_at": "2026-03-31T00:00:00Z",
                            "html_url": "https://github.com/org/repo-101",
                            "default_branch": "main",
                            "stargazers_count": 0,
                            "clone_url": "https://github.com/org/repo-101.git",
                        }
                    ]
                )
            return _FakeResponse([])

    monkeypatch.setattr("api.routes.github.get_pool", lambda: FakePool())
    monkeypatch.setattr("api.routes.github._decrypt_token", lambda value: "gh-token")
    monkeypatch.setattr("api.routes.github.httpx.AsyncClient", lambda: FakeClient())

    request = SimpleNamespace(state=SimpleNamespace(user_id="workos-user"))
    repos = await github_routes.list_repos(request)

    assert len(repos) == 101
    assert page_calls[0]["affiliation"] == "owner,collaborator,organization_member"
    assert repos[0]["full_name"] == "org/repo-101"


@pytest.mark.asyncio
async def test_get_repo_tree_returns_truncation_metadata(monkeypatch):
    class FakePool:
        async def fetchrow(self, query, *args):
            return {"github_token": "encrypted"}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None, params=None):
            return _FakeResponse(
                {
                    "tree": [
                        {"path": "src", "type": "tree", "sha": "abc"},
                        {"path": "src/app.py", "type": "blob", "sha": "def", "size": 42},
                    ],
                    "truncated": True,
                }
            )

    monkeypatch.setattr("api.routes.github.get_pool", lambda: FakePool())
    monkeypatch.setattr("api.routes.github._decrypt_token", lambda value: "gh-token")
    monkeypatch.setattr("api.routes.github.httpx.AsyncClient", lambda: FakeClient())

    request = SimpleNamespace(state=SimpleNamespace(user_id="workos-user"))
    tree = await github_routes.get_repo_tree(request, "octocat", "hello-world", "main")

    assert tree["truncated"] is True
    assert tree["items"][0]["path"] == "src"
    assert tree["items"][1]["size"] == 42
