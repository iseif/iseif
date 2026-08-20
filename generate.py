#!/usr/bin/env python3
"""Generate a Neofetch-style GitHub profile card for github.com/iseif.

The script creates dark_mode.svg and light_mode.svg. On GitHub Actions it uses
GitHub's API to refresh public profile stats and converts the current GitHub
avatar into ASCII art.
"""

from __future__ import annotations

import argparse
import html
import io
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageEnhance, ImageOps

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "profile.json"
API = "https://api.github.com"


@dataclass
class Stats:
    public_repos: str = "auto"
    followers: str = "auto"
    stars: str = "auto"
    github_since: str = "auto"
    avatar_url: str | None = None


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def headers(token: str | None) -> dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "iseif-profile-readme",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def rest_get(path: str, token: str | None, params: dict[str, Any] | None = None) -> Any:
    r = requests.get(f"{API}{path}", headers=headers(token), params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_stats(username: str, token: str | None) -> Stats:
    stats = Stats()

    # Basic public account information + owned public repository stars.
    user = rest_get(f"/users/{username}", token)
    stats.public_repos = f"{user.get('public_repos', 0):,}"
    stats.followers = f"{user.get('followers', 0):,}"
    stats.avatar_url = user.get("avatar_url")
    created_at = user.get("created_at")
    if created_at:
        stats.github_since = datetime.fromisoformat(created_at.replace("Z", "+00:00")).strftime("%Y")

    stars = 0
    page = 1
    while True:
        repos = rest_get(
            f"/users/{username}/repos",
            token,
            {"type": "owner", "sort": "updated", "per_page": 100, "page": page},
        )
        if not repos:
            break
        stars += sum(int(repo.get("stargazers_count", 0)) for repo in repos if not repo.get("fork"))
        if len(repos) < 100:
            break
        page += 1
    stats.stars = f"{stars:,}"

    return stats


def fallback_ascii() -> list[str]:
    art = [
        "        SSSSS   EEEEE   IIIII  FFFFF",
        "       SS      EE        I    FF   ",
        "       SS      EE        I    FF   ",
        "        SSSS   EEEE      I    FFFF ",
        "           SS  EE        I    FF   ",
        "           SS  EE        I    FF   ",
        "       SSSSS   EEEEE   IIIII  FF   ",
    ]
    top = [""] * 8
    bottom = [""] * 9
    return top + art + bottom


def avatar_to_ascii(url: str | None, token: str | None, columns: int = 38, rows: int = 26) -> list[str]:
    if not url:
        return fallback_ascii()

    try:
        r = requests.get(url, headers=headers(token), timeout=30)
        r.raise_for_status()
        image = Image.open(io.BytesIO(r.content)).convert("L")
        image = ImageOps.fit(image, (420, 420), method=Image.Resampling.LANCZOS, centering=(0.5, 0.45))
        image = ImageOps.autocontrast(image, cutoff=1)
        image = ImageEnhance.Contrast(image).enhance(1.35)
        image = image.resize((columns, rows), Image.Resampling.LANCZOS)

        chars = "@%#*+=-:. "
        px = image.load()
        cx, cy = (columns - 1) / 2, (rows - 1) / 2
        rx, ry = columns / 2.05, rows / 2.05
        lines: list[str] = []
        for y in range(rows):
            line = []
            for x in range(columns):
                # Circular avatar crop, similar to GitHub's profile photo.
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 > 1.0:
                    line.append(" ")
                    continue
                value = px[x, y]
                idx = round((value / 255) * (len(chars) - 1))
                line.append(chars[idx])
            lines.append("".join(line).rstrip())
        return lines
    except Exception as exc:  # Keep profile generation resilient.
        print(f"warning: avatar conversion failed: {exc}", file=sys.stderr)
        return fallback_ascii()


def dotted(label: str, value: str, target: int = 49) -> tuple[str, str, str]:
    prefix = f". {label}:"
    dots = "." * max(2, target - len(prefix) - len(value))
    return prefix, f" {dots} ", value


def escape(value: Any) -> str:
    return html.escape(str(value), quote=False)


def field_tspan(y: int, label: str, value: str, x: int) -> str:
    prefix, dots, val = dotted(label, value)
    return (
        f'<tspan x="{x}" y="{y}" class="muted">. </tspan>'
        f'<tspan class="key">{escape(label)}</tspan><tspan class="muted">:{escape(dots[1:])}</tspan>'
        f'<tspan class="value">{escape(val)}</tspan>'
    )


def section_tspan(y: int, title: str, x: int) -> str:
    rule = "-" * max(8, 52 - len(title))
    return f'<tspan x="{x}" y="{y}" class="text">- {escape(title)} {rule}</tspan>'


def theme_css(mode: str) -> tuple[str, str, str, str, str, str]:
    if mode == "dark":
        return ("#0d1117", "#c9d1d9", "#8b949e", "#ffa657", "#a5d6ff", "#3fb950")
    return ("#ffffff", "#24292f", "#57606a", "#bc4c00", "#0969da", "#1a7f37")


def render_svg(config: dict[str, Any], stats: Stats, ascii_lines: list[str], mode: str) -> str:
    theme = config.get("theme", {})
    width = int(theme.get("width", 1100))
    height = int(theme.get("height", 530))
    left_width = int(theme.get("left_column_width", 390))
    font_size = int(theme.get("font_size", 16))
    x = left_width + 25

    bg, text, muted, key, value, accent = theme_css(mode)

    # Truncate to fit the fixed profile card cleanly.
    join = lambda values: " · ".join(values)
    fields = [
        ("Role", config["role"]),
        ("Focus", join(config["focus"])),
        ("Editor", join(config["editors"])),
        ("Programming", join(config["programming"])),
        ("Backend", join(config["backend"])),
        ("Mobile", join(config["mobile"])),
        ("Cloud", join(config["cloud"])),
        ("Languages", join(config["spoken_languages"])),
    ]

    avatar_svg = []
    y0 = 30
    step = 19
    for i, line in enumerate(ascii_lines[:27]):
        avatar_svg.append(f'<tspan x="18" y="{y0 + i * step}">{escape(line)}</tspan>')

    right = []
    header = f"{config.get('terminal_user', 'seif')}@{config.get('terminal_host', 'github')}"
    right.append(f'<tspan x="{x}" y="30" class="text">{escape(header)}  ----------------------------------------------</tspan>')

    y = 58
    for label, val in fields:
        right.append(field_tspan(y, label, val, x))
        y += 25

    y += 9
    right.append(section_tspan(y, "Contact", x))
    y += 25
    for label, url in config["contacts"].items():
        display = url.removeprefix("https://").rstrip("/")
        right.append(field_tspan(y, label, display, x))
        y += 25

    y += 8
    right.append(section_tspan(y, "GitHub Stats", x))
    y += 25
    right.append(field_tspan(y, "Public Repos", stats.public_repos, x)); y += 25
    right.append(field_tspan(y, "Stars", stats.stars, x)); y += 25
    right.append(field_tspan(y, "Followers", stats.followers, x)); y += 25
    right.append(field_tspan(y, "GitHub Since", stats.github_since, x))

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Seif Ibrahim GitHub profile" xml:space="preserve">
  <style>
    .card {{ font-family: Consolas, "Liberation Mono", Menlo, monospace; font-size: {font_size}px; }}
    .text {{ fill: {text}; }}
    .muted {{ fill: {muted}; }}
    .key {{ fill: {key}; }}
    .value {{ fill: {value}; }}
    .accent {{ fill: {accent}; }}
    tspan {{ white-space: pre; }}
  </style>
  <rect width="{width}" height="{height}" rx="16" fill="{bg}"/>
  <text class="card text">{''.join(avatar_svg)}</text>
  <text class="card">{''.join(right)}</text>
</svg>
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="Generate without network access using placeholder stats and fallback ASCII art")
    args = parser.parse_args()

    config = load_config()
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")

    if args.offline:
        stats = Stats(github_since="dynamic")
        ascii_lines = fallback_ascii()
    else:
        try:
            stats = fetch_stats(config["username"], token)
        except Exception as exc:
            print(f"warning: GitHub stats fetch failed: {exc}", file=sys.stderr)
            stats = Stats(github_since="dynamic")
        ascii_lines = avatar_to_ascii(stats.avatar_url, token)

    (ROOT / "dark_mode.svg").write_text(render_svg(config, stats, ascii_lines, "dark"), encoding="utf-8")
    (ROOT / "light_mode.svg").write_text(render_svg(config, stats, ascii_lines, "light"), encoding="utf-8")
    print("Generated dark_mode.svg and light_mode.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
