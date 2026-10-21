#!/usr/bin/env python3
"""Generate a self-hosted profile card (SVG) from the GitHub GraphQL + REST API."""

import json
import os
import sys
import urllib.request

LOGIN = os.environ.get("GH_LOGIN", "william-xue")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
API = "https://api.github.com"

LANG_COLORS = {
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "Vue": "#41b883",
    "Go": "#00add8",
    "Rust": "#dea584",
    "Python": "#3572a5",
    "Java": "#b07219",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "Shell": "#89e051",
    "C++": "#f34b7d",
    "C": "#555555",
    "Jupyter Notebook": "#da5b0b",
    "MDX": "#fcb32c",
    "SCSS": "#c6538c",
    "Dockerfile": "#384d54",
    "Batchfile": "#c1f12e",
    "PowerShell": "#012456",
}

GRAPHQL = """
query($login: String!) {
  user(login: $login) {
    name
    login
    createdAt
    location
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false,
                 orderBy: {field: STARGAZERS, direction: DESC}) {
      nodes { name stargazerCount primaryLanguage { name } pushedAt }
    }
    all: repositories(privacy: PUBLIC, ownerAffiliations: OWNER) { totalCount }
  }
}
"""


def request(url, data=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"bearer {TOKEN}",
        "User-Agent": "profile-card",
    }
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def gql(query, variables):
    return request(f"{API}/graphql", {"query": query, "variables": variables})


def esc(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def human(n):
    if n >= 1000:
        return f"{n / 1000:.1f}".rstrip("0").rstrip(".") + "k"
    return str(n)


def collect():
    data = gql(GRAPHQL, {"login": LOGIN})
    if "errors" in data:
        sys.exit(f"GraphQL error: {data['errors']}")
    user = data["data"]["user"]
    repos = user["repositories"]["nodes"]

    stars = sum(r["stargazerCount"] for r in repos)
    joined = int(user["createdAt"][:4])

    recent = sorted(repos, key=lambda r: r["pushedAt"], reverse=True)[:25]
    langs = {}
    for repo in recent:
        try:
            for name, size in request(f"{API}/repos/{LOGIN}/{repo['name']}/languages").items():
                langs[name] = langs.get(name, 0) + size
        except Exception:
            continue
    top = sorted(langs.items(), key=lambda kv: kv[1], reverse=True)[:5]
    rest = sum(size for _, size in sorted(langs.items(), key=lambda kv: kv[1], reverse=True)[5:])
    if rest:
        top.append(("Other", rest))
    total = sum(size for _, size in top) or 1

    return {
        "name": user["name"] or user["login"],
        "login": user["login"],
        "location": user["location"] or "",
        "followers": user["followers"]["totalCount"],
        "repos": user["all"]["totalCount"],
        "stars": stars,
        "years": max(1, 2026 - joined),
        "languages": [(n, s, s / total) for n, s in top],
        "featured": [r for r in repos if r["stargazerCount"] > 0][:3],
    }


def render(d):
    W, H = 860, 268
    accent, text, muted, border = "#3fb950", "#e6edf3", "#8b949e", "#21262d"

    stats = [
        ("Stars earned", human(d["stars"])),
        ("Followers", human(d["followers"])),
        ("Years on GitHub", str(d["years"])),
        ("Public repos", human(d["repos"])),
    ]
    cols = [28, 236, 468, 700]

    parts = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub profile card">')
    parts.append(
        "<defs>"
        '<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#0d1117"/><stop offset="1" stop-color="#101a1c"/>'
        "</linearGradient>"
        '<radialGradient id="glow" cx="0.08" cy="0" r="0.9">'
        '<stop offset="0" stop-color="#3fb950" stop-opacity="0.16"/>'
        '<stop offset="1" stop-color="#3fb950" stop-opacity="0"/>'
        "</radialGradient>"
        f'<clipPath id="bar"><rect x="28" y="196" width="{W - 56}" height="9" rx="4.5"/></clipPath>'
        "</defs>"
    )
    parts.append(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="url(#bg)" stroke="{border}"/>')
    parts.append(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="url(#glow)"/>')

    parts.append(
        f'<text x="28" y="56" font-family="ui-sans-serif,-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial" '
        f'font-size="23" font-weight="700" fill="{text}">{esc(d["name"])}</text>'
    )
    meta = f'@{d["login"]}' + (f'  ·  {d["location"]}' if d["location"] else "")
    parts.append(
        f'<text x="29" y="78" font-family="ui-sans-serif,-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial" '
        f'font-size="12.5" fill="{muted}" letter-spacing="0.2">{esc(meta)}</text>'
    )

    chip = "building graph editor internals"
    chip_w = len(chip) * 6.9 + 44
    cx = W - 28 - chip_w
    parts.append(f'<rect x="{cx:.1f}" y="34" width="{chip_w:.1f}" height="27" rx="13.5" fill="#3fb950" fill-opacity="0.10" stroke="#3fb950" stroke-opacity="0.35"/>')
    parts.append(f'<circle cx="{cx + 16:.1f}" cy="47.5" r="3.2" fill="{accent}"/>')
    parts.append(
        f'<text x="{cx + 26:.1f}" y="52" font-family="ui-monospace,SFMono-Regular,Menlo,monospace" '
        f'font-size="11.5" fill="{accent}">{esc(chip)}</text>'
    )

    for (label, value), x in zip(stats, cols):
        parts.append(
            f'<text x="{x}" y="136" font-family="ui-sans-serif,-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial" '
            f'font-size="27" font-weight="700" fill="{accent}" letter-spacing="-0.5">{esc(value)}</text>'
        )
        parts.append(
            f'<text x="{x}" y="156" font-family="ui-monospace,SFMono-Regular,Menlo,monospace" '
            f'font-size="10.5" fill="{muted}" letter-spacing="0.9">{esc(label.upper())}</text>'
        )

    parts.append(
        f'<text x="28" y="188" font-family="ui-monospace,SFMono-Regular,Menlo,monospace" '
        f'font-size="10.5" fill="{muted}" letter-spacing="0.9">MOST USED LANGUAGES</text>'
    )

    bar_w = W - 56
    offset = 28.0
    parts.append('<g clip-path="url(#bar)">')
    for name, _, ratio in d["languages"]:
        seg = max(bar_w * ratio, 0)
        color = LANG_COLORS.get(name, "#8b949e")
        parts.append(f'<rect x="{offset:.2f}" y="196" width="{seg:.2f}" height="9" fill="{color}"/>')
        offset += seg
    parts.append("</g>")

    lx = 28.0
    for name, _, ratio in d["languages"]:
        color = LANG_COLORS.get(name, "#8b949e")
        parts.append(f'<circle cx="{lx + 4:.1f}" cy="228" r="4" fill="{color}"/>')
        label = f'{name} {ratio * 100:.0f}%'
        parts.append(
            f'<text x="{lx + 13:.1f}" y="232" font-family="ui-sans-serif,-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial" '
            f'font-size="11.5" fill="{text}" fill-opacity="0.85">{esc(label)}</text>'
        )
        lx += len(label) * 6.6 + 26

    repo = d["featured"][0] if d["featured"] else None
    if repo:
        line = f'featured  {repo["name"]}  ★ {repo["stargazerCount"]}'
        parts.append(
            f'<text x="28" y="254" font-family="ui-monospace,SFMono-Regular,Menlo,monospace" '
            f'font-size="11" fill="{muted}">{esc(line)}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def main():
    data = collect()
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "profile-card.svg")
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(data))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
