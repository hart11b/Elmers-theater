"""Build the public Elmer's Theater page from the Screening Room artifact's index.html.

Usage: python3 build.py path/to/artifact-index.html
Writes index.html here. Posters live in posters/ with the same names as in the artifact.
"""
import sys

src = open(sys.argv[1], encoding="utf-8").read()
swaps = [
    ("<title>Screening Room</title>", "<title>Elmer’s Theater</title>"),
    ("<h1>Screening <em>Room</em></h1>", "<h1>Elmer’s <em>Theater</em></h1>"),
]
for old, new in swaps:
    if old not in src:
        sys.exit(f"build.py: expected text not found: {old}")
    src = src.replace(old, new)
open("index.html", "w", encoding="utf-8").write(src)
print("wrote index.html")
