"""Collect the latest complete ISED Financial Performance Data annual edition."""

import csv
from datetime import datetime, timezone
import gzip
import json
import math
from pathlib import Path
import re
import tempfile
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
API = "https://open.canada.ca/data/api/3/action/"
SEARCH = (
    API
    + "package_search?"
    + urlencode(
        {"q": "Financial Performance Data", "fq": "organization:ic", "rows": 70}
    )
)
MISSING = {"", "..", "x", "F", "9999", "9999.9", "99999.9", "999999"}
GEO = {
    "00": "Canada",
    "10": "Newfoundland and Labrador",
    "11": "Prince Edward Island",
    "12": "Nova Scotia",
    "13": "New Brunswick",
    "15": "Atlantic Canada",
    "24": "Quebec",
    "35": "Ontario",
    "46": "Manitoba",
    "47": "Saskatchewan",
    "48": "Alberta",
    "49": "Prairies",
    "59": "British Columbia",
    "60": "Yukon",
    "61": "Northwest Territories",
    "62": "Nunavut",
    "63": "Territories combined",
}
RANGES = {"313233": "31-33", "444500": "44-45", "484900": "48-49"}
# Numbered entries are intentionally validated against each year's actual bilingual heading.
COSTS = [
    (122, "total expenses"),
    (129, "net profit/loss"),
    (3, "cost of sales"),
    (38, "operating expenses"),
    (73, "rent"),
]


def fetch(url, path, limit):
    if (
        urlsplit(url).hostname
        not in {"ised-isde.canada.ca", "www.ised-isde.canada.ca", "open.canada.ca"}
        or urlsplit(url).scheme != "https"
    ):
        raise ValueError("Expected an official HTTPS publisher URL")
    req = Request(
        url,
        headers={
            "User-Agent": "CoolCode Business Bench source check (+https://coolcode.ca/businessbench/)"
        },
    )
    with urlopen(req, timeout=90) as incoming, path.open("wb") as outgoing:
        count = 0
        while block := incoming.read(1024 * 1024):
            count += len(block)
            if count > limit:
                raise ValueError("Publisher download exceeds size limit")
            outgoing.write(block)


def discover(packages):
    matches = []
    for item in packages:
        title = item.get("title", "")
        year = re.fullmatch(
            r"Financial Performance Data\s*\(?((?:19|20)\d{2})\)?", title, re.I
        )
        if year and item.get("organization", {}).get("name") == "ic":
            matches.append((int(year[1]), item))
    if not matches:
        raise ValueError("No ISED financial performance edition found")
    return max(matches, key=lambda pair: pair[0])


def urls_for(item, year):
    def find(prefix, suffix="csv"):
        choices = [
            r["url"]
            for r in item["resources"]
            if " ".join(r["name"].lower().split()) == prefix
            and r["url"].lower().endswith("." + suffix)
            and r.get("format", "").lower() == suffix
        ]
        if len(choices) != 1:
            raise ValueError(
                f"Expected one resource for {prefix}, found {len(choices)}"
            )
        return choices[0]

    return {
        "names": find(f"naics descriptors {year}"),
        "revenue": find(f"total revenue {year} 30k 5m"),
        "expenses": find(f"total expenses value {year} 30k 5m"),
        "profits": find(f"profit non profit businesses {year} 30k 5m"),
        "dictionary": find("data dictionary", "txt"),
    }


def number(value, factor=1):
    if value.strip() in MISSING:
        return None
    result = float(value) * factor
    if not math.isfinite(result):
        raise ValueError("Nonfinite benchmark")
    return round(result) if factor == 1000 else result


def dataset(path, headers, year):
    # The publisher CSVs contain bilingual quoted headings with embedded newlines.
    raw = path.read_bytes()
    try:
        raw.decode("utf-8-sig")
        codec = "utf-8-sig"
    except UnicodeDecodeError:
        codec = "cp1252"
    with path.open(encoding=codec, newline="") as handle:
        reader = csv.reader(handle)
        head = [c.strip().casefold().replace("_", " ") for c in next(reader)]
        for index, prefix in headers:
            if not head[index].startswith(prefix):
                raise ValueError(
                    f"{path.name}: changed field at column {index}, expected {prefix}"
                )
        for row in reader:
            if not row or not any(v.strip() for v in row):
                continue
            # The 2024 expenses CSV has a single orphaned incorporated-status marker.
            # It has no industry or year and belongs to a different cohort.
            if year == 2024 and path.name == "expenses" and row == ["2"]:
                continue
            if len(row) != len(head):
                raise ValueError(f"{path.name}: truncated or malformed CSV row")
            if row[-1] == str(year):
                yield row


def eligible(rows):
    for row in rows:
        if row[0] == "3":
            if row[2] not in GEO:
                raise ValueError("Unknown ISED geography " + row[2])
            code = RANGES.get(row[1], row[1])
            if not re.fullmatch(r"\d{2,6}|\d{2}-\d{2}", code):
                raise ValueError("Unexpected NAICS code")
            yield code, row[2], row


def collect(files, year):
    names = {
        r[0]: r[1].strip()
        for r in dataset(
            files["names"],
            [(0, "naics code"), (1, "description english"), (3, "year")],
            year,
        )
    }
    rev_header = [
        (1, "naics code"),
        (3, "whole industry"),
        (4, "whole industry low revenue"),
        (14, "whole industry total revenue"),
        (15, "quality indicator"),
        (16, "bottom quartile total revenue"),
        (34, "year"),
    ]
    industries = {}
    for code, geo, row in eligible(dataset(files["revenue"], rev_header, year)):
        n, revenue = number(row[3]), number(row[14], 1000)
        if n is None or revenue is None or n <= 0:
            continue
        if row[4:6] != ["30", "5000"]:
            raise ValueError("Unexpected cohort revenue band")
        profile = industries.setdefault(code, {"name": names[code], "areas": {}})
        if geo in profile["areas"]:
            raise ValueError("Duplicate revenue cohort")
        profile["areas"][geo] = {
            "n": int(n),
            "mean": [revenue],
            "q": [row[15]],
            "quartiles": [number(x, 1000) for x in row[16:20]],
        }
    ex_header = (
        [(1, "naics code"), (136, "year")]
        + [(idx, name) for idx, name in COSTS]
        + [(idx + 1, "quality indicator") for idx, _ in COSTS]
    )
    for code, geo, row in eligible(dataset(files["expenses"], ex_header, year)):
        target = industries.get(code, {}).get("areas", {}).get(geo)
        if target is not None:
            for i, _ in COSTS:
                value = number(row[i], 1000)
                target["mean"].append(value)
                target["q"].append(row[i + 1] if value is not None else "")
    for code, geo, row in eligible(
        dataset(
            files["profits"],
            [(1, "naics code"), (3, "% of profitable"), (40, "year")],
            year,
        )
    ):
        target = industries.get(code, {}).get("areas", {}).get(geo)
        if target is not None:
            share = number(row[3])
            if share is not None and not 0 <= share <= 100:
                raise ValueError("Unexpected profitable business share")
            target["profitable"] = share
    profiles = []
    duplicates = {}
    for code, item in sorted(industries.items(), key=lambda t: (len(t[0]), t[0])):
        if "00" not in item["areas"]:
            continue
        for cohort in item["areas"].values():
            if (
                len(cohort["mean"]) != 6
                or "profitable" not in cohort
                or any(q not in {"", "A", "B", "C", "D", "E"} for q in cohort["q"])
            ):
                raise ValueError(f"Incomplete financial data for {code}")
        signature = (item["name"], json.dumps(item["areas"], sort_keys=True))
        if signature in duplicates:
            duplicates[signature]["aliases"].append(code)
        else:
            profile = {
                "code": code,
                "aliases": [],
                "name": item["name"],
                "areas": item["areas"],
            }
            profiles.append(profile)
            duplicates[signature] = profile
    return profiles


def install(folder, profiles, meta, target):
    grouped = {}
    for p in profiles:
        grouped.setdefault(p["code"][:2], []).append(p)
    shards = []
    new = folder / "edition"
    new.mkdir()
    for group, rows in sorted(grouped.items()):
        name = group + ".json.gz"
        shards.append(name)
        raw = json.dumps(
            rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        (new / name).write_bytes(gzip.compress(raw, mtime=0))
    meta.update(shards=shards, industry_count=len(profiles))
    (new / "edition.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n"
    )
    target.mkdir(parents=True, exist_ok=True)
    # Collection runs inside an isolated workflow checkout. An unsuccessful validation
    # cannot generate a Pages dispatch or commit a partial public edition.
    for p in new.iterdir():
        p.replace(target / p.name)
    for p in target.glob("*.json.gz"):
        if p.name not in shards:
            p.unlink()


def main():
    with tempfile.TemporaryDirectory(dir=ROOT / "data") as work:
        folder = Path(work)
        fetch(SEARCH, folder / "catalog", 16 * 1024 * 1024)
        content = json.loads((folder / "catalog").read_text())
        year, item = discover(content["result"]["results"])
        urls = urls_for(item, year)
        files = {}
        for key in ["names", "revenue", "expenses", "profits"]:
            files[key] = folder / key
            fetch(urls[key], files[key], 90 * 1024 * 1024)
        profiles = collect(files, year)
        if len(profiles) < 100:
            raise ValueError("Incomplete national edition")
        target = ROOT / "data" / str(year)
        old = ROOT / "data/current.json"
        if old.exists() and json.loads(old.read_text())["year"] > year:
            raise ValueError("Publisher would roll back to an older edition")
        if (target / "edition.json").exists() and len(profiles) < 0.8 * json.loads(
            (target / "edition.json").read_text()
        )["industry_count"]:
            raise ValueError("Review the material coverage change before publication")
        meta = {
            "year": year,
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": "https://open.canada.ca/data/en/dataset/" + item["id"],
            "resources": urls,
        }
        install(folder, profiles, meta, target)
        pending = old.with_suffix(".tmp")
        pending.write_text(json.dumps({"year": year}) + "\n")
        pending.replace(old)
        print(f"Validated {len(profiles):,} profiles in the {year} edition")


if __name__ == "__main__":
    main()
