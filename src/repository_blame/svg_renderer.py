import re
from pathlib import Path

from .constants import OTHER_COLOR, TRACK_COLOR


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
        shown = [
            (lang_name, color, count, count / total * 100 if total else 0)
            for (lang_name, color), count in top
        ]
        rest = sum(count for _, count in items[max_items:])
        if rest > 0:
            shown.append(("Other", OTHER_COLOR, rest, rest / total * 100 if total else 0))

    return shown


def wrap_legend_items(items, max_width, font_size=13):
    rows = []
    current_row = []
    current_width = 0

    for lang_name, _color, _count, pct in items:
        pct_text = f"{pct:.1f}%"
        item_width = (
            14
            + approx_text_width(lang_name, font_size, bold=True)
            + 8
            + approx_text_width(pct_text, font_size, bold=False)
            + 22
        )

        if current_row and current_width + item_width > max_width:
            rows.append(current_row)
            current_row = []
            current_width = 0

        current_row.append((lang_name, _color, _count, pct))
        current_width += item_width

    if current_row:
        rows.append(current_row)

    return rows


def render_legend(parts, x, y, rows, font_size=13, row_gap=24):
    dot_r = 5

    for row in rows:
        cursor_x = x
        for lang_name, color, _count, pct in row:
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


def split_contributors(contributors, total_lines, min_percent):
    full_rows = []
    minor_rows = []
    total_contributors = len(contributors)

    for user, data in contributors:
        percent = data["total"] / total_lines * 100 if total_lines else 0
        if total_contributors < 5 or percent >= min_percent:
            full_rows.append((user, data, percent))
        else:
            minor_rows.append((user, data, percent))

    return full_rows, minor_rows


def limit_rows(rows, show_contributors_limit):
    if show_contributors_limit is None:
        return rows, []
    return rows[:show_contributors_limit], rows[show_contributors_limit:]


def build_visible_layout(visible, bar_width):
    layout_info = []
    total_height = 0

    for user, data, percent in visible:
        lang_items = summarize_languages(data["langs"], data["total"], max_items=6, min_percent=2.0)
        legend_rows = wrap_legend_items(lang_items, max_width=bar_width)
        row_h = max(44, 18 + 18 + len(legend_rows) * 22) + 26
        layout_info.append((user, data, percent, lang_items, legend_rows, row_h))
        total_height += row_h

    return layout_info, total_height


def hidden_section_height(hidden, minor_contributors_limit, width, margin):
    if not hidden or minor_contributors_limit == 0:
        return 0

    if minor_contributors_limit is None:
        hidden_count = len(hidden)
        has_more_label = False
    else:
        hidden_count = min(len(hidden), minor_contributors_limit)
        has_more_label = len(hidden) > minor_contributors_limit

    layout_count = hidden_count + (1 if has_more_label else 0)
    icons_per_row = max(1, (width - margin * 2 - 80) // 38)
    hidden_rows = (layout_count + icons_per_row - 1) // icons_per_row
    return 34 + hidden_rows * 38


def append_avatar(parts, user, avatar, x, y, size, clip_prefix):
    uid = safe_id(user)

    if avatar:
        parts.append(
            f'<clipPath id="{clip_prefix}-{uid}"><circle cx="{x + size/2}" cy="{y + size/2}" r="{size/2}"/></clipPath>'
        )
        parts.append(
            f'<image href="{avatar}" x="{x}" y="{y}" width="{size}" height="{size}" clip-path="url(#{clip_prefix}-{uid})"/>'
        )
        return

    parts.append(f'<circle cx="{x + size/2}" cy="{y + size/2}" r="{size/2}" fill="#d0d7de"/>')
    parts.append(
        f'<text x="{x + size/2}" y="{y + size * 0.64:.0f}" text-anchor="middle" font-size="{max(12, int(size * 0.36))}" font-weight="700" fill="#57606a">{escape(user[:1].upper())}</text>'
    )


def append_contributor_row(parts, row, geometry):
    user, data, percent, lang_items, legend_rows, row_h = row
    left_x, text_x, bar_x, bar_width, y = geometry
    avatar_size = 44
    avatar_id = safe_id(user)
    bar_height = 18
    bar_radius = 9
    bar_y = y + 3
    clip_id = f"bar-clip-{avatar_id}"

    append_avatar(parts, user, data.get("avatar"), left_x, y, avatar_size, "avatar")

    parts.append(
        f'<text x="{text_x}" y="{y + 14}" font-size="16" font-weight="700" fill="#24292f">{escape(user)}</text>'
    )
    parts.append(
        f'<text x="{text_x}" y="{y + 34}" font-size="13" fill="#57606a">{data["total"]} lines &#183; {percent:.2f}%</text>'
    )

    parts.append(
        f'<clipPath id="{clip_id}"><rect x="{bar_x}" y="{bar_y}" width="{bar_width}" height="{bar_height}" rx="{bar_radius}"/></clipPath>'
    )
    parts.append(
        f'<rect x="{bar_x}" y="{bar_y}" width="{bar_width}" height="{bar_height}" rx="{bar_radius}" fill="{TRACK_COLOR}"/>'
    )

    seg_x = bar_x
    for _lang_name, color, count, _pct in lang_items:
        seg_w = bar_width * count / data["total"] if data["total"] else 0
        if seg_w <= 0:
            continue
        parts.append(
            f'<rect x="{seg_x:.2f}" y="{bar_y}" width="{seg_w:.2f}" height="{bar_height}" fill="{color}" clip-path="url(#{clip_id})"/>'
        )
        seg_x += seg_w

    render_legend(parts, bar_x, y + 44, legend_rows, font_size=13, row_gap=22)
    return y + row_h


def append_hidden_contributors(parts, hidden, minor_contributors_limit, hidden_title, width, margin, y):
    if not hidden or minor_contributors_limit == 0:
        return

    hidden_to_show = hidden if minor_contributors_limit is None else hidden[:minor_contributors_limit]
    parts.append(f'<text x="{margin}" y="{y + 10}" font-size="13" fill="#57606a">{hidden_title}</text>')

    icon_x = margin
    icon_y = y + 24
    size = 28
    max_icon_x = width - margin - 80

    for user, data, _percent in hidden_to_show:
        if icon_x + size > max_icon_x:
            icon_x = margin
            icon_y += size + 10

        append_avatar(parts, user, data.get("avatar"), icon_x, icon_y, size, "small-avatar")
        icon_x += size + 10

    if minor_contributors_limit is not None and len(hidden) > minor_contributors_limit:
        remaining = len(hidden) - minor_contributors_limit
        more_text_width = approx_text_width(f"+{remaining} more", 13)

        if icon_x + more_text_width + 8 > width - margin:
            icon_x = margin
            icon_y += size + 10

        parts.append(
            f'<text x="{icon_x + 4}" y="{icon_y + 19}" font-size="13" fill="#57606a">+{remaining} more</text>'
        )


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
    full_rows, minor_rows = split_contributors(contributors, total_lines, min_percent)
    visible, overflow_rows = limit_rows(full_rows, show_contributors_limit)
    hidden = overflow_rows + minor_rows
    hidden_title = "Other contributors" if overflow_rows else f"Contributors below {min_percent}%"
    layout_info, visible_height = build_visible_layout(visible, bar_width)
    total_height = (
        header_h
        + 18
        + visible_height
        + hidden_section_height(hidden, minor_contributors_limit, width, margin)
        + 20
    )

    parts = [
        f'<svg width="{width}" height="{total_height}" viewBox="0 0 {width} {total_height}" xmlns="http://www.w3.org/2000/svg">',
        "<style>",
        'text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;}',
        "</style>",
        f'<rect x="1" y="1" width="{width-2}" height="{total_height-2}" rx="{card_radius}" fill="#ffffff" stroke="#d0d7de" stroke-width="1"/>',
        f'<text x="{margin}" y="46" font-size="20" font-weight="700" fill="#24292f">{escape(title)}</text>',
        f'<text x="{margin}" y="68" font-size="13" fill="#57606a">{total_lines} non-empty blamed lines &#183; {len(contributors)} contributors</text>',
    ]

    y = header_h
    for row in layout_info:
        y = append_contributor_row(parts, row, (left_x, text_x, bar_x, bar_width, y))

    append_hidden_contributors(parts, hidden, minor_contributors_limit, hidden_title, width, margin, y)
    parts.append("</svg>")

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text("\n".join(parts), encoding="utf-8")
