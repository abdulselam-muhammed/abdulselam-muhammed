"""Builds assets/terminal-card.svg: a neofetch-style terminal card for the GitHub profile.

Run from the repo root:  python scripts/gen_card.py
Stats come from `gh api graphql` (your own login, so private contributions count);
if gh is missing, the last values in scripts/stats.json are used.
"""
import base64
import datetime as dt
import io
import json
import shutil
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
LOGIN = "abdulselam-muhammed"
STATS_FILE = ROOT / "scripts" / "stats.json"
AVATAR = ROOT / "assets" / "src" / "avatar.png"
OUT = ROOT / "assets" / "terminal-card.svg"

QUERY = """query($l:String!){user(login:$l){createdAt followers{totalCount} following{totalCount}
pullRequests{totalCount} issues{totalCount}
repositories(ownerAffiliations:OWNER,first:100){totalCount nodes{stargazerCount isFork
languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}}}
contributionsCollection{contributionCalendar{totalContributions}}}}"""


def fetch_stats():
    if not shutil.which("gh"):
        return json.loads(STATS_FILE.read_text(encoding="utf-8"))
    raw = subprocess.run(["gh", "api", "graphql", "-f", f"query={QUERY}", "-f", f"l={LOGIN}"],
                         capture_output=True, text=True, check=True).stdout
    u = json.loads(raw)["data"]["user"]
    langs = {}
    for repo in u["repositories"]["nodes"]:
        if repo["isFork"]:
            continue
        for e in repo["languages"]["edges"]:
            n = e["node"]["name"]
            langs.setdefault(n, {"size": 0, "color": e["node"]["color"] or "#8b949e"})
            langs[n]["size"] += e["size"]
    stats = {
        "created": u["createdAt"][:10],
        "repos": u["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in u["repositories"]["nodes"]),
        "followers": u["followers"]["totalCount"],
        "following": u["following"]["totalCount"],
        "prs": u["pullRequests"]["totalCount"],
        "issues": u["issues"]["totalCount"],
        "contributions": u["contributionsCollection"]["contributionCalendar"]["totalContributions"],
        "languages": sorted(([k, v["size"], v["color"]] for k, v in langs.items()), key=lambda x: -x[1]),
    }
    STATS_FILE.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    return stats


def uptime(created: str) -> str:
    a = dt.date.fromisoformat(created)
    b = dt.date.today()
    y, m, d = b.year - a.year, b.month - a.month, b.day - a.day
    if d < 0:
        m -= 1
        prev = (b.replace(day=1) - dt.timedelta(days=1))
        d += prev.day
    if m < 0:
        y -= 1
        m += 12
    unit = lambda n, w: f"{n} {w}" + ("" if n == 1 else "s")
    return f"{unit(y, 'year')}, {unit(m, 'month')}, {unit(d, 'day')}"


def pixel_avatar(w_px=230, h_px=470, cols=40):
    """Crop the avatar to a portrait, pixelate it, quantise the colours, return a PNG data URI."""
    im = Image.open(AVATAR).convert("RGB")
    W, H = im.size
    cw = int(H * w_px / h_px)
    left = max(0, (W - cw) // 2)
    im = im.crop((left, 0, left + cw, H))
    rows = round(cols * h_px / w_px)
    small = im.resize((cols, rows), Image.BILINEAR).quantize(colors=40, method=Image.MEDIANCUT).convert("RGB")
    big = small.resize((cols * 5, rows * 5), Image.NEAREST)
    buf = io.BytesIO()
    big.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


# ---- theme -------------------------------------------------------------------------------
BG, PANEL, BORDER = "#0d1117", "#161b22", "#30363d"
TXT, DIM, KEY, VAL, HEAD, PROMPT = "#c9d1d9", "#6e7681", "#ffa657", "#a5d6ff", "#e6edf3", "#7ee787"
FONT = "Consolas,'SFMono-Regular','DejaVu Sans Mono','Courier New',monospace"
FS, LH, CHW = 13, 18.5, 7.15  # font size, line height, approx char width


def build(stats):
    W, H = 900, 600
    ix, iy, iw, ih = 40, 44, 230, 470
    tx = ix + iw + 34
    width_chars = 64
    out = []
    y = iy + 12

    def text(x, yy, parts, size=FS):
        spans = "".join(f'<tspan fill="{c}"{" font-weight=\"bold\"" if b else ""}>{escape(s)}</tspan>' for s, c, b in parts)
        out.append(f'<text x="{x}" y="{yy:.1f}" font-size="{size}" xml:space="preserve">{spans}</text>')

    def header(title):
        nonlocal y
        rule = "─" * (width_chars - len(title) - 4) + "-—-"
        text(tx, y, [(title, HEAD, True), (" " + rule, BORDER, False)])
        y += LH

    def row(key, value, value_color=VAL):
        nonlocal y
        dots = "." * max(3, 24 - len(key))
        text(tx, y, [("▸ ", KEY, False), (key + ":", KEY, False), (" " + dots + " ", DIM, False), (value, value_color, False)])
        y += LH

    def gap(n=0.6):
        nonlocal y
        y += LH * n

    header(f"{LOGIN}@github")
    row("Uptime", uptime(stats["created"]))
    row("Host", "Mazad Global")
    row("Kernel", "Full-stack developer | marketplace platforms")
    row("Website", "linkedin.com/in/abdulselam-muhammed")
    gap()
    header("Stack")
    row("Backend", "NestJS, Laravel, Node.js")
    row("Frontend", "Next.js, React, Flutter")
    row("Data", "PostgreSQL, MySQL")
    row("DevOps", "Docker, GitHub Actions, Git")
    gap()
    header("Languages")
    row("Programming", "TypeScript, JavaScript, PHP, Python, Dart")
    row("Markup", "HTML, CSS, Blade")

    # language bar
    langs = stats["languages"]
    total = sum(l[1] for l in langs) or 1
    top = langs[:3]
    other = total - sum(l[1] for l in top)
    segs = [(n, s / total, c) for n, s, c in top] + ([("Other", other / total, "#8b949e")] if other > 0 else [])
    bar_w, bx = width_chars * CHW, tx
    y += 4
    for n, frac, c in segs:
        w = bar_w * frac
        out.append(f'<rect x="{bx:.1f}" y="{y - 11:.1f}" width="{max(w, 2):.1f}" height="12" fill="{c}"/>')
        bx += w
    y += LH
    legend = []
    for n, frac, c in segs:
        legend += [("● ", c, False), (f"{n} {round(frac * 100)}%   ", DIM, False)]
    text(tx, y, legend, size=12)
    y += LH
    gap(0.4)
    header("Now")
    row("Building", "Mazad: NestJS services + Next.js admin")
    row("Learning", "System design, observability, CI/CD")
    gap()
    header("GitHub Stats")
    sep = (" | ", BORDER, False)
    text(tx, y, [("Repos ", KEY, False), (str(stats["repos"]), VAL, False), sep,
                 ("Stars ", KEY, False), (str(stats["stars"]), VAL, False), sep,
                 ("Followers ", KEY, False), (str(stats["followers"]), VAL, False), sep,
                 ("Following ", KEY, False), (str(stats["following"]), VAL, False)])
    y += LH
    text(tx, y, [("Contributions (1y) ", KEY, False), (f"{stats['contributions']:,}", VAL, False), sep,
                 ("PRs ", KEY, False), (f"{stats['prs']:,}", VAL, False), sep,
                 ("Issues ", KEY, False), (str(stats["issues"]), VAL, False)])
    y += LH * 1.2

    # colour palette blocks (terminal colours)
    dark = ["#484f58", "#ff7b72", "#3fb950", "#d29922", "#58a6ff", "#bc8cff", "#39c5cf", "#b1bac4"]
    light = ["#6e7681", "#ffa198", "#56d364", "#e3b341", "#79c0ff", "#d2a8ff", "#56d4dd", "#ffffff"]
    for i, (a, b) in enumerate(zip(dark, light)):
        out.append(f'<rect x="{tx + i * 22}" y="{y - 12:.1f}" width="22" height="13" fill="{a}"/>')
        out.append(f'<rect x="{tx + i * 22}" y="{y + 1:.1f}" width="22" height="13" fill="{b}"/>')

    # prompt with blinking cursor
    py = H - 30
    out.append(f'<line x1="{ix}" y1="{py - 22}" x2="{W - 40}" y2="{py - 22}" stroke="{BORDER}"/>')
    prompt = [("visitor", PROMPT, False), ("@", TXT, False), (LOGIN, KEY, True), (":", TXT, False), ("~", VAL, False), ("$ ", TXT, False)]
    text(ix, py, prompt)
    cursor_x = ix + CHW * len("visitor@" + LOGIN + ":~$ ")
    out.append(
        f'<rect x="{cursor_x:.1f}" y="{py - 12}" width="8" height="15" fill="{KEY}">'
        '<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.5;1" dur="1.1s" repeatCount="indefinite"/></rect>'
    )

    avatar = pixel_avatar(iw, ih)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}" role="img" aria-label="{LOGIN} terminal card">
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="10" fill="{PANEL}" stroke="{BORDER}"/>
<rect x="{ix - 2}" y="{iy - 2}" width="{iw + 4}" height="{ih + 4}" fill="{BG}"/>
<image x="{ix}" y="{iy}" width="{iw}" height="{ih}" preserveAspectRatio="xMidYMid slice" style="image-rendering:pixelated" href="{avatar}"/>
{chr(10).join(out)}
</svg>
'''
    OUT.write_text(svg, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(svg) // 1024} KB)")


if __name__ == "__main__":
    build(fetch_stats())
