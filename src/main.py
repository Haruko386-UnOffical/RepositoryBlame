import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from repository_blame.config import load_config
from repository_blame.logging_utils import warn
from repository_blame.stats import collect_stats
from repository_blame.svg_renderer import generate_svg
from repository_blame.users import parse_users


def main():
    config = load_config()
    alias_map, canonical_map = parse_users(config.raw_users)
    stats, total_lines = collect_stats(config, alias_map, canonical_map)

    generate_svg(
        stats,
        total_lines,
        config.output,
        config.width,
        config.title,
        config.min_percent,
        config.minor_contributors_limit,
        config.show_contributors_limit,
    )
    warn(f"generated {config.output}")


if __name__ == "__main__":
    main()
