// The small JSON description of a chart that the model writes in a ```chart
// block, and the check that it is what it should be.
//
//   {
//     "type": "line",                      // line, bar or pie
//     "title": "NPV against the discount rate",
//     "xLabel": "Discount rate",           // optional
//     "yLabel": "NPV",                     // optional
//     "format": "currency",                // number (default), currency, percent
//     "currency": "£",                     // optional, for format "currency"
//     "series": ["NPV"],                   // the lines, bar groups or pie values
//     "data": [{ "x": "0%", "NPV": 120 }, { "x": "5%", "NPV": 80 }]
//   }
//
// The model's text isn't trusted: it is parsed, and anything that doesn't match
// is refused with a message, which the page shows under the chart's JSON.

export const MAX_ROWS = 500;
export const MAX_SERIES = 6;

export type ChartType = "line" | "bar" | "pie";
export type ChartFormat = "number" | "currency" | "percent";

export type Row = { x: string } & Record<string, string | number>;

export type ChartSpec = {
  type: ChartType;
  title: string;
  xLabel?: string;
  yLabel?: string;
  format: ChartFormat;
  currency: string;
  series: string[];
  data: Row[];
};

export type ChartResult =
  { ok: true; spec: ChartSpec } | { ok: false; reason: string };

const TYPES: ChartType[] = ["line", "bar", "pie"];
const FORMATS: ChartFormat[] = ["number", "currency", "percent"];

const refuse = (reason: string): ChartResult => ({ ok: false, reason });
const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

export function parseChart(text: string): ChartResult {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    return refuse("it isn't valid JSON");
  }
  if (!isRecord(raw)) return refuse("it should be a JSON object");

  if (!TYPES.includes(raw.type as ChartType))
    return refuse('"type" should be "line", "bar" or "pie"');
  const type = raw.type as ChartType;

  if (typeof raw.title !== "string" || raw.title.trim() === "")
    return refuse('"title" should be some text');

  for (const key of ["xLabel", "yLabel", "currency"] as const)
    if (raw[key] !== undefined && typeof raw[key] !== "string")
      return refuse(`"${key}" should be text`);

  const format = raw.format ?? "number";
  if (!FORMATS.includes(format as ChartFormat))
    return refuse('"format" should be "number", "currency" or "percent"');

  const series = raw.series;
  if (
    !Array.isArray(series) ||
    series.length === 0 ||
    !series.every(
      (name) => typeof name === "string" && name !== "" && name !== "x",
    )
  )
    return refuse('"series" should be a list of names (other than "x")');
  if (new Set(series).size !== series.length)
    return refuse('"series" names should all be different');
  if (series.length > MAX_SERIES)
    return refuse(`"series" can have at most ${MAX_SERIES} names`);
  if (type === "pie" && series.length !== 1)
    return refuse('a pie chart takes exactly one name in "series"');

  const data = raw.data;
  if (!Array.isArray(data) || data.length === 0)
    return refuse('"data" should be a list of rows');
  if (data.length > MAX_ROWS)
    return refuse(`"data" can have at most ${MAX_ROWS} rows`);

  const rows: Row[] = [];
  for (const [index, entry] of data.entries()) {
    if (!isRecord(entry)) return refuse(`row ${index + 1} should be an object`);
    const { x } = entry;
    if (typeof x !== "string" && typeof x !== "number")
      return refuse(`row ${index + 1} needs an "x" (text or a number)`);
    const row: Row = { x: String(x) };
    for (const name of series as string[]) {
      const value = entry[name];
      if (typeof value !== "number" || !Number.isFinite(value))
        return refuse(`row ${index + 1} needs a number for "${name}"`);
      row[name] = value;
    }
    rows.push(row);
  }
  if (type === "pie" && rows.some((row) => (row[series[0]] as number) < 0))
    return refuse("a pie chart can't have negative values");

  return {
    ok: true,
    spec: {
      type,
      title: raw.title,
      xLabel: raw.xLabel as string | undefined,
      yLabel: raw.yLabel as string | undefined,
      format: format as ChartFormat,
      currency: (raw.currency as string | undefined) ?? "£",
      series: series as string[],
      data: rows,
    },
  };
}

/** A number as the chart's format shows it: 1234.5 → "£1,234.50", 0.05 → "5%". */
export function formatValue(
  value: number,
  format: ChartFormat,
  currency: string,
): string {
  if (format === "percent")
    return `${(value * 100).toLocaleString("en-GB", { maximumFractionDigits: 2 })}%`;
  if (format === "currency") {
    const shown = Math.abs(value).toLocaleString("en-GB", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return `${value < 0 ? "-" : ""}${currency}${shown}`;
  }
  return value.toLocaleString("en-GB", { maximumFractionDigits: 4 });
}
