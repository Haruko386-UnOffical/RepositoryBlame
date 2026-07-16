from collections import defaultdict

from .git_blame import blame_file, get_language, list_files
from .github_api import fetch_avatar_by_login_base64, resolve_commit_identity
from .logging_utils import warn
from .users import normalize_user


def new_stats_map():
    return defaultdict(lambda: {"total": 0, "langs": defaultdict(int), "avatar": None})


def collect_stats(config, alias_map, canonical_map, repo_dir="."):
    stats = new_stats_map()
    total_lines = 0
    commit_cache = {}

    files = list_files(config.ignore_patterns, repo_dir)
    warn(f"found {len(files)} supported files")

    for file in files:
        lang = get_language(file)
        if lang is None:
            continue

        for sha, author, email in blame_file(file, repo_dir):
            login, avatar = resolve_commit_identity(config.repo, sha, config.token, commit_cache)
            if login:
                user = canonical_map.get(login.lower(), login)
            else:
                user = normalize_user(author, email, alias_map, canonical_map)

            stats[user]["total"] += 1
            stats[user]["langs"][lang] += 1
            total_lines += 1

            if avatar and not stats[user].get("avatar"):
                stats[user]["avatar"] = avatar

    # Fallback avatar path for users resolved through aliases / noreply parsing.
    for user in list(stats.keys()):
        if not stats[user].get("avatar"):
            stats[user]["avatar"] = fetch_avatar_by_login_base64(user)

    return stats, total_lines
