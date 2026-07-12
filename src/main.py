#!/usr/bin/env python3
import base64
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from repository_blame.config import load_config, parse_optional_limit
from repository_blame.git_blame import get_language, run
from repository_blame.logging_utils import warn
from repository_blame.stats import collect_stats
from repository_blame.svg_renderer import generate_svg, safe_id
from repository_blame.users import parse_users


REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REF_PATTERN = re.compile(r"^[A-Za-z0-9._/-]+$")


def parse_minor_contributors_limit(raw_value, default=22):
    return parse_optional_limit(raw_value, default=default)


def parse_show_contributors_limit(raw_value, default=10):
    return parse_optional_limit(raw_value, default=default)


def normalize_repository(raw_repository, default_repository):
    value = (raw_repository or "").strip()

    if not value:
        value = (default_repository or "").strip()

    value = re.sub(r"^https://github\.com/", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\.git$", "", value)
    value = value.strip("/")

    if not REPOSITORY_PATTERN.fullmatch(value):
        raise SystemExit(
            f"Invalid repository format: {raw_repository or default_repository!r}; "
            "expected owner/name"
        )

    return value


def clone_target_repository(repository, branch, token):
    temp_root = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir()))
    target_dir = Path(
        tempfile.mkdtemp(prefix=f"repositoryblame-{safe_id(repository)}-", dir=temp_root)
    )

    clone_url = f"https://github.com/{repository}.git"

    env = os.environ.copy()
    if token:
        credentials = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env.update(
            {
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
                "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {credentials}",
                "GIT_TERMINAL_PROMPT": "0",
            }
        )

    cmd = ["git", "clone", "--no-tags"]

    if branch:
        cmd.extend(["--branch", branch])

    cmd.extend([clone_url, str(target_dir)])

    warn(f"cloning target repository: {repository}")
    run(cmd, env=env)

    return target_dir


def checkout_current_repository_ref(repo_dir, ref):
    ref = (ref or "").strip()
    if not ref:
        return

    if ref.startswith("-") or ".." in ref or not REF_PATTERN.fullmatch(ref):
        raise SystemExit(f"Invalid branch/ref: {ref}")

    warn(f"checking out current repository ref: {ref}")

    try:
        run(["git", "checkout", ref], cwd=repo_dir)
    except subprocess.CalledProcessError:
        run(["git", "fetch", "origin", ref], cwd=repo_dir)
        run(["git", "checkout", "FETCH_HEAD"], cwd=repo_dir)


def prepare_target_repository(target_repository, target_branch, token, workflow_repository=None):
    if workflow_repository is None:
        workflow_repository = os.environ.get("GITHUB_REPOSITORY", "")
    repository = normalize_repository(target_repository, workflow_repository)
    target_branch = (target_branch or "").strip()

    if target_branch and (
        target_branch.startswith("-")
        or ".." in target_branch
        or not REF_PATTERN.fullmatch(target_branch)
    ):
        raise SystemExit(f"Invalid branch/ref: {target_branch}")

    if (target_repository or "").strip():
        repo_dir = clone_target_repository(repository, target_branch, token)
    else:
        repo_dir = Path.cwd()
        checkout_current_repository_ref(repo_dir, target_branch)

    sha = run(["git", "rev-parse", "--short", "HEAD"], cwd=repo_dir).strip()
    warn(f"analyzing repository: {repository} ({sha})")

    return repo_dir, repository

def main():
    config = load_config()
    repo_dir, target_repository = prepare_target_repository(
        config.repository, config.branch, config.token, config.repo
    )
    alias_map, canonical_map = parse_users(config.raw_users)
    # Commit identity lookups must use the repository being analyzed, rather
    # than the repository in which this workflow happens to run.
    config = replace(config, repo=target_repository)
    stats, total_lines = collect_stats(config, alias_map, canonical_map, repo_dir)

    generate_svg(
        stats,
        total_lines,
        config.output,
        config.width,
        config.title,
        config.min_percent,
        config.minor_contributors_limit,
        config.show_contributors_limit,
        target_repository,
    )
    warn(f"generated {config.output}")


if __name__ == "__main__":
    main()
