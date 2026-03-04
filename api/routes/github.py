"""GitHub Integration: OAuth, repo listing, and file access."""

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.config import settings
from api.database import get_pool

logger = logging.getLogger(__name__)
router = APIRouter(tags=["github"])

GITHUB_OAUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API = "https://api.github.com"


class GitHubCallbackRequest(BaseModel):
    code: str


# ------------------------------------------------------------------ #
#  OAuth                                                               #
# ------------------------------------------------------------------ #


@router.get("/connect")
async def github_connect(request: Request):
    """Redirect the user to GitHub OAuth."""
    workos_user_id = getattr(request.state, "user_id", None)
    if not workos_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    client_id = getattr(settings, "github_client_id", None)
    if not client_id:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured")

    redirect_uri = f"{getattr(settings, 'base_url', 'https://gptcgt.ai')}/api/github/callback"
    scope = "repo read:user"

    auth_url = (
        f"{GITHUB_OAUTH_URL}?client_id={client_id}"
        f"&redirect_uri={redirect_uri}&scope={scope}&state={workos_user_id}"
    )
    return {"auth_url": auth_url}


@router.post("/callback")
async def github_callback(request: Request, body: GitHubCallbackRequest):
    """Exchange GitHub OAuth code for access token and store it."""
    workos_user_id = getattr(request.state, "user_id", None)
    if not workos_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    client_id = getattr(settings, "github_client_id", None)
    client_secret = getattr(settings, "github_client_secret", None)
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": body.code,
            },
            headers={"Accept": "application/json"},
        )

        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="GitHub OAuth failed")

        data = resp.json()
        access_token = data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail=data.get("error_description", "No access token"))

        # Get GitHub user profile
        gh_user = await client.get(
            f"{GITHUB_API}/user",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        gh_profile = gh_user.json() if gh_user.status_code == 200 else {}

    # Store token in database
    pool = get_pool()
    await pool.execute(
        """
        UPDATE users
        SET github_token = $1, github_username = $2
        WHERE workos_user_id = $3
        """,
        access_token,
        gh_profile.get("login", ""),
        workos_user_id,
    )

    return {
        "status": "connected",
        "username": gh_profile.get("login"),
        "avatar_url": gh_profile.get("avatar_url"),
    }


# ------------------------------------------------------------------ #
#  Repo listing                                                        #
# ------------------------------------------------------------------ #


@router.get("/repos")
async def list_repos(request: Request):
    """List the user's GitHub repositories."""
    workos_user_id = getattr(request.state, "user_id", None)
    if not workos_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT github_token FROM users WHERE workos_user_id = $1",
        workos_user_id,
    )
    if not row or not row["github_token"]:
        raise HTTPException(status_code=400, detail="GitHub not connected")

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API}/user/repos",
            headers={"Authorization": f"Bearer {row['github_token']}"},
            params={"sort": "updated", "per_page": 50, "type": "owner"},
        )

        if resp.status_code == 401:
            raise HTTPException(status_code=401, detail="GitHub token expired. Please reconnect.")
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to fetch repos")

        repos = resp.json()

    return [
        {
            "id": r["id"],
            "name": r["name"],
            "full_name": r["full_name"],
            "description": r["description"],
            "language": r["language"],
            "private": r["private"],
            "updated_at": r["updated_at"],
            "html_url": r["html_url"],
            "default_branch": r["default_branch"],
            "stargazers_count": r["stargazers_count"],
        }
        for r in repos
    ]


# ------------------------------------------------------------------ #
#  File tree + content                                                 #
# ------------------------------------------------------------------ #


@router.get("/tree/{owner}/{repo}")
async def get_repo_tree(request: Request, owner: str, repo: str, branch: Optional[str] = None):
    """Get the file tree for a repository."""
    workos_user_id = getattr(request.state, "user_id", None)
    if not workos_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT github_token FROM users WHERE workos_user_id = $1",
        workos_user_id,
    )
    if not row or not row["github_token"]:
        raise HTTPException(status_code=400, detail="GitHub not connected")

    ref = branch or "main"
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{ref}",
            headers={"Authorization": f"Bearer {row['github_token']}"},
            params={"recursive": "1"},
        )

        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="Failed to fetch tree")

        data = resp.json()

    tree = data.get("tree", [])
    return [
        {
            "path": item["path"],
            "type": item["type"],  # "blob" or "tree"
            "size": item.get("size", 0),
            "sha": item["sha"],
        }
        for item in tree
        if item["type"] in ("blob", "tree")
    ][:500]  # Cap to 500 items


@router.get("/file/{owner}/{repo}/{path:path}")
async def get_file_content(
    request: Request, owner: str, repo: str, path: str, branch: Optional[str] = None
):
    """Get the content of a single file from a repository."""
    workos_user_id = getattr(request.state, "user_id", None)
    if not workos_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT github_token FROM users WHERE workos_user_id = $1",
        workos_user_id,
    )
    if not row or not row["github_token"]:
        raise HTTPException(status_code=400, detail="GitHub not connected")

    ref = branch or "main"
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
            headers={
                "Authorization": f"Bearer {row['github_token']}",
                "Accept": "application/vnd.github.v3.raw",
            },
            params={"ref": ref},
        )

        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="File not found")
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="Failed to fetch file")

        # Cap file size at 1MB
        content = resp.text[:1_000_000]

    return {"path": path, "content": content}


@router.get("/status")
async def github_status(request: Request):
    """Check if the user has GitHub connected."""
    workos_user_id = getattr(request.state, "user_id", None)
    if not workos_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT github_token, github_username FROM users WHERE workos_user_id = $1",
        workos_user_id,
    )

    if not row or not row["github_token"]:
        return {"connected": False}

    return {
        "connected": True,
        "username": row["github_username"],
    }
