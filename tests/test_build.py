import csv
from datetime import datetime
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build import BASE, build, margin, money, read_data
from collectors.ised import dataset, discover, number, urls_for


class PublishedBenchmarks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.meta = read_data(ROOT)
        build(ROOT)
        cls.site = ROOT / "dist"

    def test_no_indexable_dead_ends_or_alias_duplicates(self):
        urls = [
            e.text
            for e in ET.parse(self.site / "sitemap.xml").iter()
            if e.tag.endswith("}loc")
        ]
        self.assertEqual(
            set(urls),
            {BASE + "records/"}
            | {BASE + "records/" + code + "/" for code in self.rows},
        )
        self.assertEqual(len(urls), len(set(urls)))
        directory = (self.site / "records/index.html").read_text()
        for code, row in self.rows.items():
            route = "records/" + code + "/"
            self.assertIn('href="./' + code + '/"', directory)
            page = (self.site / route / "index.html").read_text()
            self.assertIn(f'<link rel="canonical" href="{BASE}{route}">', page)
            self.assertIn(money(row["areas"]["00"]["mean"][0]), page)
            for alias in row["aliases"]:
                self.assertNotIn(alias, self.rows)

    def test_download_uses_source_units_and_suppression(self):
        with (self.site / "data/benchmarks.csv").open(newline="") as csv_file:
            rows = list(csv.DictReader(csv_file))
        self.assertEqual(len(rows), sum(len(p["areas"]) for p in self.rows.values()))
        report = next(
            r for r in rows if r["naics"] == "7225" and r["geography"] == "Canada"
        )
        actual = self.rows["7225"]["areas"]["00"]
        self.assertEqual(report["revenue_cad"], str(actual["mean"][0]))
        self.assertEqual(report["profit_quality"], actual["q"][2])
        self.assertEqual(report["reference_year"], str(self.meta["year"]))
        self.assertEqual(margin({"mean": [500, 0, 0]}), 0)
        self.assertIsNone(margin({"mean": [500, 0, None]}))

    def test_home_example_uses_real_data_and_has_public_provenance(self):
        root = (self.site / "index.html").read_text()
        featured = json.loads((ROOT / "config/profiles.json").read_text())["featured"]
        national = self.rows[featured]["areas"]["00"]
        self.assertIn(f"{national['n']:,} businesses · Canada", root)
        self.assertIn(self.meta["source"], root)
        self.assertIn('type="application/ld+json"', root)
        self.assertEqual(root.count('rel="canonical"'), 1)
        self.assertNotRegex(root, r'<input[^>]* name="(?:revenue|expenses)"')
        status = json.loads((self.site / "data/status.json").read_text())
        self.assertEqual(status["checked_at"], self.meta["checked_at"])
        self.assertIsNotNone(datetime.fromisoformat(status["checked_at"]).tzinfo)
        self.assertEqual(status["industry_count"], len(self.rows))


class SourceParsing(unittest.TestCase):
    def test_source_numbers_preserve_signed_profit_and_zero(self):
        self.assertEqual(number("-3.4", 1000), -3400)
        self.assertEqual(number("0.0", 1000), 0)
        for missing in ["", "9999", "99999.9", "999999", "9999.9"]:
            self.assertIsNone(number(missing, 1000))
        with self.assertRaises(ValueError):
            number("nan")

    def test_discovery_chooses_latest_official_named_edition(self):
        items = [
            {
                "title": "Financial Performance Data (2024)",
                "organization": {"name": "ic"},
            },
            {
                "title": "Financial Performance Data 2025",
                "organization": {"name": "ic"},
            },
            {
                "title": "Financial Performance Data 2099",
                "organization": {"name": "other"},
            },
        ]
        self.assertEqual(discover(items), (2025, items[1]))
        with self.assertRaises(ValueError):
            urls_for({"resources": []}, 2025)

    def test_parser_keeps_year_and_rejects_malformed_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "expenses"
            file.write_text("inc,year\n3,2023\n2\n3,2024\n")
            self.assertEqual(
                list(dataset(file, [(0, "inc"), (1, "year")], 2024)), [["3", "2024"]]
            )
            with self.assertRaisesRegex(ValueError, "malformed"):
                list(dataset(file, [(0, "inc")], 2025))
            with self.assertRaisesRegex(ValueError, "changed field"):
                list(dataset(file, [(0, "different")], 2024))


if __name__ == "__main__":
    unittest.main()
