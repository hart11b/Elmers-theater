"""Update Elmer's Theater from the files you edit on GitHub.

1. Movies listed in add-movies.csv are looked up on TMDB, get a poster and
   details, and are added to data/library.json. Their lines are then removed
   from the CSV. Lines TMDB can't match stay in the CSV, marked "# NOT FOUND".
2. index.html is rebuilt from data/library.json, so edits or removals you make
   directly in that file show up on the site too.

Needs the TMDB_API_KEY environment variable (a TMDB v3 API key or v4 read token).
Run from the repository root: python3 tools/update.py
"""
import csv
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

LIBRARY = "data/library.json"
ADD_CSV = "add-movies.csv"
PAGE = "index.html"
POSTERS = "posters"

FORMATS = ["4K", "Blu-ray", "DVD", "HD", "SD", "Digital"]
LOCATIONS = ["Kaleidescape", "Binder", "Original case", "Amazon", "iTunes",
             "Movies Anywhere", "Fandango", "Unsorted"]
RATINGS = ["G", "PG", "PG-13", "R", "NR", "TV-14", "TV-MA"]
GENRE_MAP = {
    "Science Fiction": ["Sci-Fi"], "Sci-Fi & Fantasy": ["Sci-Fi", "Fantasy"],
    "Action & Adventure": ["Action", "Adventure"], "War & Politics": ["War"],
    "Kids": ["Family"], "Music": ["Music"], "TV Movie": [], "Foreign": [],
    "News": [], "Reality": [], "Soap": [], "Talk": [],
}
KNOWN_GENRES = {"Action", "Adventure", "Animation", "Biography", "Comedy", "Crime",
                "Documentary", "Drama", "Family", "Fantasy", "History", "Horror",
                "Music", "Mystery", "Romance", "Sci-Fi", "Sport", "Thriller",
                "War", "Western"}
LANGUAGES = {"ko": "Korean", "ja": "Japanese", "de": "German", "fr": "French",
             "es": "Spanish", "it": "Italian", "zh": "Chinese", "cn": "Chinese",
             "hi": "Hindi", "sv": "Swedish", "da": "Danish", "no": "Norwegian",
             "ru": "Russian", "pt": "Portuguese", "th": "Thai", "uk": "Ukrainian",
             "pl": "Polish", "nl": "Dutch", "tr": "Turkish", "fa": "Persian"}
HEADER = """# Add movies here, one per line: Title, Year, Format, Location, Type
# Only Title is required. Year helps TMDB find the right one.
# Format: 4K, Blu-ray, DVD, HD, SD or Digital (default 4K). Use / for more than one, e.g. 4K/Digital
# Location: Kaleidescape, Binder, Original case, Amazon, iTunes, Movies Anywhere or Fandango (default Kaleidescape)
# Type: movie or tv (default movie)
# Example: M3GAN, 2022, 4K, Kaleidescape
# After you commit, GitHub adds them with posters in about a minute and removes them from this list.
"""

KEY = os.environ.get("TMDB_API_KEY", "").strip()


def tmdb(path, **params):
    headers = {"Accept": "application/json"}
    if KEY.startswith("eyJ"):  # v4 read access token
        headers["Authorization"] = "Bearer " + KEY
    else:
        params["api_key"] = KEY
    url = "https://api.themoviedb.org/3" + path + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
        return json.load(r)


def one_sentence(text, limit=140):
    text = " ".join((text or "").split())
    if not text:
        return ""
    first = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    if len(first) <= limit:
        return first
    cut = first[:limit - 1].rsplit(" ", 1)[0].rstrip(",;:")
    return cut + "…"


def genres(tmdb_genres, kind):
    out = []
    for g in tmdb_genres:
        for name in GENRE_MAP.get(g["name"], [g["name"]]):
            if name in KNOWN_GENRES and name not in out:
                out.append(name)
    if kind == "tv":
        out.insert(0, "TV")
    return out[:5]


def us_rating(details, kind):
    if kind == "movie":
        for country in details.get("release_dates", {}).get("results", []):
            if country["iso_3166_1"] == "US":
                for rel in country["release_dates"]:
                    if rel.get("certification") in RATINGS:
                        return rel["certification"]
    else:
        for c in details.get("content_ratings", {}).get("results", []):
            if c["iso_3166_1"] == "US" and c.get("rating") in RATINGS:
                return c["rating"]
    return "NR"


def parse_list(value, allowed, default):
    items = [v.strip() for v in re.split(r"[/;|]", value or "") if v.strip()]
    lookup = {a.lower(): a for a in allowed}
    picked = [lookup[i.lower()] for i in items if i.lower() in lookup]
    return picked or [default]


def lookup(title, year, kind):
    search = tmdb(f"/search/{kind}", query=title,
                  **({"year" if kind == "movie" else "first_air_date_year": year} if year else {}))
    results = search.get("results", [])
    if not results and year:
        results = tmdb(f"/search/{kind}", query=title).get("results", [])
    if not results:
        return None
    best = results[0]
    extra = "release_dates,credits" if kind == "movie" else "content_ratings,credits"
    return tmdb(f"/{kind}/{best['id']}", append_to_response=extra)


def build_entry(row, details, kind, new_id):
    title = details.get("title") or details.get("name")
    date = details.get("release_date") or details.get("first_air_date") or ""
    if kind == "movie":
        director = ", ".join(c["name"] for c in details.get("credits", {}).get("crew", [])
                             if c.get("job") == "Director")
        runtime = details.get("runtime") or None
    else:
        director = ", ".join(c["name"] for c in details.get("created_by", []))
        runtime = None
    g = genres(details.get("genres", []), kind)
    lang = LANGUAGES.get(details.get("original_language", "en"), "")
    if lang and "International" not in g:
        g.append("International")
    entry = {
        "t": title, "y": int(date[:4]) if date[:4].isdigit() else (row["year"] or None),
        "r": us_rating(details, kind), "rt": runtime, "g": g, "d": director,
        "s": one_sentence(details.get("overview")),
        "fmt": parse_list(row["format"], FORMATS, "4K"), "hdr": None,
        "loc": parse_list(row["location"], LOCATIONS, "Kaleidescape"),
        "n": 1, "ed": [], "k": kind, "src": [row["title"]], "id": new_id, "nd": 1,
    }
    if lang:
        entry["lang"] = lang
    return entry


def save_poster(details, entry):
    poster = details.get("poster_path")
    if not poster:
        return
    path = f"{POSTERS}/p{entry['id']}.jpg"
    with urllib.request.urlopen("https://image.tmdb.org/t/p/w342" + poster, timeout=60) as r:
        data = r.read()
    with open(path, "wb") as f:
        f.write(data)
    entry["pz"] = path


def read_rows():
    if not os.path.exists(ADD_CSV):
        return []
    rows = []
    with open(ADD_CSV, encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            cells = next(csv.reader(io.StringIO(line), skipinitialspace=True)) + [""] * 5
            title, year, fmt, loc, kind = (c.strip() for c in cells[:5])
            if title.lower() == "title":
                continue
            rows.append({"line": line.rstrip("\n"), "title": title,
                         "year": int(year) if year.isdigit() else None,
                         "format": fmt, "location": loc,
                         "kind": "tv" if kind.lower() in ("tv", "series", "show") else "movie"})
    return rows


def write_library(lib):
    with open(LIBRARY, "w", encoding="utf-8") as f:
        f.write("[\n" + ",\n".join(json.dumps(b, ensure_ascii=False, separators=(",", ":"))
                                   for b in lib) + "\n]\n")


def rebuild_page(lib):
    page = open(PAGE, encoding="utf-8").read()
    base = json.dumps(lib, ensure_ascii=False, separators=(",", ":"))
    new, count = re.subn(r"const BASE=\[.*?\];\n", lambda m: "const BASE=" + base + ";\n",
                         page, count=1, flags=re.S)
    if count != 1:
        sys.exit("update.py: could not find the library in index.html")
    if new != page:
        open(PAGE, "w", encoding="utf-8").write(new)
        print("rebuilt index.html")


def main():
    lib = json.load(open(LIBRARY, encoding="utf-8"))
    rows = read_rows()
    keep, added = [], []
    if rows and not KEY:
        sys.exit("update.py: TMDB_API_KEY is not set, so new movies can't be looked up")
    for row in rows:
        try:
            details = lookup(row["title"], row["year"], row["kind"])
        except urllib.error.URLError as e:
            print(f"TMDB error for {row['title']}: {e}")
            keep.append(row["line"])
            continue
        if not details:
            print(f"Not found on TMDB: {row['title']}")
            keep.append(f"# NOT FOUND (check spelling or add the year): {row['line']}")
            continue
        new_id = max((b["id"] for b in lib), default=-1) + 1
        entry = build_entry(row, details, row["kind"], new_id)
        if any(b["t"] == entry["t"] and b["y"] == entry["y"] for b in lib):
            print(f"Already in the library: {entry['t']} ({entry['y']})")
            continue
        save_poster(details, entry)
        lib.append(entry)
        added.append(f"{entry['t']} ({entry['y']})")
        print(f"Added {entry['t']} ({entry['y']})" + ("" if entry.get("pz") else " without a poster"))
    if rows:
        write_library(lib)
        with open(ADD_CSV, "w", encoding="utf-8") as f:
            f.write(HEADER + "".join(line + "\n" for line in keep))
    rebuild_page(lib)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary and added:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("### Added\n" + "".join(f"- {a}\n" for a in added))


if __name__ == "__main__":
    main()
