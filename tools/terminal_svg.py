#!/usr/bin/env python3
"""Render the terminal-style SVGs used by the profile README.

    python3 tools/terminal_svg.py              # writes assets/boot.svg and assets/beesay.svg
    python3 tools/terminal_svg.py --static     # final frame only, no animation (for previews)
    python3 tools/terminal_svg.py --gitlog USER [--hide REPO ...]  # writes assets/gitlog.svg from USER's recent public commits

Plain SVG + SMIL only, so it still animates inside GitHub's <img> sandbox
(no scripts, no web fonts, no external requests).
"""
import argparse
import json
import os
import unicodedata
import urllib.parse
import urllib.request
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FONT = ("ui-monospace, 'SF Mono', Menlo, Consolas, 'DejaVu Sans Mono', "
        "'PingFang SC', 'Microsoft YaHei', 'Noto Sans CJK SC', monospace")
BG, BAR, EDGE = "#0b0f0c", "#141c16", "#24402c"
GREEN, DIM, AMBER, WHITE = "#4af626", "#2f8f3a", "#ffb000", "#d7ffd9"
FS, LH = 14, 20       # font size and line height of the terminal text
CW = FS * 0.6         # width of one ASCII cell in a typical monospace font
PAD = 24              # left padding inside the window
BAR_H = 32            # title bar height

STATIC = False


def cells(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def text(x, y, s, fill=GREEN, size=FS, bold=False, anchor=None):
    extra = ' font-weight="bold"' if bold else ""
    extra += f' text-anchor="{anchor}"' if anchor else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}"{extra} '
            f'xml:space="preserve">{escape(s)}</text>')


def appear(t, body):
    """Hidden until t seconds, then shown for good."""
    if STATIC:
        return f"<g>{body}</g>"
    return (f'<g opacity="0"><set attributeName="opacity" to="1" begin="{t:.2f}s" fill="freeze"/>'
            f"{body}</g>")


def cursor(x, y, begin, xs=None, step=0.0, end=None):
    """Block cursor: follows the typed characters, then blinks; hidden after `end`."""
    if STATIC:
        return ""
    move = ""
    if xs:
        move = (f'<animate attributeName="x" values="{";".join(f"{v:.1f}" for v in xs)}" '
                f'dur="{step * len(xs):.2f}s" begin="{begin:.2f}s" fill="freeze" calcMode="discrete"/>')
    hide = f'<set attributeName="visibility" to="hidden" begin="{end:.2f}s" fill="freeze"/>' if end else ""
    return (f'<g opacity="0"><set attributeName="opacity" to="1" begin="{begin:.2f}s" fill="freeze"/>{hide}'
            f'<rect x="{x:.1f}" y="{y - FS + 2:.1f}" width="{CW:.1f}" height="{FS + 2}" fill="{GREEN}">{move}'
            f'<animate attributeName="opacity" values="1;0" dur="1s" repeatCount="indefinite" calcMode="discrete"/>'
            f"</rect></g>")


def prompt(y):
    return text(PAD, y, "evan@hive", GREEN, bold=True) + text(PAD + 9 * CW, y, ":~$", WHITE)


def command(uid, y, cmd, t0, step=0.07, end=None):
    """A prompt with `cmd` typed out from t0. Returns (svg, time typing ends)."""
    x = PAD + 13 * CW
    out = appear(max(t0 - 0.3, 0), prompt(y))
    if STATIC:
        return out + text(x, y, cmd, WHITE), t0
    widths = [i * CW for i in range(len(cmd) + 1)]
    widths[-1] += CW  # leave room for glyphs a little wider than the estimate
    out += (f'<clipPath id="{uid}"><rect x="{x:.1f}" y="{y - FS - 2:.1f}" height="{LH}" width="0">'
            f'<animate attributeName="width" values="{";".join(f"{w:.1f}" for w in widths)}" '
            f'dur="{step * len(widths):.2f}s" begin="{t0:.2f}s" fill="freeze" calcMode="discrete"/></rect></clipPath>'
            f'<g clip-path="url(#{uid})">{text(x, y, cmd, WHITE)}</g>')
    out += cursor(x, y, t0, [x + w for w in widths[:-1]] + [x + len(cmd) * CW], step, end)
    return out, t0 + step * len(widths)


def window(w, h, title, body):
    crt = "" if STATIC else (
        f'<rect x="0" y="-80" width="{w}" height="80" fill="url(#band)">'
        f'<animateTransform attributeName="transform" type="translate" values="0 0;0 {h + 80}" '
        f'dur="7s" repeatCount="indefinite"/></rect>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="{FONT}">
<defs>
  <clipPath id="frame"><rect width="{w}" height="{h}" rx="10"/></clipPath>
  <pattern id="scan" width="4" height="3" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" opacity=".35"/></pattern>
  <linearGradient id="band" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{GREEN}" stop-opacity="0"/><stop offset=".5" stop-color="{GREEN}" stop-opacity=".05"/><stop offset="1" stop-color="{GREEN}" stop-opacity="0"/>
  </linearGradient>
  <radialGradient id="vignette" cx=".5" cy=".5" r=".75"><stop offset=".6" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".45"/></radialGradient>
  <filter id="glow" x="-2%" y="-2%" width="104%" height="104%"><feGaussianBlur stdDeviation="1.1" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<g clip-path="url(#frame)">
  <rect width="{w}" height="{h}" fill="{BG}"/>
  <rect width="{w}" height="{BAR_H}" fill="{BAR}"/>
  <circle cx="20" cy="16" r="6" fill="#ff5f56"/><circle cx="40" cy="16" r="6" fill="#ffbd2e"/><circle cx="60" cy="16" r="6" fill="#27c93f"/>
  {text(w / 2, 21, title, DIM, size=13, anchor="middle")}
  <g filter="url(#glow)">{body}</g>
  {crt}
  <rect width="{w}" height="{h}" fill="url(#scan)"/>
  <rect width="{w}" height="{h}" fill="url(#vignette)"/>
</g>
<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="10" fill="none" stroke="{EDGE}"/>
</svg>
'''


# ---------------------------------------------------------------- boot.svg

SCISSORS_OPEN = r"""
  .-""-.                    _.-'
 /      \              _.-'
 \      /\        _.-'
  '-..-'  \  _.-'
           >o<
  .-""-.  /  '-._
 /      \/        '-._
 \      /              '-._
  '-..-'                    '-.
""".strip("\n").split("\n")

SCISSORS_SHUT = r"""
  .-""-.
 /      \
 \      /\
  '-..-'  \_______________________
           >o====================='
  .-""-.  /
 /      \/
 \      /
  '-..-'
""".strip("\n").split("\n")

HAIR_COL = 33  # the lock of hair hangs just past the open blade tips, where the shut blades cross it

INFO = [
    ("Role", "做游戏的程序员 · Unity 客户端"),
    ("Host", "山东师范大学 · 计算机 2026 届"),
    ("Engine", "Unity 6 · C#"),
    ("Shell", "zsh · Claude Code · Codex"),
    ("Packages", "1 只猫 · 1 盘棋 · 1 条蛇 · 1 只蜜蜂"),
    ("Project", "《宫廷理发师》HeirCut · Steam 页已上线"),
    ("Steam", "Is this my name?"),
    ("Motto", "Because it's there."),
]

PALETTE = ["#1d2b20", "#ff5f56", GREEN, AMBER, "#5fafff", "#d670d6", "#5fd7d7", WHITE]


def scissors(x, y0, begin):
    """Scissors that keep snipping a lock of hair; the cut end falls and grows back."""
    def block(lines, color=GREEN):
        return "".join(text(x, y0 + i * LH, line, color) for i, line in enumerate(lines))

    def hair(rows):
        return "".join(text(x + HAIR_COL * CW, y0 + r * LH, ")" if r % 2 else "(", AMBER) for r in rows)

    if STATIC:
        return block(SCISSORS_OPEN) + hair(range(9))
    cycle = f'dur="2.4s" begin="{begin:.2f}s" repeatCount="indefinite"'
    snip = 'keyTimes="0;.5;.67"'  # open until 1.2s, shut until 1.6s, then open again
    gone = 'keyTimes="0;.5"'      # from the snip until the cycle restarts
    return (
        f'<g><animate attributeName="opacity" values="1;0;1" {snip} calcMode="discrete" {cycle}/>{block(SCISSORS_OPEN)}</g>'
        f'<g opacity="0"><animate attributeName="opacity" values="0;1;0" {snip} calcMode="discrete" {cycle}/>{block(SCISSORS_SHUT)}</g>'
        f'<g>{hair(range(0, 3))}</g>'
        f'<g><animate attributeName="opacity" values="1;0" {gone} calcMode="discrete" {cycle}/>{hair(range(3, 5))}</g>'
        f'<g><animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.9;1" {cycle}/>'
        f'<animateTransform attributeName="transform" type="translate" values="0 0;0 0;6 60;6 60" keyTimes="0;.5;.9;1" {cycle}/>'
        f'{hair(range(5, 9))}</g>'
    )


def boot():
    w = 860
    rows_info = 2 + len(INFO) + 1
    top = BAR_H + 28
    h = top + LH * (4 + rows_info + 1) + 18
    y = lambda row: top + row * LH
    out = []

    c1, t = command("c1", y(0), "whoami", 0.4, end=1.2)
    out.append(c1)
    out.append(appear(1.2, text(PAD, y(1), "EvanWong —— No Game No Life", WHITE)))

    c2, t = command("c2", y(3), "neofetch", 1.6, end=2.6)
    out.append(c2)

    t0, base = 2.6, 4
    out.append(appear(t0, scissors(PAD, y(base + 1), t0 + 0.6)))
    ix = PAD + 38 * CW
    lx = ix + 10 * CW
    out.append(appear(t0, text(ix, y(base), "evan", AMBER, bold=True) + text(ix + 4 * CW, y(base), "@", WHITE)
                      + text(ix + 5 * CW, y(base), "hive", AMBER, bold=True)))
    out.append(appear(t0 + 0.05, text(ix, y(base + 1), "-" * 9, DIM)))
    for i, (label, value) in enumerate(INFO):
        row = base + 2 + i
        out.append(appear(t0 + 0.1 + 0.07 * i, text(ix, y(row), label, AMBER, bold=True) + text(lx, y(row), value, WHITE)))
    row = base + 2 + len(INFO)
    swatches = "".join(f'<rect x="{ix + i * 2 * CW:.1f}" y="{y(row) - FS + 3:.1f}" width="{2 * CW:.1f}" height="{FS}" fill="{c}"/>'
                       for i, c in enumerate(PALETTE))
    out.append(appear(t0 + 0.1 + 0.07 * len(INFO), swatches))

    last = base + rows_info + 1
    t_end = t0 + 0.2 + 0.07 * len(INFO)
    out.append(appear(t_end, prompt(y(last))))
    out.append(cursor(PAD + 13 * CW, y(last), t_end))
    return window(w, h, "evan@hive: ~ — zsh", "".join(out))


# -------------------------------------------------------------- beesay.svg

BEE = r"""
        __     __
       /  \   /  \
       \   \ /   /
        '-._Y_.-'
    >=[|||||](o.o)
        " "
""".strip("\n").split("\n")
BEE_WINGS = 4  # the first rows are the wings

# Lines I like; the last one is my GitHub bio
QUOTES = [
    ("也许头脑会出错，但是血脉不会。", "中島 敦《光と風と夢》"),
    ("从前，我不曾为自己的所做所为而后悔过，唯独对于没做的事，总是后悔莫及。", "中島 敦《光と風と夢》"),
    ("后来他“死了”，他那淡淡的形象也就消失，仿佛水消失在水中。", "Jorge Luis Borges《Las ruinas circulares》"),
    ("人生一事无所为则嫌长，有所为则恨短。", "中島 敦《山月記》"),
    ("Because it's there.", "George Mallory，被问为什么要登珠峰"),
]
NO_LINE_START = "，。、；：？！”）》"


def wrap(s, width):
    lines, line = [], ""
    for ch in s:
        if cells(line + ch) > width and ch not in NO_LINE_START:
            lines.append(line)
            line = ""
        line += ch
    return lines + [line]


def beesay():
    w, qfs, qlh = 460, 15, 24
    top = BAR_H + 26
    out = []
    cmd = "fortune quotes | beesay"
    show_at = 0.4 + 0.07 * (len(cmd) + 1) + 0.3
    c, _ = command("c1", top, cmd, 0.4, end=show_at)
    out.append(c)

    bx, by, bw, bh = PAD, top + 18, w - 2 * PAD, 128
    hold = 6.5
    cycle = hold * len(QUOTES)
    quotes = []
    for i, (quote, source) in enumerate(QUOTES):
        lines = wrap(quote, 46)
        body = "".join(text(bx + 18, by + 34 + k * qlh, line, WHITE, size=qfs) for k, line in enumerate(lines))
        body += text(bx + bw - 16, by + bh - 16, "—— " + source, AMBER, size=12, anchor="end")
        if STATIC:
            quotes.append(f"<g>{body}</g>" if i == 0 else "")
            continue
        a, b = 0.4 / cycle, (hold - 0.4) / cycle
        quotes.append(f'<g opacity="0"><animate attributeName="opacity" values="0;1;1;0;0" '
                      f'keyTimes="0;{a:.4f};{b:.4f};{hold / cycle:.4f};1" dur="{cycle}s" '
                      f'begin="{show_at + i * hold:.2f}s" repeatCount="indefinite"/>{body}</g>')
    bubble = (f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="8" fill="{GREEN}" fill-opacity=".04" '
              f'stroke="{GREEN}" stroke-dasharray="6 4"/>' + "".join(quotes))
    tail_y = by + bh + 16
    tail = text(PAD + 16 * CW, tail_y, "\\", GREEN) + text(PAD + 17 * CW, tail_y + LH - 4, "\\", GREEN)
    out.append(appear(show_at, bubble + tail))

    bee_x, bee_y = PAD + 8 * CW, tail_y + 2 * LH
    def rows(lines, first=0):
        return "".join(text(bee_x, bee_y + (first + k) * (LH - 4), line, GREEN) for k, line in enumerate(lines))
    wings, body = rows(BEE[:BEE_WINGS]), rows(BEE[BEE_WINGS:], BEE_WINGS)
    if STATIC:
        bee = wings + body
    else:
        # Hover instead of hopping: sway sideways and bob on different periods so the path keeps
        # changing, lean into the sway, and let the wings shimmer rather than swap shape
        ease = lambda n: 'calcMode="spline" keySplines="' + ";".join([".45 0 .55 1"] * n) + '"'
        cx, cy = bee_x + 11 * CW, bee_y + 3 * (LH - 4)
        trail_y = bee_y + BEE_WINGS * (LH - 4)
        trail = "".join(
            f'<g opacity="0"><animate attributeName="opacity" values="0;.7;0" dur=".9s" begin="{i * 0.3:.1f}s" repeatCount="indefinite"/>'
            f'{text(bee_x + (2 - 2 * i) * CW, trail_y, "-", DIM)}</g>' for i in range(3))
        bee = (f'<g><animateTransform attributeName="transform" type="translate" values="-16 0;16 0;-16 0" keyTimes="0;.5;1" dur="7s" repeatCount="indefinite" {ease(2)}/>'
               f'<g><animateTransform attributeName="transform" type="translate" values="0 -4;0 4;0 -4" keyTimes="0;.5;1" dur="2.4s" repeatCount="indefinite" {ease(2)}/>'
               f'<g><animateTransform attributeName="transform" type="rotate" values="0 {cx:.1f} {cy:.1f};3 {cx:.1f} {cy:.1f};0 {cx:.1f} {cy:.1f};-3 {cx:.1f} {cy:.1f};0 {cx:.1f} {cy:.1f}" '
               f'keyTimes="0;.25;.5;.75;1" dur="7s" repeatCount="indefinite" {ease(4)}/>'
               f'{trail}<g><animate attributeName="opacity" values="1;.55;1" dur=".2s" repeatCount="indefinite"/>{wings}</g>{body}</g></g></g>')
    out.append(appear(show_at, bee))
    h = bee_y + len(BEE) * (LH - 4) + 10
    return window(w, h, "fortune | beesay", "".join(out))


# -------------------------------------------------------------- gitlog.svg

def recent_commits(user, hidden=(), count=6):
    """Latest commits authored by `user` in public repos not in `hidden`, newest first, merge commits skipped."""
    query = urllib.parse.urlencode({"q": f"author:{user}", "sort": "author-date", "order": "desc", "per_page": 50})
    request = urllib.request.Request(f"https://api.github.com/search/commits?{query}",
                                     headers={"Accept": "application/vnd.github+json"})
    if os.environ.get("GITHUB_TOKEN"):
        request.add_header("Authorization", "Bearer " + os.environ["GITHUB_TOKEN"])
    with urllib.request.urlopen(request, timeout=30) as response:
        items = json.load(response)["items"]
    commits = []
    for item in items:
        message = item["commit"]["message"].split("\n")[0]
        # A token that can see private repos gets them in the results too; never show those
        if item["repository"]["private"] or len(item["parents"]) > 1 or item["repository"]["name"] in hidden:
            continue
        commits.append((item["sha"][:7], item["repository"]["name"], message, item["commit"]["author"]["date"][5:10]))
    return commits[:count]


def clip(s, limit):
    if cells(s) <= limit:
        return s
    while cells(s) > limit - 1:
        s = s[:-1]
    return s + "…"


def gitlog(commits):
    w = 860
    top = BAR_H + 28
    h = top + LH * (len(commits) + 2) + 18
    y = lambda row: top + row * LH
    cmd = "git log --oneline -n %d" % len(commits)
    t = 0.4 + 0.07 * (len(cmd) + 1) + 0.3
    c, _ = command("c1", y(0), cmd, 0.4, end=t)
    out = [c]
    width = int((w - 2 * PAD) / CW)
    for i, (sha, repo, message, date) in enumerate(commits):
        row, x = y(1 + i), PAD
        line = text(x, row, "*", AMBER) + text(x + 2 * CW, row, sha, AMBER)
        x += 10 * CW
        line += text(x, row, f"({repo})", GREEN, bold=True)
        x += (len(repo) + 3) * CW
        room = width - int((x - PAD) / CW) - 7
        line += text(x, row, clip(message, room), WHITE)
        line += text(w - PAD, row, date, DIM, anchor="end")
        out.append(appear(t + 0.12 * i, line))
    end = t + 0.12 * len(commits)
    out.append(appear(end, prompt(y(len(commits) + 1))))
    out.append(cursor(PAD + 13 * CW, y(len(commits) + 1), end))
    return window(w, h, "git log — zsh", "".join(out))


def main():
    global STATIC
    parser = argparse.ArgumentParser()
    parser.add_argument("--static", action="store_true", help="render the final frame without animation")
    parser.add_argument("--gitlog", metavar="USER", help="only render gitlog.svg, from USER's recent public commits")
    parser.add_argument("--hide", metavar="REPO", action="append", default=[], help="leave REPO out of gitlog.svg")
    parser.add_argument("--out", default=os.path.join(ROOT, "assets"))
    args = parser.parse_args()
    STATIC = args.static
    os.makedirs(args.out, exist_ok=True)
    targets = [("gitlog.svg", lambda: gitlog(recent_commits(args.gitlog, args.hide)))] if args.gitlog else \
              [("boot.svg", boot), ("beesay.svg", beesay)]
    for name, render in targets:
        svg = render()
        with open(os.path.join(args.out, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print("wrote", os.path.join(args.out, name))


if __name__ == "__main__":
    main()
