// Unit tests for the check on a chart's JSON. No browser is needed.
import { expect, test } from "@playwright/test";
import {
  MAX_ROWS,
  MAX_SERIES,
  formatValue,
  parseChart,
} from "../src/markdown/chartSpec";

const line = {
  type: "line",
  title: "NPV",
  series: ["NPV"],
  data: [
    { x: "0%", NPV: 120 },
    { x: 5, NPV: 80.5 },
  ],
};

const reason = (value: unknown) => {
  const result = parseChart(
    typeof value === "string" ? value : JSON.stringify(value),
  );
  return result.ok ? "ok" : result.reason;
};

test("a valid line, bar and pie chart are accepted", () => {
  expect(reason(line)).toBe("ok");
  expect(reason({ ...line, type: "bar" })).toBe("ok");
  expect(
    reason({
      type: "pie",
      title: "Weights",
      series: ["Weight"],
      format: "percent",
      data: [
        { x: "A", Weight: 0.6 },
        { x: "B", Weight: 0.4 },
      ],
    }),
  ).toBe("ok");
});

test("defaults are filled in and an x given as a number becomes text", () => {
  const result = parseChart(JSON.stringify(line));
  expect(result.ok && result.spec.format).toBe("number");
  expect(result.ok && result.spec.currency).toBe("£");
  expect(result.ok && result.spec.data[1].x).toBe("5");
});

test("text that isn't JSON, or isn't an object, is refused", () => {
  expect(reason("{not json")).toContain("valid JSON");
  expect(reason("[1, 2]")).toContain("JSON object");
  expect(reason("42")).toContain("JSON object");
  expect(reason("null")).toContain("JSON object");
});

test("a wrong or missing type, title or format is refused", () => {
  expect(reason({ ...line, type: "scatter" })).toContain('"type"');
  expect(reason({ ...line, type: undefined })).toContain('"type"');
  expect(reason({ ...line, title: "" })).toContain('"title"');
  expect(reason({ ...line, title: 5 })).toContain('"title"');
  expect(reason({ ...line, format: "euros" })).toContain('"format"');
  expect(reason({ ...line, xLabel: 3 })).toContain('"xLabel"');
});

test("missing or bad series are refused", () => {
  expect(reason({ ...line, series: undefined })).toContain('"series"');
  expect(reason({ ...line, series: [] })).toContain('"series"');
  expect(reason({ ...line, series: [1] })).toContain('"series"');
  expect(reason({ ...line, series: ["x"] })).toContain('"series"');
  expect(reason({ ...line, series: ["A", "A"] })).toContain("different");
  const many = Array.from({ length: MAX_SERIES + 1 }, (_, i) => `S${i}`);
  expect(reason({ ...line, series: many })).toContain("at most");
});

test("missing data, or the wrong kind of row, is refused", () => {
  expect(reason({ ...line, data: undefined })).toContain('"data"');
  expect(reason({ ...line, data: [] })).toContain('"data"');
  expect(reason({ ...line, data: "rows" })).toContain('"data"');
  expect(reason({ ...line, data: [5] })).toContain("row 1 should be an object");
  expect(reason({ ...line, data: [{ NPV: 1 }] })).toContain('"x"');
  expect(reason({ ...line, data: [{ x: "a" }] })).toContain('number for "NPV"');
  expect(reason({ ...line, data: [{ x: "a", NPV: "5" }] })).toContain("number");
  expect(reason({ ...line, data: [{ x: "a", NPV: null }] })).toContain(
    "number",
  );
});

test("more rows than the limit are refused, and exactly the limit is fine", () => {
  const rows = (count: number) =>
    Array.from({ length: count }, (_, i) => ({ x: String(i), NPV: i }));
  expect(reason({ ...line, data: rows(MAX_ROWS) })).toBe("ok");
  expect(reason({ ...line, data: rows(MAX_ROWS + 1) })).toContain(
    `at most ${MAX_ROWS} rows`,
  );
});

test("a pie chart needs exactly one series and no negative values", () => {
  const pie = {
    type: "pie",
    title: "P",
    series: ["A"],
    data: [{ x: "a", A: 1 }],
  };
  expect(reason(pie)).toBe("ok");
  expect(reason({ ...pie, series: ["A", "B"] })).toContain("exactly one");
  expect(reason({ ...pie, data: [{ x: "a", A: -1 }] })).toContain("negative");
});

test("numbers are shown in the chart's format", () => {
  expect(formatValue(1234.5, "currency", "£")).toBe("£1,234.50");
  expect(formatValue(-5, "currency", "$")).toBe("-$5.00");
  expect(formatValue(0.05, "percent", "£")).toBe("5%");
  expect(formatValue(0.1234, "percent", "£")).toBe("12.34%");
  expect(formatValue(1234.5678, "number", "£")).toBe("1,234.5678");
});
