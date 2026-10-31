# Elmer's Theater

The movie library for Elmer's home theater: https://hart11b.github.io/Elmers-theater/

## Add a movie

1. Open **https://github.com/hart11b/Elmers-theater/edit/main/add-movies.csv** (bookmark this on your phone).
2. Add a line at the bottom: `Title, Year, Format, Location`, e.g. `M3GAN, 2022, 4K, Kaleidescape`.
   Only the title is required. Add `, tv` at the end for a TV series.
3. Tap **Commit changes…**, then **Commit changes** again.

About a minute later GitHub looks it up on TMDB, adds the poster, rating, runtime, director, genres and a one-line synopsis, removes the line from the list, and updates the site. Anything it can't find stays in the list marked `# NOT FOUND`. Fix the spelling or add the year and commit again.

## Fix or remove a movie

Open **https://github.com/hart11b/Elmers-theater/edit/main/data/library.json**. Each movie is one line. Change a field, or delete the whole line to remove it, then commit. The site rebuilds automatically.

Useful fields: `t` title, `y` year, `r` rating, `fmt` formats, `loc` where it lives, `nd` nudity (0 none, 1 unconfirmed, 2 yes).

## Setup checklist

- The TMDB key must be saved as the repository secret `TMDB_API_KEY`: https://github.com/hart11b/Elmers-theater/settings/secrets/actions
- To see whether an update ran, or why it failed: https://github.com/hart11b/Elmers-theater/actions
- Don't rename this repo or the GitHub account. The QR code plaque points to this address.

## How it works

`.github/workflows/update-library.yml` runs `tools/update.py` whenever `add-movies.csv` or `data/library.json` changes. It needs the TMDB key saved as the repository secret `TMDB_API_KEY`.
