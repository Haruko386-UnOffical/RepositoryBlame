#!/usr/bin/env python3
import base64
import fnmatch
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LANG_BY_EXT = {
    ".go": ("Go", "#00ADD8"),
    ".py": ("Python", "#3572A5"),
    ".ipynb": ("Jupyter Notebook", "#DA5B0B"),
    ".js": ("JavaScript", "#F1E05A"),
    ".mjs": ("JavaScript", "#F1E05A"),
    ".cjs": ("JavaScript", "#F1E05A"),
    ".ts": ("TypeScript", "#3178C6"),
    ".tsx": ("TypeScript", "#3178C6"),
    ".jsx": ("JavaScript", "#F1E05A"),
    ".vue": ("Vue", "#41B883"),
    ".java": ("Java", "#B07219"),
    ".kt": ("Kotlin", "#A97BFF"),
    ".kts": ("Kotlin", "#A97BFF"),
    ".c": ("C", "#555555"),
    ".h": ("C/C++ Header", "#555555"),
    ".cpp": ("C++", "#F34B7D"),
    ".cc": ("C++", "#F34B7D"),
    ".cxx": ("C++", "#F34B7D"),
    ".hpp": ("C++", "#F34B7D"),
    ".cs": ("C#", "#178600"),
    ".rs": ("Rust", "#DEA584"),
    ".html": ("HTML", "#E34C26"),
    ".htm": ("HTML", "#E34C26"),
    ".css": ("CSS", "#563D7C"),
    ".scss": ("SCSS", "#C6538C"),
    ".sass": ("Sass", "#A53B70"),
    ".less": ("Less", "#1D365D"),
    ".sh": ("Shell", "#89E051"),
    ".bash": ("Shell", "#89E051"),
    ".zsh": ("Shell", "#89E051"),
    ".ps1": ("PowerShell", "#012456"),
    ".yaml": ("YAML", "#CB171E"),
    ".yml": ("YAML", "#CB171E"),
    ".json": ("JSON", "#292929"),
    ".toml": ("TOML", "#9C4221"),
    ".xml": ("XML", "#0060AC"),
    ".md": ("Markdown", "#083FA1"),
    ".tex": ("TeX", "#3D6117"),
    ".r": ("R", "#198CE7"),
    ".rb": ("Ruby", "#701516"),
    ".php": ("PHP", "#4F5D95"),
    ".swift": ("Swift", "#F05138"),
    ".dart": ("Dart", "#00B4AB"),
    ".lua": ("Lua", "#000080"),
    ".gd": ("GDScript", "#355570"),
    ".dockerfile": ("Dockerfile", "#384D54"),
}

NAME_BY_FILENAME = {
    "Dockerfile": ("Dockerfile", "#384D54"),
    "Makefile": ("Makefile", "#427819"),
    "CMakeLists.txt": ("CMake", "#DA3434"),
}

DEFAULT_IGNORE = [
    ".git/**",
    ".github/**",
    "node_modules/**",
    "vendor/**",
    "dist/**",
    "build/**",
    "target/**",
    "coverage/**",
    ".next/**",
    ".nuxt/**",
    ".vite/**",
    ".venv/**",
    "venv/**",
    "__pycache__/**",
    "*.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "Cargo.lock",
    "go.sum",
    "*.min.js",
    "*.min.css",
    "*.map",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.webp",
    "*.svg",
    "*.ico",
    "*.pdf",
    "*.zip",
    "*.tar",
    "*.gz",
    "*.7z",
    "*.mp4",
    "*.mov",
    "*.avi",
    "*.mp3",
    "*.wav",
    "*.onnx",
    "*.pt",
    "*.pth",
]


def run(cmd):
    return subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout


def warn(message):
    print(f"[code-stats-card] {message}", file=sys.stderr)


def escape(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def safe_id(value):
    return re.sub(r"[^a-zA-Z0-9_-]", "-", str(value))


def parse_users(raw):
    """
    Optional fallback aliases.

    Input format:
      GitHubUser=alias,email,name
      AnotherUser=another@example.com,Another Name
    """
    mapping = {}
    canonical = {}

    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        github, aliases = line.split("=", 1)
        github = github.strip()
        if not github:
            continue

        canonical[github.lower()] = github
        mapping[github.lower()] = github

        for alias in aliases.split(","):
            alias = alias.strip().strip("<>")
            if alias:
                mapping[alias.lower()] = github

    return mapping, canonical


def parse_github_user_from_email(email):
    email = (email or "").strip().strip("<>")
    match = re.match(r"(?:\d+\+)?([^@]+)@users\.noreply\.github\.com$", email, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def normalize_user(author, email, alias_map, canonical_map):
    author = (author or "").strip()
    email = (email or "").strip().strip("<>")

    author_key = author.lower()
    email_key = email.lower()

    if email_key in alias_map:
        return alias_map[email_key]

    if author_key in alias_map:
        return alias_map[author_key]

    github_user = parse_github_user_from_email(email)
    if github_user:
        return canonical_map.get(github_user.lower(), github_user)

    return author or email or "Unknown"


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


def list_files(ignore_patterns):
    raw = run(["git", "ls-files", "-z"])
    files = raw.split("\0")
    result = []

    for file in files:
        if not file:
            continue
        if should_ignore(file, ignore_patterns):
            continue
        if get_language(file) is None:
            continue
        if not Path(file).is_file():
            continue
        result.append(file)

    return result


def blame_file(path):
    """
    Return non-empty blamed lines as tuples:
      (commit_sha, fallback_author_name, fallback_author_email)
    """
    try:
        output = run(["git", "blame", "--line-porcelain", "--", path])
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
            current_author = line[len("author "):]
        elif line.startswith("author-mail "):
            current_email = line[len("author-mail "):]
        elif line.startswith("\t"):
            content = line[1:]
            if content.strip() and current_sha:
                result.append((current_sha, current_author, current_email))

    return result

def parse_minor_contributors_limit(raw_value, default=22):
    value = str(raw_value or "").strip().lower()
    if value == "":
        return default
    
    if value in ("all", "full", "*"):
        return None  # No limit
    
    try:
        parsed = int(value)
        return max(parsed, 0)
    except ValueError:
        return default

def parse_show_contributors_limit(raw_value, default=10):
    value = str(raw_value or "").strip().lower()
    if value == "":
        return default
    
    if value in ("all", "full", "*"):
        return None # No limit
    
    try:
        parsed = int(value)
        return max(parsed, 0)
    except ValueError:
        return default

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
        avatar_url = account.get("avatar_url")
        avatar = None
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
        url = f"https://github.com/{username}.png?size=96"
        return fetch_url_base64(url)
    except (HTTPError, URLError, TimeoutError, ValueError):
        return None


def lang_segments(lang_counts, total, bar_width):
    items = sorted(lang_counts.items(), key=lambda x: x[1], reverse=True)
    segments = []
    used = 0.0

    for idx, (lang, count) in enumerate(items):
        if idx == len(items) - 1:
            width = max(0.0, bar_width - used)
        else:
            width = bar_width * count / total if total else 0.0
            used += width
        if width > 0.1:
            segments.append((lang, count, width))

    return segments

OTHER_COLOR = "#d1d7de"
TRACK_COLOR = "#eff2f5"

def format_pct(part, total):
    if total <= 0:
        return "0.0%"
    return f"{part / total * 100:.1f}%"

def approx_text_width(text, font_size=13, bold=False):
    factor = 0.62 if bold else 0.56
    return int(len(text) * font_size * factor)

def summarize_languages(lang_counter, total, max_items=6, min_percent=2.0):
    items = sorted(lang_counter.items(), key=lambda x: x[1], reverse=True)

    shown = []
    other_count = 0

    for (lang_name, color), count in items:
        pct = count / total * 100 if total else 0
        if len(shown) < max_items and pct >= min_percent:
            shown.append((lang_name, color, count, pct))
        else:
            other_count += count

    if other_count > 0:
        shown.append(("Other", OTHER_COLOR, other_count, other_count / total * 100 if total else 0))

    if not shown and items:
        top = items[:max_items]
        shown = [(lang_name, color, count, count / total * 100 if total else 0)
                 for (lang_name, color), count in top]
        rest = sum(count for _, count in items[max_items:])
        if rest > 0:
            shown.append(("Other", OTHER_COLOR, rest, rest / total * 100 if total else 0))

    return shown

def wrap_legend_items(items, max_width, font_size=13):
    rows = []
    current_row = []
    current_width = 0

    for lang_name, color, count, pct in items:
        label = lang_name
        pct_text = f"{pct:.1f}%"

        item_width = (
            14 +                       # dot + margin
            approx_text_width(label, font_size, bold=True) +
            8 +
            approx_text_width(pct_text, font_size, bold=False) +
            22                        # item gap
        )

        if current_row and current_width + item_width > max_width:
            rows.append(current_row)
            current_row = []
            current_width = 0

        current_row.append((lang_name, color, count, pct))
        current_width += item_width

    if current_row:
        rows.append(current_row)

    return rows

def render_legend(parts, x, y, rows, font_size=13, row_gap=24):
    dot_r = 5

    for row in rows:
        cursor_x = x
        for lang_name, color, count, pct in row:
            pct_text = f"{pct:.1f}%"

            parts.append(
                f'<circle cx="{cursor_x + dot_r}" cy="{y - 4}" r="{dot_r}" fill="{color}"/>'
            )
            cursor_x += 18

            parts.append(
                f'<text x="{cursor_x}" y="{y}" font-size="{font_size}" font-weight="600" fill="#24292f">{escape(lang_name)}</text>'
            )
            cursor_x += approx_text_width(lang_name, font_size, bold=True) + 8

            parts.append(
                f'<text x="{cursor_x}" y="{y}" font-size="{font_size}" fill="#57606a">{pct_text}</text>'
            )
            cursor_x += approx_text_width(pct_text, font_size, bold=False) + 22

        y += row_gap

    return y

def generate_svg(stats, total_lines, output, width, title, min_percent, minor_contributors_limit, show_contributors_limit):
    margin = 32
    avatar_size = 44
    left_x = margin
    text_x = left_x + avatar_size + 16
    bar_x = 265
    bar_width = width - bar_x - margin
    header_h = 92
    card_radius = 18

    contributors = sorted(stats.items(), key=lambda x: x[1]["total"], reverse=True)

    full_rows = []
    minor_rows = []

    total_contributors = len(contributors)

    for user, data in contributors:
        percent = data["total"] / total_lines * 100 if total_lines else 0

        if total_contributors < 5:
            full_rows.append((user, data, percent))
        else:
            if percent >= min_percent:
                full_rows.append((user, data, percent))
            else:
                minor_rows.append((user, data, percent))

    if show_contributors_limit is None:
        visible = full_rows
        overflow_rows = []
    else:
        visible = full_rows[:show_contributors_limit]
        overflow_rows = full_rows[show_contributors_limit:]

    hidden = overflow_rows + minor_rows

    if overflow_rows:
        hidden_title = "Other contributors"
    else:
        hidden_title = f"Contributors below {min_percent}%"

    # 先预估高度
    layout_info = []
    total_height = header_h + 18

    for user, data, percent in visible:
        lang_items = summarize_languages(data["langs"], data["total"], max_items=6, min_percent=2.0)
        legend_rows = wrap_legend_items(lang_items, max_width=bar_width)
        row_h = max(avatar_size, 18 + 18 + len(legend_rows) * 22) + 26
        layout_info.append((user, data, percent, lang_items, legend_rows, row_h))
        total_height += row_h

    if hidden and minor_contributors_limit != 0:
        if minor_contributors_limit is None:
            hidden_count = len(hidden)
            has_more_label = False
        else:
            hidden_count = min(len(hidden), minor_contributors_limit)
            has_more_label = len(hidden) > minor_contributors_limit

        layout_count = hidden_count + (1 if has_more_label else 0)

        icons_per_row = max(1, (width - margin * 2 - 80) // 38)
        hidden_rows = (layout_count + icons_per_row - 1) // icons_per_row

        total_height += 34 + hidden_rows * 38

    total_height += 20

    parts = [
        f'<svg width="{width}" height="{total_height}" viewBox="0 0 {width} {total_height}" xmlns="http://www.w3.org/2000/svg">',
        '<style>',
        'text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;}',
        '</style>',
        f'<rect x="1" y="1" width="{width-2}" height="{total_height-2}" rx="{card_radius}" fill="#ffffff" stroke="#d0d7de" stroke-width="1"/>',
        f'<text x="{margin}" y="46" font-size="20" font-weight="700" fill="#24292f">{escape(title)}</text>',
        f'<text x="{margin}" y="68" font-size="13" fill="#57606a">{total_lines} non-empty blamed lines · {len(contributors)} contributors</text>',
    ]

    y = header_h

    for user, data, percent, lang_items, legend_rows, row_h in layout_info:
        avatar_y = y
        name_y = y + 14
        meta_y = y + 34
        bar_y = y + 3

        avatar = data.get("avatar")
        avatar_id = safe_id(user)

        if avatar:
            parts.append(
                f'<clipPath id="avatar-{avatar_id}"><circle cx="{left_x + avatar_size/2}" cy="{avatar_y + avatar_size/2}" r="{avatar_size/2}"/></clipPath>'
            )
            parts.append(
                f'<image href="{avatar}" x="{left_x}" y="{avatar_y}" width="{avatar_size}" height="{avatar_size}" clip-path="url(#avatar-{avatar_id})"/>'
            )
        else:
            parts.append(
                f'<circle cx="{left_x + avatar_size/2}" cy="{avatar_y + avatar_size/2}" r="{avatar_size/2}" fill="#d0d7de"/>'
            )
            parts.append(
                f'<text x="{left_x + avatar_size/2}" y="{avatar_y + 28}" text-anchor="middle" font-size="16" font-weight="700" fill="#57606a">{escape(user[:1].upper())}</text>'
            )

        # 用户名
        parts.append(
            f'<text x="{text_x}" y="{name_y}" font-size="16" font-weight="700" fill="#24292f">{escape(user)}</text>'
        )

        # 行数和占比
        parts.append(
            f'<text x="{text_x}" y="{meta_y}" font-size="13" fill="#57606a">{data["total"]} lines · {percent:.2f}%</text>'
        )

        # bar 底轨 + 裁剪
        bar_height = 18
        bar_radius = 9
        clip_id = f"bar-clip-{avatar_id}"

        parts.append(
            f'<clipPath id="{clip_id}"><rect x="{bar_x}" y="{bar_y}" width="{bar_width}" height="{bar_height}" rx="{bar_radius}"/></clipPath>'
        )
        parts.append(
            f'<rect x="{bar_x}" y="{bar_y}" width="{bar_width}" height="{bar_height}" rx="{bar_radius}" fill="{TRACK_COLOR}"/>'
        )

        seg_x = bar_x
        for lang_name, color, count, pct in lang_items:
            seg_w = bar_width * count / data["total"] if data["total"] else 0
            if seg_w <= 0:
                continue
            parts.append(
                f'<rect x="{seg_x:.2f}" y="{bar_y}" width="{seg_w:.2f}" height="{bar_height}" fill="{color}" clip-path="url(#{clip_id})"/>'
            )
            seg_x += seg_w

        # legend
        legend_start_y = y + 44
        render_legend(parts, bar_x, legend_start_y, legend_rows, font_size=13, row_gap=22)

        y += row_h

    if hidden and minor_contributors_limit != 0:
        if minor_contributors_limit is None:
            hidden_to_show = hidden
        else:
            hidden_to_show = hidden[:minor_contributors_limit]

        parts.append(
            f'<text x="{margin}" y="{y + 10}" font-size="13" fill="#57606a">'
            f'{hidden_title}'
            f'</text>'
        )

        icon_x = margin
        icon_y = y + 24
        size = 28

        max_icon_x = width - margin - 80

        for user, data, percent in hidden_to_show:
            if icon_x + size > max_icon_x:
                icon_x = margin
                icon_y += size + 10

            avatar = data.get("avatar")
            uid = safe_id(user)

            if avatar:
                parts.append(
                    f'<clipPath id="small-avatar-{uid}">'
                    f'<circle cx="{icon_x + size/2}" cy="{icon_y + size/2}" r="{size/2}"/>'
                    f'</clipPath>'
                )
                parts.append(
                    f'<image href="{avatar}" x="{icon_x}" y="{icon_y}" '
                    f'width="{size}" height="{size}" '
                    f'clip-path="url(#small-avatar-{uid})"/>'
                )
            else:
                parts.append(
                    f'<circle cx="{icon_x + size/2}" cy="{icon_y + size/2}" '
                    f'r="{size/2}" fill="#d0d7de"/>'
                )
                parts.append(
                    f'<text x="{icon_x + size/2}" y="{icon_y + 19}" '
                    f'text-anchor="middle" font-size="12" font-weight="700" fill="#57606a">'
                    f'{escape(user[:1].upper())}'
                    f'</text>'
                )

            icon_x += size + 10

        if minor_contributors_limit is not None and len(hidden) > minor_contributors_limit:
            remaining = len(hidden) - minor_contributors_limit
            
            more_text_width = approx_text_width(f"+{remaining} more", 13)

            if icon_x + more_text_width + 8 > width - margin:
                icon_x = margin
                icon_y += size + 10

            parts.append(
                f'<text x="{icon_x + 4}" y="{icon_y + 19}" font-size="13" fill="#57606a">'
                f'+{remaining} more'
                f'</text>'
            )

    parts.append("</svg>")

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text("\n".join(parts), encoding="utf-8")


def main():
    output = os.environ.get("INPUT_OUTPUT", "dist/code-stats.svg")
    title = os.environ.get("INPUT_TITLE", "Code Stats")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("INPUT_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN", "")

    try:
        width = int(os.environ.get("INPUT_WIDTH", "900"))
    except ValueError:
        width = 900

    try:
        min_percent = float(os.environ.get("INPUT_MIN_PERCENT", "0.8"))
    except ValueError:
        min_percent = 0.8

    minor_contributors_limit = parse_minor_contributors_limit(
        os.environ.get("INPUT_MINOR_CONTRIBUTORS_LIMIT", 22), default=22
    )
    show_contributors_limit = parse_show_contributors_limit(
        os.environ.get("INPUT_SHOW_CONTRIBUTORS_LIMIT", 10), default=10
    )

    raw_ignore = os.environ.get("INPUT_IGNORE", "")
    raw_users = os.environ.get("INPUT_USERS", "")

    alias_map, canonical_map = parse_users(raw_users)
    ignore_patterns = DEFAULT_IGNORE + [line.strip() for line in raw_ignore.splitlines() if line.strip()]

    stats = defaultdict(lambda: {"total": 0, "langs": defaultdict(int), "avatar": None})
    total_lines = 0
    commit_cache = {}

    files = list_files(ignore_patterns)
    warn(f"found {len(files)} supported files")

    for file in files:
        lang = get_language(file)
        if lang is None:
            continue

        for sha, author, email in blame_file(file):
            login, avatar = resolve_commit_identity(repo, sha, token, commit_cache)
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

    generate_svg(stats, total_lines, output, width, title, min_percent, minor_contributors_limit, show_contributors_limit)
    warn(f"generated {output}")


if __name__ == "__main__":
    main()
