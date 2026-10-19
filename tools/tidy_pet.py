#!/usr/bin/env python3
"""Tidy the YourTomo cat SVGs for this profile.

YourTomo's rotating hints ("hacking on <repo>", "featured projects ↓", "live stats + graphs ↓")
point at sections this page does not have, and the first one names whatever repo was pushed to
last. Drop them, and point the intro bubble at what is actually further down the page.

    python3 tools/tidy_pet.py dist/pet.svg dist/pet-light.svg
"""
import re
import sys

# One rotating hint: a hidden group that fades in on an 18s loop, with a bubble and its text
HINT = re.compile(r'<g opacity="0"><animate [^>]*dur="18s"[^>]*/><rect [^>]*/><polygon [^>]*/>'
                  r'<text [^>]*>[^<]*</text></g>\n?')
INTRO_OLD = "scroll down for projects + contact"
INTRO_NEW = "scroll down: chess, snake, git log"


def tidy(svg):
    # The cat only shows the intro and the hints while awake, so finding none is fine
    svg = HINT.sub("", svg).replace(INTRO_OLD, INTRO_NEW)
    if "hacking on" in svg:
        raise SystemExit("a 'hacking on' bubble survived; YourTomo's SVG layout changed, update tools/tidy_pet.py")
    return svg


def main():
    for path in sys.argv[1:]:
        with open(path, encoding="utf-8") as f:
            svg = tidy(f.read())
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print("tidied", path)


if __name__ == "__main__":
    main()
