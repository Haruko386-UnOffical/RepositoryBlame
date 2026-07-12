import fnmatch
import re
import subprocess
from pathlib import Path

from .constants import LANG_BY_EXT, NAME_BY_FILENAME
from .logging_utils import warn


def run(cmd, cwd=None, env=None):
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout


def get_language(path):
    name = Path(path).name
    if name in NAME_BY_FILENAME:
        return NAME_BY_FILENAME[name]

    lower_name = name.lower()
    if lower_name == "dockerfile":
        return NAME_BY_FILENAME["Dockerfile"]

    ext = Path(path).suffix.lower()
    return LANG_BY_EXT.get(ext)


def should_ignore(path, patterns):
    normalized = path.replace("\\", "/")
    basename = Path(normalized).name

    for pattern in patterns:
        pattern = pattern.strip().replace("\\", "/")
        if not pattern:
            continue
        if fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch(basename, pattern):
            return True
    return False


def list_files(ignore_patterns, repo_dir="."):
    raw = run(["git", "ls-files", "-z"], cwd=repo_dir)
    result = []

    for file in raw.split("\0"):
        if not file:
            continue
        if should_ignore(file, ignore_patterns):
            continue
        if get_language(file) is None:
            continue
        if not (Path(repo_dir) / file).is_file():
            continue
        result.append(file)

    return result


def blame_file(path, repo_dir="."):
    """
    Return non-empty blamed lines as tuples:
      (commit_sha, fallback_author_name, fallback_author_email)
    """
    try:
        output = run(["git", "blame", "--line-porcelain", "--", path], cwd=repo_dir)
    except subprocess.CalledProcessError as exc:
        warn(f"skip blame failed file: {path}; {exc.stderr.strip()}")
        return []

    result = []
    current_sha = None
    current_author = None
    current_email = None
    header_re = re.compile(r"^([0-9a-f]{40})\s+")

    for line in output.splitlines():
        header = header_re.match(line)
        if header:
            current_sha = header.group(1)
            current_author = None
            current_email = None
            continue

        if line.startswith("author "):
            current_author = line[len("author ") :]
        elif line.startswith("author-mail "):
            current_email = line[len("author-mail ") :]
        elif line.startswith("\t"):
            content = line[1:]
            if content.strip() and current_sha:
                result.append((current_sha, current_author, current_email))

    return result
