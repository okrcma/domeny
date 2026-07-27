import json
import unittest

import fetch_auctions as fa

CSV_NEW = """\
Doména,Znaků,Příhozy,Cena,Datum začátku (UTC)
penicilin.cz,9,0,0,2026-08-11T10:00:00Z
xqzw.cz,4,0,0,2026-08-01T10:00:00Z
zena.cz,4,0,0,2026-08-05T10:00:00Z
"""

CSV_RUNNING = """\
Doména,Znaků,Příhozy,Cena,Konec aukce (UTC)
koka.cz,4,16,1602,2026-07-27T19:24:40.363391Z
zena.cz,4,3,400,2026-07-27T19:10:00Z
"""

DICT_TSV = """\
word\tfreq\tascii
být\t4041154\tbyt
žena\t75288\tzena
byt\t27000\tbyt
penicilin\t120\tpenicilin
"""


class ParseUpcomingTest(unittest.TestCase):
    def test_parses_rows_with_start_and_no_end(self):
        rows = fa.parse_auctions_csv(CSV_NEW, kind="upcoming")
        self.assertEqual(len(rows), 3)
        self.assertEqual(
            rows[0],
            {"domain": "penicilin.cz", "sld": "penicilin",
             "start": "2026-08-11T10:00:00Z", "end": None},
        )

    def test_skips_blank_lines(self):
        self.assertEqual(len(fa.parse_auctions_csv(CSV_NEW + "\n\n", kind="upcoming")), 3)


class ParseRunningTest(unittest.TestCase):
    def test_parses_rows_with_end_and_no_start(self):
        rows = fa.parse_auctions_csv(CSV_RUNNING, kind="running")
        self.assertEqual(
            rows[0],
            {"domain": "koka.cz", "sld": "koka",
             "start": None, "end": "2026-07-27T19:24:40Z"},
        )

    def test_fractional_seconds_are_truncated(self):
        rows = fa.parse_auctions_csv(CSV_RUNNING, kind="running")
        self.assertEqual(rows[1]["end"], "2026-07-27T19:10:00Z")


class InputValidationTest(unittest.TestCase):
    def test_rejects_wrong_kind_header(self):
        with self.assertRaises(ValueError):
            fa.parse_auctions_csv(CSV_RUNNING, kind="upcoming")
        with self.assertRaises(ValueError):
            fa.parse_auctions_csv(CSV_NEW, kind="running")

    def test_rejects_reordered_header_columns(self):
        reordered = "Doména,Znaků,Cena,Příhozy,Datum začátku (UTC)\n"
        with self.assertRaises(ValueError):
            fa.parse_auctions_csv(reordered + "foo.cz,3,0,0,2026-08-01T10:00:00Z\n",
                                  kind="upcoming")

    def test_rejects_wrong_column_count(self):
        header = "Doména,Znaků,Příhozy,Cena,Datum začátku (UTC)\n"
        with self.assertRaises(ValueError):
            fa.parse_auctions_csv(header + "foo.cz,3,0,0\n", kind="upcoming")

    def test_rejects_bad_timestamp(self):
        header = "Doména,Znaků,Příhozy,Cena,Datum začátku (UTC)\n"
        with self.assertRaises(ValueError):
            fa.parse_auctions_csv(header + "foo.cz,3,0,0,11.08.2026 12:00\n",
                                  kind="upcoming")

    def test_rejects_non_cz_domain(self):
        header = "Doména,Znaků,Příhozy,Cena,Datum začátku (UTC)\n"
        with self.assertRaises(ValueError):
            fa.parse_auctions_csv(header + "foo.com,3,0,0,2026-08-01T10:00:00Z\n",
                                  kind="upcoming")

    def test_accepts_bom_crlf_and_casing(self):
        text = "﻿Doména,Znaků,Příhozy,Cena,Datum začátku (UTC)\r\n" \
               "Zena.CZ,4,1,150.00,2026-08-01T10:00:00Z\r\n"
        rows = fa.parse_auctions_csv(text, kind="upcoming")
        self.assertEqual(rows[0]["domain"], "zena.cz")


class IntraFeedDuplicateTest(unittest.TestCase):
    def test_duplicate_domain_within_one_feed_raises(self):
        header = "Doména,Znaků,Příhozy,Cena,Datum začátku (UTC)\n"
        row = "foo.cz,3,0,0,2026-08-01T10:00:00Z\n"
        with self.assertRaises(ValueError):
            fa.parse_auctions_csv(header + row + row, kind="upcoming")


class CliGuardTest(unittest.TestCase):
    def test_csv_running_without_csv_is_rejected(self):
        with self.assertRaises(SystemExit):
            fa.main(["--csv-running", "/nonexistent.csv"])


class MergeRowsTest(unittest.TestCase):
    def test_running_wins_over_upcoming_for_same_domain(self):
        upcoming = fa.parse_auctions_csv(CSV_NEW, kind="upcoming")
        running = fa.parse_auctions_csv(CSV_RUNNING, kind="running")
        merged = fa.merge_rows(upcoming, running)
        by_domain = {r["domain"]: r for r in merged}
        self.assertEqual(len(merged), 4)  # 3 upcoming + koka, zena deduped
        self.assertEqual(by_domain["zena.cz"]["end"], "2026-07-27T19:10:00Z")
        self.assertIsNone(by_domain["zena.cz"]["start"])
        self.assertIn("koka.cz", by_domain)


class LoadDictionaryTest(unittest.TestCase):
    def test_maps_ascii_to_highest_frequency_word(self):
        best = fa.load_dictionary(DICT_TSV)
        self.assertEqual(best["byt"], ("být", 4041154))
        self.assertEqual(best["zena"], ("žena", 75288))


class BuildOutputTest(unittest.TestCase):
    def test_annotates_sorts_and_shapes(self):
        upcoming = fa.parse_auctions_csv(CSV_NEW, kind="upcoming")
        running = fa.parse_auctions_csv(CSV_RUNNING, kind="running")
        best = fa.load_dictionary(DICT_TSV)
        out = fa.build_output(fa.merge_rows(upcoming, running), best,
                              updated="2026-07-27T00:00:00Z")
        self.assertEqual(out["columns"], ["domain", "word", "freq", "start", "end"])
        self.assertEqual(
            out["rows"],
            [
                ["zena.cz", "žena", 75288, None, "2026-07-27T19:10:00Z"],
                ["penicilin.cz", "penicilin", 120, "2026-08-11T10:00:00Z", None],
                ["koka.cz", None, None, None, "2026-07-27T19:24:40Z"],
                ["xqzw.cz", None, None, "2026-08-01T10:00:00Z", None],
            ],
        )
        self.assertEqual(out["source"], [fa.SOURCE_URL_NEW, fa.SOURCE_URL_RUNNING])


class DataChangedTest(unittest.TestCase):
    def _out(self, updated):
        rows = fa.parse_auctions_csv(CSV_NEW, kind="upcoming")
        return fa.build_output(rows, fa.load_dictionary(DICT_TSV), updated=updated)

    def test_same_rows_different_timestamp_is_unchanged(self):
        old = json.dumps(self._out("2026-07-26T00:00:00Z"))
        self.assertFalse(fa.data_changed(old, self._out("2026-07-27T00:00:00Z")))

    def test_different_rows_is_changed(self):
        old = json.dumps(self._out("2026-07-26T00:00:00Z"))
        new = self._out("2026-07-27T00:00:00Z")
        new["rows"] = new["rows"][:-1]
        self.assertTrue(fa.data_changed(old, new))

    def test_changed_source_is_changed(self):
        new = self._out("x")
        old = dict(new, source=["https://elsewhere.example/"])
        self.assertTrue(fa.data_changed(json.dumps(old), new))

    def test_missing_or_invalid_old_file_is_changed(self):
        self.assertTrue(fa.data_changed(None, self._out("x")))
        self.assertTrue(fa.data_changed("not json{", self._out("x")))


class MainEndToEndTest(unittest.TestCase):
    def test_main_writes_once_then_reports_unchanged(self):
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as td:
            td = pathlib.Path(td)
            (td / "new.csv").write_text(CSV_NEW, encoding="utf-8")
            (td / "run.csv").write_text(CSV_RUNNING, encoding="utf-8")
            (td / "dict.tsv").write_text(DICT_TSV, encoding="utf-8")
            out = td / "auctions.json"
            argv = ["--csv", str(td / "new.csv"),
                    "--csv-running", str(td / "run.csv"),
                    "--dictionary", str(td / "dict.tsv"), "--out", str(out)]
            self.assertEqual(fa.main(argv), 0)
            first = out.read_text(encoding="utf-8")
            self.assertEqual(json.loads(first)["rows"][0][0], "zena.cz")
            self.assertEqual(fa.main(argv), 0)
            self.assertEqual(out.read_text(encoding="utf-8"), first)


if __name__ == "__main__":
    unittest.main()
