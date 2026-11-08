"""
Generates a custom amber-terminal-themed stats SVG using GitHub's own API,
authenticated with the workflow's built-in GITHUB_TOKEN (5,000 req/hr, never
shared with other users) instead of a public free service.

Env vars expected:
  GH_USERNAME   - the GitHub username to report on
  GITHUB_TOKEN  - provided automatically by GitHub Actions

Output: dist/dashboard.svg
"""

import json
import os
import urllib.request
from collections import Counter
from html import escape

USERNAME = os.environ["GH_USERNAME"]
TOKEN = os.environ["GITHUB_TOKEN"]

API = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "User-Agent": USERNAME,
}

GRAPHQL_QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      contributionCalendar { totalContributions }
    }
  }
}
"""


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


def fetch_contributions():
    """Last-12-months activity via GraphQL. Returns None on any failure so the
    workflow never breaks; the dashboard then falls back to repo-based stats."""
    try:
        body = json.dumps({"query": GRAPHQL_QUERY, "variables": {"login": USERNAME}}).encode()
        req = urllib.request.Request(f"{API}/graphql", data=body, headers=HEADERS, method="POST")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
        c = data["data"]["user"]["contributionsCollection"]
        return {
            "total": c["contributionCalendar"]["totalContributions"],
            "commits": c["totalCommitContributions"],
            "prs": c["totalPullRequestContributions"],
        }
    except Exception as exc:  # noqa: BLE001
        print(f"GraphQL contributions unavailable, using repo stats instead: {exc}")
        return None


def main():
    repos = [r for r in fetch_all_repos() if not r.get("fork")]  # your own work only
    contrib = fetch_contributions()

    lang_counts = Counter(r["language"] for r in repos if r.get("language"))
    top_langs = lang_counts.most_common(4)
    max_count = max((c for _, c in top_langs), default=1)

    if contrib:
        stats = [
            ("REPOS", len(repos)),
            ("CONTRIBS / 1Y", contrib["total"]),
            ("COMMITS / 1Y", contrib["commits"]),
            ("PULL REQS", contrib["prs"]),
        ]
    else:
        user = fetch(f"{API}/users/{USERNAME}")
        stats = [
            ("REPOS", len(repos)),
            ("FOLLOWERS", user.get("followers", 0)),
            ("STARS", sum(r.get("stargazers_count", 0) for r in repos)),
            ("FORKS", sum(r.get("forks_count", 0) for r in repos)),
        ]

    margin, gap, box_h = 20, 16, 90
    # canvas width is derived FROM the boxes, never hardcoded, so nothing can overflow the frame
    total_width = margin * 2 + len(stats) * 190 + (len(stats) - 1) * gap
    box_w = (total_width - margin * 2 - (len(stats) - 1) * gap) / len(stats)

    boxes_svg = ""
    for i, (label, value) in enumerate(stats):
        x = margin + i * (box_w + gap)
        boxes_svg += f"""
        <g transform="translate({x},20)">
          <rect width="{box_w}" height="{box_h}" rx="8" fill="#141414" stroke="#FFA500" stroke-width="2"/>
          <text x="{box_w/2}" y="40" text-anchor="middle" font-family="Courier New, monospace"
                font-size="30" fill="#FFB000" font-weight="bold">{value}</text>
          <text x="{box_w/2}" y="68" text-anchor="middle" font-family="Courier New, monospace"
                font-size="13" fill="#FFA500" letter-spacing="2">{escape(label)}</text>
        </g>"""

    # bars stretch to fill the frame instead of leaving dead space on the right
    bar_x = 170
    bar_max = total_width - bar_x - margin - 50
    bars_svg = ""
    bar_y = 150
    for lang, count in top_langs:
        bar_w = max(6, int(bar_max * (count / max_count)))
        label = lang if len(lang) <= 14 else lang[:13] + "…"  # never collides with the bar
        bars_svg += f"""
        <text x="20" y="{bar_y + 14}" font-family="Courier New, monospace" font-size="14" fill="#FFB000">{escape(label)}</text>
        <rect x="{bar_x}" y="{bar_y}" width="{bar_max}" height="18" rx="3" fill="#141414" stroke="#FFA500" stroke-width="1"/>
        <rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="18" rx="3" fill="#FFA500"/>
        <text x="{bar_x + bar_max + 10}" y="{bar_y + 14}" font-family="Courier New, monospace" font-size="12" fill="#FFA500">{count}</text>"""
        bar_y += 30

    svg_h = bar_y + 20
    svg = f"""<svg width="{total_width}" height="{svg_h}" viewBox="0 0 {total_width} {svg_h}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{total_width}" height="{svg_h}" rx="12" fill="#0a0a0a" stroke="#FFA500" stroke-width="2"/>
  {boxes_svg}
  <text x="20" y="135" font-family="Courier New, monospace" font-size="13" fill="#FFB000" letter-spacing="2">TOP_LANGUAGES</text>
  {bars_svg}
</svg>"""

    os.makedirs("dist", exist_ok=True)
    with open("dist/dashboard.svg", "w", encoding="utf-8") as f:
        f.write(svg)


if __name__ == "__main__":
    main()
