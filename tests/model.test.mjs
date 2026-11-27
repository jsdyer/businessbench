import test from "node:test";
import assert from "node:assert/strict";
import { comparison, matching, money, pct } from "../web/model.mjs";

test("personal margin compares with the ratio of peer means", () => {
  const peer = { mean: [100000, 79000, 20000] };
  assert.deepEqual(comparison(120000, 84000, peer), {
    margin: 30,
    diff: 10,
    outside: false,
  });
  assert.deepEqual(comparison(30000, 33000, peer), {
    margin: -10,
    diff: -30,
    outside: false,
  });
  assert.equal(comparison(5000001, 0, peer).outside, true);
});
test("retains true zero and missing margins as distinct", () => {
  assert.equal(
    comparison(25000, 25000, { mean: [50000, 50000, null] }).diff,
    null,
  );
  assert.equal(comparison(35000, 35000, { mean: [50000, 50000, 0] }).diff, 0);
  for (const values of [
    [0, 2],
    [-20, 5],
    [10, -1],
    [NaN, 2],
    [10, Infinity],
  ]) {
    assert.equal(comparison(...values, { mean: [100, 100, 0] }), null);
  }
  assert.equal(pct(0), "0.0%");
  assert.equal(money(null), "Unavailable");
});
test("finds complete and equivalent industry codes or multiple search terms", () => {
  const firms = [
    { code: "54192", name: "Photographic services", aliases: ["541920"] },
    { code: "12345", name: "Other services", aliases: [] },
  ];
  for (const query of ["541920", "SERVICES photo"])
    assert.deepEqual(matching(firms, query), [firms[0]]);
  assert.deepEqual(matching(firms, "unlisted"), []);
});
