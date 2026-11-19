// How the cost and context numbers are written. Costs are in US dollars:
// "$0.012" under a dollar, "<$0.001" below a tenth of a cent, "$1.24" from a
// dollar up.

export function formatCost(dollars: number): string {
  if (dollars >= 1) return `$${dollars.toFixed(2)}`;
  if (dollars === 0) return "$0.000";
  if (dollars < 0.001) return "<$0.001";
  return `$${dollars.toFixed(3)}`;
}

/** A token count is an estimate, so it is rounded: "≈38,400". */
export function formatTokens(tokens: number): string {
  const rounded = tokens >= 1000 ? Math.round(tokens / 100) * 100 : tokens;
  return rounded.toLocaleString("en-US");
}

/** "29 Oct 2026" */
export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}
