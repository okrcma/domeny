#!/usr/bin/env python3
"""Fetch the public CZ.NIC auction CSV exports and build data/auctions.json.

Two feeds are fetched: upcoming auctions (start times) and currently running
auctions (end times). Rows are joined against data/dictionary.tsv (SYN2015,
CC BY 4.0) and written as compact, deterministic JSON consumed by the static
site. Bid counts and prices are deliberately dropped — with daily snapshots
they would only ever be stale noise. The output file is rewritten only when
the auction data actually changed, so a no-op run leaves the git tree clean.

Stdlib only. Makes exactly two GET requests, paced 1 s apart (none with
--csv/--csv-running).
"""

import argparse
import csv
import io
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SOURCE_URL_NEW = "https://www.domenovyprohlizec.cz/cs/auctions/export-csv/new/"
SOURCE_URL_RUNNING = "https://www.domenovyprohlizec.cz/cs/auctions/export-csv/in_auction/"
# Per repo rules: generic User-Agent, no identifying information outbound.
USER_AGENT = "personal research tool"
REPO_ROOT = Path(__file__).resolve().parent.parent
COLUMNS = ["domain", "word", "freq", "start", "end"]

DOMAIN_RE = re.compile(r"^[a-z0-9-]+\.cz$")
TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d+)?Z$")
EXPECTED_HEADERS = {
    "upcoming": ["Doména", "Znaků", "Příhozy", "Cena", "Datum začátku (UTC)"],
    "running": ["Doména", "Znaků", "Příhozy", "Cena", "Konec aukce (UTC)"],
}


def parse_auctions_csv(text, kind):
    """Parse one export CSV; kind is "upcoming" (start) or "running" (end).

    Fails loudly on any format drift so bad data breaks CI instead of
    reaching the published site. Timestamps are truncated to whole seconds.
    """
    rows = []
    seen = set()
    header_seen = False
    for rec in csv.reader(io.StringIO(text)):
        if not rec or not any(field.strip() for field in rec):
            continue
        if not header_seen:
            header_seen = True
            header = [rec[0].lstrip("﻿").strip(), *(f.strip() for f in rec[1:])]
            if header != EXPECTED_HEADERS[kind]:
                raise ValueError(f"unexpected {kind} CSV header: {rec!r}")
            continue
        if len(rec) != 5:
            raise ValueError(f"expected 5 columns, got {len(rec)}: {rec!r}")
        domain, _chars, _bids, _price, ts = rec
        domain = domain.strip().lower()
        if not DOMAIN_RE.match(domain):
            raise ValueError(f"unexpected domain format: {domain!r}")
        m = TS_RE.match(ts.strip())
        if not m:
            raise ValueError(f"unexpected timestamp: {ts!r}")
        ts = m.group(1) + "Z"
        if domain in seen:
            raise ValueError(f"duplicate domain in {kind} feed: {domain}")
        seen.add(domain)
        rows.append(
            {
                "domain": domain,
                "sld": domain.removesuffix(".cz"),
                "start": ts if kind == "upcoming" else None,
                "end": ts if kind == "running" else None,
            }
        )
    return rows


def merge_rows(upcoming, running):
    """Combine both feeds; a running row wins over an upcoming duplicate."""
    running_domains = {r["domain"] for r in running}
    return running + [r for r in upcoming if r["domain"] not in running_domains]


def load_dictionary(text):
    """Map each ascii form to its highest-frequency dictionary (word, freq)."""
    best = {}
    for i, line in enumerate(text.splitlines()):
        if i == 0 or not line.strip():
            continue
        word, freq, ascii_form = line.split("\t")
        freq = int(freq)
        current = best.get(ascii_form)
        if current is None or freq > current[1]:
            best[ascii_form] = (word, freq)
    return best


def build_output(rows, best, updated):
    """Annotate auction rows with dictionary matches; deterministic order."""
    when = lambda row: row[3] or row[4]
    matched = []
    unmatched = []
    for r in rows:
        hit = best.get(r["sld"])
        row = [r["domain"], hit[0] if hit else None, hit[1] if hit else None,
               r["start"], r["end"]]
        (matched if hit else unmatched).append(row)
    matched.sort(key=lambda row: (-row[2], when(row), row[0]))
    unmatched.sort(key=lambda row: (when(row), row[0]))
    return {
        "source": [SOURCE_URL_NEW, SOURCE_URL_RUNNING],
        "updated": updated,
        "columns": list(COLUMNS),
        "rows": matched + unmatched,
    }


def data_changed(old_text, new_output):
    """True if new_output differs from the previously written JSON, ignoring
    the `updated` timestamp (so unchanged data never dirties the git tree)."""
    if not old_text:
        return True
    try:
        old = json.loads(old_text)
    except json.JSONDecodeError:
        return True
    return any(old.get(key) != new_output[key] for key in ("source", "columns", "rows"))


def fetch_csv(url, timeout=60):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv", type=Path,
                        help="read the upcoming-auctions CSV from a local file")
    parser.add_argument("--csv-running", type=Path,
                        help="read the running-auctions CSV from a local file")
    parser.add_argument("--dictionary", type=Path, default=REPO_ROOT / "data" / "dictionary.tsv")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "auctions.json")
    args = parser.parse_args(argv)
    if args.csv_running and not args.csv:
        parser.error("--csv-running requires --csv")

    if args.csv:
        new_text = args.csv.read_text(encoding="utf-8")
        running_text = (args.csv_running.read_text(encoding="utf-8")
                        if args.csv_running else None)
    else:
        new_text = fetch_csv(SOURCE_URL_NEW)
        time.sleep(1)  # CZ.NIC allows 1 request/second
        running_text = fetch_csv(SOURCE_URL_RUNNING)

    upcoming = parse_auctions_csv(new_text, kind="upcoming")
    running = (parse_auctions_csv(running_text, kind="running")
               if running_text is not None else [])
    rows = merge_rows(upcoming, running)
    best = load_dictionary(args.dictionary.read_text(encoding="utf-8"))
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    output = build_output(rows, best, updated=updated)

    old_text = args.out.read_text(encoding="utf-8") if args.out.exists() else None
    matches = sum(1 for row in output["rows"] if row[1] is not None)
    summary = (f"{len(upcoming)} upcoming + {len(running)} running auctions, "
               f"{matches} dictionary matches")
    if not data_changed(old_text, output):
        print(f"{args.out}: unchanged ({summary})")
        return 0
    tmp = args.out.with_name(args.out.name + ".tmp")
    tmp.write_text(
        json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, args.out)
    print(f"{args.out}: updated — {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
