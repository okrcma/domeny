# Data attribution

## auctions.json

**Source dataset:** CZ.NIC domain auction lists (upcoming and currently
running auctions), public CSV exports of the Doménový prohlížeč service.

**Download URLs:**
`https://www.domenovyprohlizec.cz/cs/auctions/export-csv/new/` (upcoming) and
`https://www.domenovyprohlizec.cz/cs/auctions/export-csv/in_auction/`
(running).

**License:** No explicit license is published for this dataset; database
rights belong to CZ.NIC, z. s. p. o. The list is publicly available without
authentication and is republished here in transformed form for informational
purposes, with attribution. This project is not affiliated with or endorsed
by CZ.NIC. Will be taken down on request.

**Processing applied (this repository):** both feeds parsed from CSV and
merged (a running row supersedes an upcoming duplicate); joined against
`dictionary.tsv` (each domain's second-level label matched to the
highest-frequency lemma with the same diacritics-stripped form); sorted by
frequency descending, unmatched domains after, by time. Upcoming rows keep
their start timestamp, running rows their end timestamp (truncated to whole
seconds). Bid counts and prices present in the source CSVs are deliberately
dropped: with daily snapshots they would always be stale. Updated
automatically; the `updated` field records the last data change (UTC).

## dictionary.tsv

**Source dataset:** Czech National Corpus — SYN2015 lemma frequency list
(Srovnávací frekvenční seznamy, file `syn2015_lemma_utf8.zip`).

**Download URL:**
`https://wiki.korpus.cz/lib/exe/fetch.php?media=seznamy:syn2015_lemma_utf8.zip`
(linked from `https://wiki.korpus.cz/doku.php/seznamy:srovnavaci_seznamy`)

**Downloaded:** 2026-07-27

**License:** Creative Commons Attribution 4.0 International (CC BY 4.0).
The source page states (Czech): „Toto dílo podléhá licenci Creative Commons
CC BY 4.0 International" and links to
<http://creativecommons.org/licenses/by/4.0/>.

**Required citation (as specified on the source page):**

> Český národní korpus: *Srovnávací frekvenční seznamy*. Ústav Českého
> národního korpusu FF UK, Praha 2016.

**Source format:** 8 tab-separated columns per row: rank, lemma, absolute
frequency in SYN2015, total recalculated frequency, partial recalculated
frequencies for fiction / non-fiction / journalism, frequency characteristic.
The source list only includes lemmas with frequency ≥ 10.

**Processing applied (this repository):**

- Kept columns: lemma and its **absolute frequency in SYN2015** (column 3;
  an integer count of occurrences, not per-million).
- Filtered to lemmas consisting solely of lowercase Czech letters
  (`a–z` plus `á č ď é ě í ň ó ř š ť ú ů ý ž`), length ≥ 2. Entries with
  uppercase letters (proper nouns/abbreviations), digits, punctuation, or
  non-Czech characters were dropped (45,502 of 126,973 rows dropped).
- Added an `ascii` column: the lemma NFD-normalized with combining marks
  removed (diacritics stripped to plain a–z).
- If duplicate lemmas had occurred they would have been summed; in practice
  the filtered source contained no duplicates (81,471 rows in = 81,471 out).
- Sorted by frequency descending. A cap of the top 100,000 lemmas is
  configured but was not reached (81,471 rows total).
