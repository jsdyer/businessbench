import { comparison, matching, money, pct } from "./model.mjs";
const $ = (selector) => document.querySelector(selector);
const root = document.body.dataset.root;
const finder = $("#industry-find");
if (finder) {
  let pending;
  let sequence = 0;
  finder.addEventListener("input", async () => {
    const request = ++sequence;
    const out = $("#industry-matches");
    const status = $("#find-status");
    out.replaceChildren();
    if (!finder.value.trim()) {
      status.textContent = "";
      return;
    }
    try {
      pending ??= fetch(root + "data/industries.json").then((r) => {
        if (!r.ok) throw Error();
        return r.json();
      });
      const rows = matching(await pending, finder.value);
      if (request !== sequence) return;
      status.textContent = rows.length
        ? rows.length.toLocaleString() +
          " matching profiles. Showing " +
          Math.min(6, rows.length) +
          "."
        : "No matching published industry. Try a broader industry name or NAICS code.";
      for (const row of rows.slice(0, 6)) {
        const li = document.createElement("li"),
          a = document.createElement("a");
        a.href = root + "records/" + row.code + "/";
        a.textContent = row.name + " · " + row.code;
        li.append(a);
        out.append(li);
      }
    } catch {
      pending = null;
      status.textContent =
        "Open all industry profiles below to browse the saved edition.";
    }
  });
}
const filter = $("#directory-filter");
if (filter) {
  const rows = [...document.querySelectorAll("[data-search]")];
  filter.addEventListener("input", () => {
    let count = 0;
    const terms = filter.value.toLowerCase().trim().split(/\s+/);
    for (const row of rows) {
      row.hidden = !terms.every((term) => row.dataset.search.includes(term));
      if (!row.hidden) count++;
    }
    $("#directory-count").textContent = count.toLocaleString() + " profiles";
  });
}
const dataNode = $("#profile-data");
if (dataNode) {
  const { areas, geos } = JSON.parse(dataNode.textContent);
  const region = $("#region"),
    form = $("#compare");
  const url = new URL(location.href);
  if (Object.hasOwn(areas, url.searchParams.get("area")))
    region.value = url.searchParams.get("area");
  function recalculate() {
    if (!form.checkValidity()) {
      $("#answer").textContent = "";
      return;
    }
    const result = comparison(
      $("#revenue").valueAsNumber,
      $("#expenses").valueAsNumber,
      areas[region.value],
    );
    if (!result) {
      $("#answer").textContent =
        "Enter positive revenue and non-negative expenses.";
      return;
    }
    const delta = result.diff;
    const message =
      delta === null
        ? "The benchmark margin is unavailable."
        : Math.abs(delta) < 0.05
          ? "This matches the benchmark to one decimal place."
          : Math.abs(delta).toFixed(1) +
            " percentage points " +
            (delta > 0 ? "above" : "below") +
            " the " +
            geos[region.value] +
            " benchmark.";
    $("#answer").textContent =
      "Your margin is " +
      pct(result.margin) +
      ". " +
      message +
      (result.outside
        ? " Your revenue falls outside this publication’s $30,000 to $5 million range."
        : "");
  }
  function update() {
    const row = areas[region.value];
    $("#cohort").textContent =
      row.n.toLocaleString() + " businesses · " + geos[region.value];
    for (const item of document.querySelectorAll("[data-money]"))
      item.textContent = money(row.mean[Number(item.dataset.money)]);
    for (const item of document.querySelectorAll("[data-quality]"))
      item.textContent = row.q[Number(item.dataset.quality)] || "—";
    $("#profit-share").textContent = pct(row.profitable);
    $("#margin").textContent = pct(
      row.mean[2] === null || !row.mean[0]
        ? null
        : (100 * row.mean[2]) / row.mean[0],
    );
    for (const [i, item] of [
      ...document.querySelectorAll("[data-quartile]"),
    ].entries())
      item.textContent = money(row.quartiles[i]);
    if ($("#answer").textContent) recalculate();
  }
  region.addEventListener("change", () => {
    const next = new URL(location.href);
    if (region.value === "00") next.searchParams.delete("area");
    else next.searchParams.set("area", region.value);
    history.replaceState(null, "", next);
    update();
  });
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    recalculate();
  });
  form.addEventListener("input", () => {
    if ($("#answer").textContent) recalculate();
  });
  window.addEventListener("pageshow", update);
  update();
}
