"""Exercise the real saved edition at its Pages path, including mobile and no JavaScript."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import tempfile
import threading

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    screenshots = ROOT / "browser-checks"
    screenshots.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / "businessbench").symlink_to(ROOT / "dist", target_is_directory=True)
        (root / "assets").mkdir()
        (root / "assets/tool-metrics.js").touch()
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), partial(QuietHandler, directory=root)
        )
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{server.server_port}/businessbench/"
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    executable_path=os.environ.get("CHROMIUM_PATH")
                )
                page = browser.new_page(viewport={"width": 1280, "height": 900})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(url)
                expect(page.get_by_role("heading", level=1)).to_have_text(
                    "How does your business compare?"
                )
                expect(page.locator("#cohort")).to_contain_text("businesses · Canada")
                page.screenshot(path=str(screenshots / "desktop.png"))
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.locator("#industry-find").bounding_box()["y"] < 844
                assert page.locator(".kpi strong").first.bounding_box()["y"] < 824
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                )
                page.screenshot(path=str(screenshots / "mobile.png"))
                page.locator("#industry-find").fill("7225")
                page.locator("#industry-matches").get_by_role(
                    "link",
                    name="Full-service restaurants and limited-service eating places · 7225",
                    exact=True,
                ).click()
                assert page.url == url + "records/7225/"
                expect(page.locator("h1")).to_contain_text("financial benchmarks")
                expect(page.locator("#cohort")).to_contain_text("Canada")
                initial_mean = page.locator(".kpi strong").first.inner_text()
                page.locator("#region").select_option("35")
                expect(page.locator("#cohort")).to_contain_text("Ontario")
                assert page.url.endswith("records/7225/?area=35")
                page.reload()
                expect(page.locator("#region")).to_have_value("35")
                private_requests = []
                page.on("request", lambda req: private_requests.append(req.url))
                page.locator("#revenue").fill("120000")
                page.locator("#expenses").fill("84000")
                page.get_by_role("button", name="Compare my margin").click()
                expect(page.locator("#answer")).to_contain_text("Your margin is 30.0%.")
                page.locator("#expenses").fill("130000")
                expect(page.locator("#answer")).to_contain_text("Your margin is -8.3%.")
                page.locator("#region").select_option("00")
                expect(page.locator(".kpi strong").first).to_have_text(initial_mean)
                assert page.url == url + "records/7225/"
                assert not any(
                    "120000" in req or "84000" in req or "130000" in req
                    for req in private_requests
                )
                page.set_viewport_size({"width": 320, "height": 700})
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                )
                page.goto(url + "records/")
                page.locator("#directory-filter").fill("541920")
                expect(page.locator("[data-search]:visible").first).to_contain_text(
                    "Photographic services"
                )
                page.locator("#directory-filter").fill("nonexistentind")
                expect(page.locator("#directory-count")).to_have_text("0 profiles")
                static = browser.new_page(
                    java_script_enabled=False, viewport={"width": 390, "height": 844}
                )
                static.goto(url)
                expect(
                    static.get_by_role("link", name="Browse all industries")
                ).to_be_visible()
                expect(static.locator("#industry-find")).to_be_hidden()
                expect(static.locator("#revenue")).to_be_hidden()
                static.goto(url + "records/7225/")
                expect(static.locator("#cohort")).to_contain_text("businesses · Canada")
                static.get_by_text("Published regions for", exact=False).click()
                expect(static.get_by_text("Ontario", exact=True).last).to_be_visible()
                expect(
                    static.get_by_role("link", name="Download benchmark figures (CSV)")
                ).to_have_attribute("href", "../../data/benchmarks.csv")
                static.get_by_role("link", name="Incorporation fees", exact=True).click()
                expect(static.locator("h1")).to_contain_text("incorporate")
                expect(static.get_by_text("$260.52", exact=True)).to_be_visible()
                page.goto(url + "fees.html")
                page.locator("#registry").select_option(label="Ontario")
                page.locator("#kind").select_option("word")
                expect(page.locator("#fee-answer")).to_contain_text("supplier")
                page.locator("#quote").fill("24.95")
                expect(page.locator("#fee-answer")).to_contain_text("$324.95")
                page.locator("#registry").select_option(label="British Columbia")
                expect(page.locator("#quote")).to_be_hidden()
                expect(page.locator("#fee-answer")).to_contain_text("$380.00")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                assert not errors, errors
                browser.close()
        finally:
            server.shutdown()
    print(
        "Browser checks passed for first view, search, region, private comparison, mobile and script-free access."
    )


if __name__ == "__main__":
    main()
