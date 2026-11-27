export function comparison(revenue, expenses, benchmark) {
  if (
    ![revenue, expenses].every(Number.isFinite) ||
    revenue <= 0 ||
    expenses < 0
  )
    return null;
  const margin = (100 * (revenue - expenses)) / revenue;
  const peer =
    benchmark.mean[2] === null || !benchmark.mean[0]
      ? null
      : (100 * benchmark.mean[2]) / benchmark.mean[0];
  if (!Number.isFinite(margin)) return null;
  return {
    margin,
    diff: peer === null ? null : margin - peer,
    outside: revenue < 30000 || revenue > 5000000,
  };
}
export function matching(items, query) {
  const terms = query.trim().toLowerCase().split(/\s+/);
  return items.filter(({ code, name, aliases }) =>
    terms.every((term) =>
      (code + " " + name + " " + aliases.join(" "))
        .toLowerCase()
        .includes(term),
    ),
  );
}
export const money = (value) =>
  value === null
    ? "Unavailable"
    : new Intl.NumberFormat("en-CA", {
        style: "currency",
        currency: "CAD",
        maximumFractionDigits: 0,
      }).format(value);
export const pct = (value) =>
  value === null ? "Unavailable" : value.toFixed(1) + "%";
