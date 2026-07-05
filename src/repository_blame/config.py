import os
from dataclasses import dataclass
from typing import Optional

from .constants import DEFAULT_IGNORE


@dataclass(frozen=True)
class AppConfig:
    output: str
    title: str
    repo: str
    token: str
    width: int
    min_percent: float
    minor_contributors_limit: Optional[int]
    show_contributors_limit: Optional[int]
    ignore_patterns: list[str]
    raw_users: str


def parse_optional_limit(raw_value, default=10):
    value = str(raw_value or "").strip().lower()
    if value == "":
        return default

    if value in ("all", "full", "*"):
        return None

    try:
        return max(int(value), 0)
    except ValueError:
        return default


def parse_int(raw_value, default):
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return default


def parse_float(raw_value, default):
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return default


def load_config(environ=None):
    environ = environ or os.environ
    raw_ignore = environ.get("INPUT_IGNORE", "")

    return AppConfig(
        output=environ.get("INPUT_OUTPUT", "dist/code-stats.svg"),
        title=environ.get("INPUT_TITLE", "Code Stats"),
        repo=environ.get("GITHUB_REPOSITORY", ""),
        token=environ.get("INPUT_GITHUB_TOKEN") or environ.get("GITHUB_TOKEN", ""),
        width=parse_int(environ.get("INPUT_WIDTH", "900"), 900),
        min_percent=parse_float(environ.get("INPUT_MIN_PERCENT", "0.8"), 0.8),
        minor_contributors_limit=parse_optional_limit(
            environ.get("INPUT_MINOR_CONTRIBUTORS_LIMIT", 22), default=22
        ),
        show_contributors_limit=parse_optional_limit(
            environ.get("INPUT_SHOW_CONTRIBUTORS_LIMIT", 10), default=10
        ),
        ignore_patterns=DEFAULT_IGNORE
        + [line.strip() for line in raw_ignore.splitlines() if line.strip()],
        raw_users=environ.get("INPUT_USERS", ""),
    )
