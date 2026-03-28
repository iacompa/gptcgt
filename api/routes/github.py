"""GitHub Integration: OAuth, repo listing, and file access."""

import hashlib
import hmac
import logging
import re
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from api.config import settings
from api.database import get_pool
from src.core.endpoints import resolve_web_origin_url

logger = logging.getLogger(__name__)
router = APIRouter(tags=["github"])

GITHUB_OAUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API = "https://api.github.com"


class GitHubCallbackRequest(BaseModel):
    code: str
    state: str = ""  # F13: state is now required for CSRF validation


def _generate_oauth_state(user_id: str) -> str:
    """F13: Generate HMAC-signed state param for OAuth CSRF protection."""
    if not settings.jwt_secret:
        raise ValueError("JWT_SECRET is not configured. Cannot generate secure OAuth state.")
    secret = settings.jwt_secret.encode()
    return hmac.new(secret, user_id.encode(), hashlib.sha256).hexdigest()[:32]


def _encrypt_token(token: str) -> str:
    """F03: Encrypt GitHub access token before storage."""
    try:
        from api.services.encryption import encrypt_key
        return encrypt_key(token)
    except Exception as e:
        logger.error(f"Failed to encrypt GitHub token: {e}")
        raise ValueError("Encryption system failure. Aborting token storage.")


def _decrypt_token(stored: str) -> str:
    """F03: Decrypt stored GitHub access token."""
    if isinstance(stored, bytes):
        stored = stored.decode("utf-8")

    if stored.startswith("pt:"):
        return stored[3:]  # Legacy plaintext
    try:
        from api.services.encryption import decrypt_key
        return decrypt_key(stored)
    except Exception as e:
        # P1-02: Fail closed on decrypt errors; do not use raw fallback.
        logger.error(f"Failed to decrypt GitHub token: {e}")
        raise ValueError("Decryption failed. Token may be corrupted.")


def _repo_name_from_url(repo_url: str) -> str:
    """Normalize GitHub repo URLs into owner/repo form."""
    repo_url = repo_url.strip()
    ssh_match = re.match(r"^git@github\.com:(?P<name>[^/]+/[^/]+?)(?:\.git)?$", repo_url)
    if ssh_match:
        return ssh_match.group("name")

    https_match = re.match(r"^https://github\.com/(?P<name>[^/]+/[^/]+?)(?:\.git)?/?$", repo_url)
    if https_match:
        return https_match.group("name")

    raise ValueError(f"Unsupported GitHub repository URL: {repo_url}")


async def _complete_github_callback(request: Request, code: str, state: str) -> dict:
    """Exchange GitHub OAuth code for an access token and persist it for the authenticated user."""
    workos_user_id = getattr(request.state, "user_id", None)
    if not workos_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    nonce = request.cookies.get("gh_oauth_nonce")
    if not nonce:
        raise HTTPException(status_code=400, detail="Missing OAuth security cookie")

    expected_state = _generate_oauth_state(f"{workos_user_id}:{nonce}")
    if not state or not hmac.compare_digest(state, expected_state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state — possible CSRF or replay attack")

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
                "code": code,
            },
            headers={"Accept": "application/json"},
        )

        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="GitHub OAuth failed")

        data = resp.json()
        access_token = data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail=data.get("error_description", "No access token"))

        gh_user = await client.get(
            f"{GITHUB_API}/user",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        gh_profile = gh_user.json() if gh_user.status_code == 200 else {}

    encrypted_token = _encrypt_token(access_token)
    pool = get_pool()
    await pool.execute(
        """
        UPDATE users
        SET github_token = $1, github_username = $2
        WHERE workos_user_id = $3
        """,
        encrypted_token,
        gh_profile.get("login", ""),
        workos_user_id,
    )

    return {
        "status": "connected",
        "username": gh_profile.get("login"),
        "avatar_url": gh_profile.get("avatar_url"),
    }


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

    redirect_uri = str(request.url_for("github_callback_get"))
    scope = "repo read:user"

    # F13: Generate HMAC state for CSRF protection with random nonce (L8)
    import secrets

    nonce = secrets.token_hex(16)
    state = _generate_oauth_state(f"{workos_user_id}:{nonce}")

    auth_url = f"{GITHUB_OAUTH_URL}?client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}&state={state}"
    response = JSONResponse(content={"auth_url": auth_url})
    response.set_cookie(
        "gh_oauth_nonce",
        nonce,
        httponly=True,
        secure=settings.environment == "production",
        max_age=600,
    )
    return response


@router.get("/callback", name="github_callback_get")
async def github_callback_get(request: Request, code: str = "", state: str = ""):
    """Browser callback from GitHub OAuth; stores the token and redirects back to Hub."""
    await _complete_github_callback(request, code, state)
    base_url = getattr(settings, "base_url", "").rstrip("/") or resolve_web_origin_url().rstrip("/")
    redirect = RedirectResponse(url=f"{base_url}/dashboard/hub?github=connected", status_code=303)
    redirect.delete_cookie("gh_oauth_nonce")
    return redirect


@router.post("/callback")
async def github_callback(request: Request, body: GitHubCallbackRequest):
    """Exchange GitHub OAuth code for access token and store it."""
    return await _complete_github_callback(request, body.code, body.state)


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

    token = _decrypt_token(row["github_token"])
    repos_by_id: dict[int, dict] = {}
    async with httpx.AsyncClient() as client:
        for page in range(1, 11):
            resp = await client.get(
                f"{GITHUB_API}/user/repos",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "sort": "updated",
                    "per_page": 100,
                    "page": page,
                    "affiliation": "owner,collaborator,organization_member",
                },
            )

            if resp.status_code == 401:
                raise HTTPException(status_code=401, detail="GitHub token expired. Please reconnect.")
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail="Failed to fetch repos")

            batch = resp.json()
            if not batch:
                break

            for repo in batch:
                repos_by_id[repo["id"]] = repo

            if len(batch) < 100:
                break

    repos = sorted(repos_by_id.values(), key=lambda repo: repo.get("updated_at", ""), reverse=True)
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
            "clone_url": r.get("clone_url"),
        }
        for r in repos
    ]


# ------------------------------------------------------------------ #
#  File tree + content                                                 #
# ------------------------------------------------------------------ #


@router.get("/tree/{owner}/{repo}")
async def get_repo_tree(request: Request, owner: str, repo: str, branch: Optional[str] = None):
    """Get the file tree for a repository."""
    import re
    if not re.match(r"^[A-Za-z0-9_.-]+$", owner) or not re.match(r"^[A-Za-z0-9_.-]+$", repo):
        raise HTTPException(status_code=400, detail="Invalid GitHub owner or repo name")

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
            headers={"Authorization": f"Bearer {_decrypt_token(row['github_token'])}"},
            params={"recursive": "1"},
        )

        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="Failed to fetch tree")

        data = resp.json()

    tree = data.get("tree", [])
    items = [
        {
            "path": item["path"],
            "type": item["type"],  # "blob" or "tree"
            "size": item.get("size", 0),
            "sha": item["sha"],
        }
        for item in tree
        if item["type"] in ("blob", "tree")
    ]
    return {
        "items": items,
        "truncated": bool(data.get("truncated")),
    }


@router.get("/file/{owner}/{repo}/{path:path}")
async def get_file_content(request: Request, owner: str, repo: str, path: str, branch: Optional[str] = None):
    """Get the content of a single file from a repository."""
    import re
    if not re.match(r"^[A-Za-z0-9_.-]+$", owner) or not re.match(r"^[A-Za-z0-9_.-]+$", repo):
        raise HTTPException(status_code=400, detail="Invalid GitHub owner or repo name")

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
                "Authorization": f"Bearer {_decrypt_token(row['github_token'])}",
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
