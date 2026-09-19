"""
Generates a custom amber-terminal-themed stats SVG using GitHub's own API,
authenticated with the workflow's built-in GITHUB_TOKEN (5,000 req/hr, never
shared with other users) instead of a public free service.

Env vars expected:
  GH_USERNAME   - the GitHub username to report on
  GITHUB_TOKEN  - provided automatically by GitHub Actions
"""

import json
import os
import urllib.request
from collections import Counter

USERNAME = os.environ["GH_USERNAME"]
TOKEN = os.environ["GITHUB_TOKEN"]

API = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "User-Agent": USERNAME,
}


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def fetch_all_repos():
    repos, page = [], 1
    while True:
        batch = fetch(f"{API}/users/{USERNAME}/repos?per_page=100&page={page}")
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return repos


def main():
    user = fetch(f"{API}/users/{USERNAME}")
    repos = fetch_all_repos()

    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    total_forks = sum(r.get("forks_count", 0) for r in repos)
    lang_counts = Counter(r["language"] for r in repos if r.get("language"))
    top_langs = lang_counts.most_common(4)
    max_count = max((c for _, c in top_langs), default=1)

    stats = [
        ("REPOS", user.get("public_repos", 0)),
        ("FOLLOWERS", user.get("followers", 0)),
        ("STARS", total_stars),
        ("FORKS", total_forks),
    ]

    box_w, box_h, gap = 190, 90, 16
    boxes_svg = ""
    for i, (label, value) in enumerate(stats):
        x = 20 + i * (box_w + gap)
        boxes_svg += f"""
        <g transform="translate({x},20)">
          <rect width="{box_w}" height="{box_h}" rx="8" fill="#141414" stroke="#FFA500" stroke-width="2"/>
          <text x="{box_w/2}" y="40" text-anchor="middle" font-family="Courier New, monospace"
                font-size="30" fill="#FFB000" font-weight="bold">{value}</text>
          <text x="{box_w/2}" y="68" text-anchor="middle" font-family="Courier New, monospace"
                font-size="13" fill="#FFA500" letter-spacing="2">{label}</text>
        </g>"""

    bars_svg = ""
    bar_y = 150
    for lang, count in top_langs:
        bar_w = int(300 * (count / max_count))
        bars_svg += f"""
        <text x="20" y="{bar_y + 14}" font-family="Courier New, monospace" font-size="14" fill="#FFB000">{lang}</text>
        <rect x="140" y="{bar_y}" width="300" height="18" rx="3" fill="#141414" stroke="#FFA500" stroke-width="1"/>
        <rect x="140" y="{bar_y}" width="{bar_w}" height="18" rx="3" fill="#FFA500"/>
        <text x="{140 + 310}" y="{bar_y + 14}" font-family="Courier New, monospace" font-size="12" fill="#FFA500">{count}</text>"""
        bar_y += 30

    svg = f"""<svg width="820" height="{bar_y + 20}" viewBox="0 0 820 {bar_y + 20}" xmlns="http://www.w3.org/2000/svg">
  <rect width="820" height="{bar_y + 20}" rx="12" fill="#0a0a0a" stroke="#FFA500" stroke-width="2"/>
  {boxes_svg}
  <text x="20" y="135" font-family="Courier New, monospace" font-size="13" fill="#FFB000" letter-spacing="2">TOP_LANGUAGES</text>
  {bars_svg}
</svg>"""

    os.makedirs("dist", exist_ok=True)
    with open("dist/dashboard.svg", "w") as f:
        f.write(svg)


if __name__ == "__main__":
    main()
