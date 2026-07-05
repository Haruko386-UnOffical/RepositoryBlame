import re


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
