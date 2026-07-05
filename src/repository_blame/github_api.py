import base64
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .logging_utils import warn


def github_api_get_json(url, token):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "code-stats-card",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = Request(url, headers=headers)
    with urlopen(req, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_url_base64(url, token=None):
    headers = {"User-Agent": "code-stats-card"}
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, headers=headers)
    with urlopen(req, timeout=12) as response:
        data = response.read()
    return "data:image/png;base64," + base64.b64encode(data).decode("utf-8")


def resolve_commit_identity(repo, sha, token, commit_cache):
    """
    Resolve a commit SHA to a GitHub account through GitHub commit API.
    Returns (login, avatar_data_uri) or (None, None).
    """
    if not repo or not sha:
        return None, None
    if sha in commit_cache:
        return commit_cache[sha]

    url = f"https://api.github.com/repos/{repo}/commits/{sha}"
    try:
        data = github_api_get_json(url, token)
        account = data.get("author") or data.get("committer")
        if not account:
            commit_cache[sha] = (None, None)
            return commit_cache[sha]

        login = account.get("login")
        avatar = None
        avatar_url = account.get("avatar_url")
        if avatar_url:
            try:
                avatar = fetch_url_base64(avatar_url, token=None)
            except (HTTPError, URLError, TimeoutError, ValueError):
                avatar = None

        commit_cache[sha] = (login, avatar)
        return commit_cache[sha]
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        warn(f"commit API resolve failed for {sha[:7]}: {exc}")
        commit_cache[sha] = (None, None)
        return commit_cache[sha]


def looks_like_github_user(user):
    return bool(re.match(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$", user or ""))


def fetch_avatar_by_login_base64(username):
    if not looks_like_github_user(username):
        return None

    try:
        return fetch_url_base64(f"https://github.com/{username}.png?size=96")
    except (HTTPError, URLError, TimeoutError, ValueError):
        return None
