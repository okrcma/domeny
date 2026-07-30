# Dictionary-word .cz domains in auction

**Live site: <https://okrcma.github.io/domeny/>**

A simple static site listing upcoming and currently running CZ.NIC auctions
of expired .cz domains, ranked by how frequent the corresponding Czech word
is — the more common the word, the more interesting the domain.

This project is completely vibe-coded.

## How it works

- `tools/fetch_auctions.py` runs once a day via GitHub Actions: it downloads
  the two public CSV exports (upcoming auctions with start times, running
  auctions with end times), joins them with the frequency dictionary
  `data/dictionary.tsv`, and writes `data/auctions.json`. Bid counts and
  prices are deliberately dropped — daily snapshots would only ever show
  stale values. The file is only rewritten when the data actually changed.
- `index.html` is the entire site: vanilla HTML/CSS/JS, no dependencies, and
  no third-party requests of any kind (no CDNs, fonts, or analytics).
- Matching is exact whole-label only: a domain counts as a dictionary word
  when its name (diacritics-stripped) equals a lemma's diacritics-stripped
  form. Typically only a few dozen of the ~6,800 listed domains match;
  the "jen slovníková slova" toggle controls whether the rest are shown.
  Splitting hyphenated or multi-word domains is a possible future extension.
- Tests: `python3 -m unittest discover -s tools`

## Running locally

```sh
python3 -m http.server 8000
```

and open <http://localhost:8000/>. Opening `index.html` directly doesn't
work: the page loads `data/auctions.json` via `fetch()`, which browsers
block on `file://`.

## Data sources

- **Auction list:** public CSV export of the
  [Doménový prohlížeč](https://www.domenovyprohlizec.cz/) service
  (CZ.NIC, z. s. p. o.).
- **Word frequencies:** Český národní korpus: *Srovnávací frekvenční
  seznamy* (SYN2015). Ústav Českého národního korpusu FF UK, Praha 2016.
  License [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

Licensing and processing details: [`data/ATTRIBUTION.md`](data/ATTRIBUTION.md).

Unofficial project; not operated or endorsed by CZ.NIC. All data is
informational only and may be out of date.
