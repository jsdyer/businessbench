#!/usr/bin/env python3
"""Publish financial profiles and the private comparison calculator from a saved ISED edition."""

import csv
import gzip
from html import escape
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from collectors.ised import GEO
from search_metadata import add_search_metadata
from fees import comparison as fee_comparison

BASE = "https://coolcode.ca/businessbench/"
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
NUMERIC = re.compile(r"\d{2,6}|\d{2}-\d{2}")
LABELS = (
    "Revenue",
    "Total expenses",
    "Net profit or loss",
    "Cost of sales",
    "Operating expenses",
    "Rent",
)
QUALITY = "A excellent · B very good · C good · D acceptable · E use with caution. Grades describe the extent of imputation in the published estimate."


def read(p):
    return json.loads(p.read_text(encoding="utf-8"))


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(value, encoding="utf-8")


def enc(value):
    return (
        json.dumps(value, separators=(",", ":"), ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def a(href, name):
    return f'<a href="{escape(href, quote=True)}">{escape(name)}</a>'


def money(value):
    return f"${value:,.0f}" if value is not None else "Unavailable"


def pct(value):
    return f"{value:.1f}%" if value is not None else "Unavailable"


def margin(cohort):
    revenue, _, profit, *_ = cohort["mean"]
    return 100 * profit / revenue if revenue and profit is not None else None


def read_data(root):
    year = read(root / "data/current.json")["year"]
    folder = root / "data" / str(year)
    meta = read(folder / "edition.json")
    profiles = {}
    if meta["year"] != year:
        raise ValueError("Source edition mismatch")
    for name in meta["shards"]:
        if not re.fullmatch(r"\d{2}\.json\.gz", name):
            raise ValueError("Invalid data shard")
        for row in json.loads(gzip.decompress((folder / name).read_bytes())):
            code = row["code"]
            if (
                code in profiles
                or not NUMERIC.fullmatch(code)
                or "00" not in row["areas"]
            ):
                raise ValueError("Invalid or duplicate national profile")
            profiles[code] = row
    if len(profiles) != meta["industry_count"] or not profiles:
        raise ValueError("Saved coverage mismatch")
    return profiles, meta


def finder(prefix):
    return (
        f'<div class="find"><div class="interactive"><label for="industry-find">Find your industry</label><input id="industry-find" type="search" '
        'autocomplete="off" placeholder="Try restaurants or 7225"><span id="find-status" role="status"></span>'
        '<ul class="pick-list" id="industry-matches"></ul></div>'
        + a(prefix + "records/", "Browse all industries")
        + "</div>"
    )


def sources(meta, profile, prefix):
    r = meta["resources"]
    return (
        '<section class="sources"><h2>Sources and coverage</h2><p>Financial Performance Data is prepared from Canadian business tax records. '
        "This edition combines incorporated and unincorporated businesses with $30,000 to $5 million in annual revenue. "
        "All amounts are Canadian dollars. Publisher amounts in thousands are converted to dollars.</p>"
        f"<p>Reference year <strong>{meta['year']}</strong> · Source files checked {escape(meta['checked_at'][:10])} UTC. "
        "The source is checked monthly. Withheld or missing values appear as unavailable. Method changes can affect comparisons between years.</p>"
        "<p>"
        + a(prefix + "data/benchmarks.csv", "Download benchmark figures (CSV)")
        + " · "
        + a(meta["source"], "ISED open-data edition")
        + " · "
        + a(r["revenue"], "Revenue CSV")
        + " · "
        + a(r["expenses"], "Expenses CSV")
        + " · "
        + a(r["profits"], "Profitable businesses CSV")
        + " · "
        + a(r["dictionary"], "ISED data dictionary")
        + "</p>"
        + "<p>"
        + a(
            "https://ised-isde.canada.ca/app/ixb/cis/performance/rev/"
            + profile["code"]
            + "?wbdisable=true",
            "ISED industry report",
        )
        + " · "
        + a(
            "https://open.canada.ca/en/open-government-licence-canada",
            "Open Government Licence – Canada",
        )
        + "</p></section>"
    )


def report(p, meta, featured=False):
    year = meta["year"]
    areas = p["areas"]
    ca = areas["00"]
    options = "".join(
        f'<option value="{key}">{escape(GEO[key])}</option>'
        for key in GEO
        if key in areas
    )
    labels = ",".join(p["aliases"])
    alias = f" Equivalent NAICS codes: {escape(labels)}." if labels else ""
    heading = "Example industry" if featured else "Industry profile"
    table_rows = "".join(
        f'<tr><th scope="row">{label}</th><td class="amount" data-money="{i}">{money(ca["mean"][i])}</td>'
        f'<td data-quality="{i}">{escape(ca["q"][i] or "—")}</td></tr>'
        for i, label in enumerate(LABELS)
    )
    quartiles = "".join(
        f'<tr><th scope="row">{label}</th><td class="amount" data-quartile>{money(value)}</td></tr>'
        for label, value in zip(
            ("Bottom 25%", "Lower-middle 25%", "Upper-middle 25%", "Top 25%"),
            ca["quartiles"],
        )
    )
    reg = "".join(
        f"<li><strong>{escape(GEO[k])}</strong><br>{r['n']:,} businesses · {money(r['mean'][0])} average revenue</li>"
        for k, r in sorted(areas.items())
    )
    return f"""<section class="report"><div class="report-top"><div><p class="eyebrow">{heading} · {year} · NAICS {p["code"]}</p>
<h2>{escape(p["name"])}</h2><p id="cohort">{ca["n"]:,} businesses · Canada</p></div><div class="interactive"><label for="region">Benchmark region</label><select id="region">{options}</select></div></div>
<div class="kpis"><div class="kpi"><span>Average revenue</span><strong data-money="0">{money(ca["mean"][0])}</strong></div><div class="kpi"><span>Average expenses</span><strong data-money="1">{money(ca["mean"][1])}</strong></div><div class="kpi"><span>Businesses profitable</span><strong id="profit-share">{pct(ca["profitable"])}</strong></div></div>
<p>Businesses in this profile reported <strong>$30,000 to $5 million</strong> in annual revenue.{alias}</p>
<div class="columns"><div><h3>What did businesses report?</h3><table><thead><tr><th scope="col">Annual item</th><th scope="col">Mean CAD</th><th scope="col">Quality</th></tr></thead><tbody>{table_rows}</tbody></table>
<p class="line">Net profit as a share of revenue: <strong id="margin">{pct(margin(ca))}</strong>. This benchmark divides the published average profit by average revenue. Rent is already included in operating expenses.</p>
<details><summary>What the quality grades mean</summary><p>{QUALITY}</p></details></div>
<form class="compare interactive" id="compare"><h3>Compare your business</h3><p>Enter your own annual figures in Canadian dollars. They stay in this browser tab.</p>
<label for="revenue">Your annual revenue ($)</label><input id="revenue" type="number" min="0.01" step="any" inputmode="decimal" required placeholder="e.g. 120000">
<label for="expenses">Your total annual expenses ($)</label><input id="expenses" type="number" min="0" step="any" inputmode="decimal" required placeholder="e.g. 84000">
<button type="submit">Compare my margin</button><output id="answer" aria-live="polite"></output></form></div>
<noscript><p>JavaScript enables the private calculator and region selector. The national figures and regional summary below are available to read.</p></noscript>
<details><summary>Average revenue within each revenue quartile</summary><p>ISED groups businesses by revenue into four equal-sized groups. Values shown are the average within each group.</p><table><thead><tr><th>Revenue group</th><th>Mean CAD</th></tr></thead><tbody>{quartiles}</tbody></table></details>
<details><summary>Published regions for {escape(p["name"])}</summary><ul class="region-list">{reg}</ul><p>Only areas with a published count and average revenue appear. Combined regions overlap their member provinces or territories.</p></details>
</section><script type="application/json" id="profile-data">{enc({"areas": areas, "geos": {k: GEO[k] for k in areas}})}</script>"""


def browse(p, prefix, profiles, examples):
    code = p["code"]
    related = list(examples)
    parent = next(
        (code[:n] for n in range(len(code) - 1, 1, -1) if code[:n] in profiles), None
    )
    if parent:
        neighbours = sorted(
            k
            for k in profiles
            if k != code and k.startswith(parent) and len(k) == len(code)
        )
        related = [parent, *neighbours[:2], *related]
    links = [
        a(prefix + "records/" + k + "/", profiles[k]["name"])
        for k in dict.fromkeys(related)
        if k in profiles and k != code
    ]
    more = ""
    if code == "7225":
        more = (
            "<p>"
            + a(
                "https://coolcode.ca/mainstreetcensus/records/industry-7225/",
                "Restaurant locations with employees by community",
            )
            + " · "
            + a(
                "https://coolcode.ca/mainstreetcensus/records/langley-restaurant-locations/",
                "Compare restaurant locations in the two Langleys",
            )
            + "</p>"
        )
    return (
        '<section class="topic-links"><h2>Keep exploring</h2><p class="tabs">'
        + " ".join(links)
        + "</p>"
        + more
        + "<p>"
        + a(
            "https://coolcode.ca/mainstreetcensus/",
            "Compare employer locations in Main Street Census",
        )
        + " · "
        + a("https://coolcode.ca/wagewindow/", "Look up Canadian occupational wages")
        + "</p></section>"
    )


def build(root=ROOT):
    root = Path(root)
    profiles, meta = read_data(root)
    tool = read(root / "tool.json")
    tpl = (root / "web/index.html").read_text()
    config = read(root / "config/profiles.json")
    feature = config["featured"]
    examples = config["explore"]
    if feature not in profiles or any(k not in profiles for k in examples):
        raise ValueError("Select current NAICS profile codes in config/profiles.json")
    dest = root / "dist"
    with tempfile.TemporaryDirectory(dir=root) as wk:
        stage = Path(wk) / "site"
        shutil.copytree(root / "web", stage)

        def save(path, title, desc, body):
            prefix = "../" * path.count("/") or "./"
            tags = ""
            if path:
                url = BASE + path
                tags = (
                    f'<link rel="canonical" href="{url}"><meta property="og:type" content="website"><meta property="og:title" content="{escape(title, quote=True)}">'
                    f'<meta property="og:description" content="{escape(desc, quote=True)}"><meta property="og:url" content="{url}">'
                )
            out = (
                tpl.replace("{{TITLE}}", escape(title))
                .replace("{{DESCRIPTION}}", escape(desc, quote=True))
                .replace("{{ROOT}}", prefix)
                .replace("{{BODY}}", body)
                .replace("{{META}}", tags)
            )
            if not path:
                dataset = {
                    "@type": "Dataset",
                    "@id": BASE + "#ised",
                    "name": f"ISED Canadian small-business financial benchmarks, {meta['year']}",
                    "isBasedOn": meta["source"],
                    "temporalCoverage": str(meta["year"]),
                    "license": "https://open.canada.ca/en/open-government-licence-canada",
                }
                out = add_search_metadata(
                    out, tool, category="BusinessApplication", datasets=[dataset]
                )
            dest_page = stage / path if path.endswith(".html") else stage / path / "index.html"
            write(dest_page, out)

        save(
            "fees.html", "Compare business incorporation fees in Canada",
            "Compare federal, BC, Ontario and Nova Scotia filing fees for an ordinary numbered or named company, with links to the official registries.",
            fee_comparison(read(root / "config/incorporation-fees.json")),
        )
        selected = profiles[feature]
        hero = (
            '<div class="hero"><div><p class="eyebrow">Canadian small-business benchmarks</p><h1>How does your business compare?</h1>'
            '<p class="lead">Pick an industry to compare revenue, expenses and profit margin with businesses in your region.</p></div>'
            + finder("./")
            + "</div>"
        )
        save(
            "",
            "Compare Canadian Small Business Financial Benchmarks by Industry",
            tool["description"],
            hero
            + report(selected, meta, featured=True)
            + '<p class="line">'
            + a(
                "records/" + feature + "/",
                f"Open the {selected['name'].lower()} profile",
            )
            + "</p>"
            + browse(selected, "./", profiles, examples)
            + sources(meta, selected, "./"),
        )
        items = sorted(
            profiles.values(), key=lambda p: (p["name"].casefold(), p["code"])
        )
        listing = [{k: p[k] for k in ("name", "code", "aliases")} for p in items]
        write(stage / "data/industries.json", enc(listing) + "\n")
        status = {k: meta[k] for k in ("year", "checked_at", "industry_count")}
        status["regional_cohorts"] = sum(len(p["areas"]) for p in items)
        write(stage / "data/status.json", json.dumps(status, indent=2) + "\n")
        with (stage / "data/benchmarks.csv").open(
            "w", encoding="utf-8", newline=""
        ) as f:
            writer = csv.writer(f)
            names = [
                "revenue",
                "expenses",
                "profit",
                "cost_of_sales",
                "operating_expenses",
                "rent",
            ]
            columns = [
                label + suffix for label in names for suffix in ("_cad", "_quality")
            ]
            writer.writerow(
                [
                    "reference_year",
                    "naics",
                    "industry",
                    "geography",
                    "businesses",
                    "profitable_percent",
                    *columns,
                    "bottom_quartile_mean_revenue_cad",
                    "lower_middle_quartile_mean_revenue_cad",
                    "upper_middle_quartile_mean_revenue_cad",
                    "top_quartile_mean_revenue_cad",
                ]
            )
            for p in items:
                for geo, row in sorted(p["areas"].items()):
                    indicators = [
                        v for pair in zip(row["mean"], row["q"]) for v in pair
                    ]
                    writer.writerow(
                        [
                            meta["year"],
                            p["code"],
                            p["name"],
                            GEO[geo],
                            row["n"],
                            row["profitable"],
                            *indicators,
                            *row["quartiles"],
                        ]
                    )
        links = []
        for p in items:
            code = p["code"]
            nam = p["name"]
            count = p["areas"]["00"]["n"]
            revenue = money(p["areas"]["00"]["mean"][0])
            desc = f"Compare revenue, expenses and profit for {count:,} Canadian businesses in {nam} within ISED’s {meta['year']} $30,000 to $5 million cohort."
            intro = f'<div class="hgroup"><p class="eyebrow">{a("../", "Industry profiles")} / NAICS {code}</p><h1>{escape(nam)} financial benchmarks</h1><p class="lead">The {meta["year"]} Canadian cohort included {count:,} businesses averaging {revenue} in annual revenue. Choose a region or compare your own results below.</p></div>'
            save(
                "records/" + code + "/",
                nam + " revenue, expenses and profit in Canada",
                desc,
                intro
                + report(p, meta)
                + browse(p, "../../", profiles, examples)
                + sources(meta, p, "../../"),
            )
            search = (nam + " " + code + " " + " ".join(p["aliases"])).casefold()
            links.append(
                f'<li data-search="{escape(search, quote=True)}">'
                + a("./" + code + "/", nam)
                + f"<small>NAICS {code} · {count:,} businesses</small></li>"
            )
        total = len(items)
        index = (
            f'<p class="eyebrow">ISED · {meta["year"]} financial data</p><h1>Industry financial profiles</h1><p class="lead">Browse {total:,} Canadian industry profiles. Open a report to see its cohort, costs and available provincial benchmarks.</p>'
            '<div class="filters interactive"><label for="directory-filter">Find an industry or NAICS code</label><input type="search" id="directory-filter" placeholder="Try photography or 54192">'
            f'<p id="directory-count" role="status">{total:,} profiles</p></div><ul class="directory">'
            + "".join(links)
            + "</ul>"
        )
        save(
            "records/",
            "Canadian small-business financial profiles by industry",
            f"Explore {total:,} published industry profiles in ISED’s {meta['year']} Canadian small-business financial performance edition.",
            index,
        )
        sitemap = ET.Element(
            "urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        )
        for path in [
            "records/",
            *["records/" + code + "/" for code in sorted(profiles)],
        ]:
            ET.SubElement(ET.SubElement(sitemap, "url"), "loc").text = BASE + path
        (stage / "sitemap.xml").write_bytes(
            ET.tostring(sitemap, encoding="utf-8", xml_declaration=True)
        )
        (stage / ".nojekyll").touch()
        if dest.exists():
            shutil.rmtree(dest)
        stage.rename(dest)
        print(f"Built {total:,} financial profiles and {len(sitemap):,} sitemap URLs")


if __name__ == "__main__":
    build()
