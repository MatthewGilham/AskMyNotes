import { expect, test, type Page } from "@playwright/test";

// The test server's fake model answers with pictures when the message contains
// "diagrams" (a flowchart, a sequence diagram and a timeline), "charts" (a line,
// a bar and a pie chart), "brokendiagram", "brokenchart", or "bluechart" (a
// chart inside a "From the web" block). "slow" streams the reply slowly.

async function startChat(page: Page, text: string) {
  await page.goto("/");
  await page.getByLabel("Message").fill(text);
  await page.getByLabel("Message").press("Enter");
  await expect(page).toHaveURL(/\/chat\//);
}

test("diagrams are drawn as SVG, and Show source and Copy work", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await startChat(page, "show me diagrams");

  const pictures = page.getByRole("img", { name: "Diagram" });
  await expect(pictures).toHaveCount(3);
  await expect(pictures.first().locator("svg")).toBeVisible();
  await expect(pictures.first()).toContainText("Is there an offer?");
  await expect(pictures.nth(1)).toContainText("Asks a question");
  await expect(pictures.nth(2)).toContainText("IFRS 10");

  // The source is hidden until asked for.
  await expect(page.locator("pre", { hasText: "flowchart TD" })).toHaveCount(0);
  await page.getByRole("button", { name: "Show source" }).first().click();
  await expect(page.locator("pre", { hasText: "flowchart TD" })).toBeVisible();
  await page.getByRole("button", { name: "Hide source" }).click();
  await expect(page.locator("pre", { hasText: "flowchart TD" })).toHaveCount(0);

  await page
    .getByRole("button", { name: "Copy diagram source" })
    .first()
    .click();
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  expect(copied.split("\r\n").join("\n")).toContain(
    "flowchart TD\n    A[Is there an offer?]",
  );
});

test("a diagram that can't be drawn shows its source and a note", async ({
  page,
}) => {
  await startChat(page, "show me a brokendiagram");

  await expect(page.getByText("Couldn't draw this diagram.")).toBeVisible();
  await expect(page.locator("pre", { hasText: "flowchart TD" })).toBeVisible();
  await expect(page.getByRole("img", { name: "Diagram" })).toHaveCount(0);
  // Nothing is left behind on the page by the failed attempt.
  await expect(page.locator("[id^=dmermaid], [id^=diagram-]")).toHaveCount(0);
});

test("line, bar and pie charts are drawn", async ({ page }) => {
  await startChat(page, "show me charts");

  const lineChart = page.getByLabel(
    "line chart: NPV against the discount rate",
  );
  const barChart = page.getByLabel("bar chart: Revenue and costs");
  const pieChart = page.getByLabel("pie chart: Portfolio weights");
  await expect(lineChart.locator("svg.recharts-surface")).toBeVisible();
  await expect(lineChart.locator(".recharts-line")).toHaveCount(1);
  await expect(barChart.locator(".recharts-bar-rectangle")).toHaveCount(4);
  await expect(pieChart.locator(".recharts-pie-sector")).toHaveCount(3);
  // Two bar series have a legend; the axes carry the format and labels.
  await expect(barChart.getByText("Revenue", { exact: true })).toBeVisible();
  await expect(lineChart.getByText("Discount rate")).toBeVisible();
  await expect(lineChart.getByText("£120.00").first()).toBeVisible();
});

test("a chart shows its values on hover", async ({ page }) => {
  await startChat(page, "show me charts");
  const bars = page.getByLabel("bar chart: Revenue and costs");
  await expect(bars.locator(".recharts-bar-rectangle").first()).toBeVisible();

  await bars.locator(".recharts-bar-rectangle").first().hover();

  const tooltip = bars.locator(".recharts-tooltip-wrapper");
  await expect(tooltip).toContainText("2024");
  await expect(tooltip).toContainText("Revenue");
  await expect(tooltip).toContainText("$100.00");
  await expect(tooltip).toContainText("$70.00");
});

test("a chart shows its values by keyboard", async ({ page }) => {
  await startChat(page, "show me charts");
  const lineChart = page.getByLabel(
    "line chart: NPV against the discount rate",
  );
  const surface = lineChart.locator("svg.recharts-surface");
  await expect(surface).toBeVisible();

  await page.keyboard.press("Tab"); // wander the page until the chart has focus
  for (
    let i = 0;
    i < 40 && !(await surface.evaluate((e) => e === document.activeElement));
    i++
  ) {
    await page.keyboard.press("Tab");
  }
  await expect(surface).toBeFocused();
  await page.keyboard.press("ArrowRight");

  await expect(lineChart.locator(".recharts-tooltip-wrapper")).toContainText(
    "£",
  );
});

test("each chart has a table of its data for screen readers", async ({
  page,
}) => {
  await startChat(page, "show me charts");

  const table = page.getByRole("table", { name: "Portfolio weights" });
  await expect(table.getByRole("row")).toHaveCount(4);
  await expect(table).toContainText("60%");
  await expect(table).toContainText("Bonds");
});

test("a chart that doesn't check out shows its JSON and a note", async ({
  page,
}) => {
  await startChat(page, "show me a brokenchart");

  await expect(page.getByText("Couldn't draw this chart:")).toBeVisible();
  await expect(
    page.getByText('"type" should be "line", "bar" or "pie"'),
  ).toBeVisible();
  await expect(page.locator("pre", { hasText: '"scatter"' })).toBeVisible();
});

test("a chart still streaming shows Drawing until it completes", async ({
  page,
}) => {
  await startChat(page, "slow show me charts");

  // The line chart's JSON is being written: nothing is drawn from half of it.
  await expect(page.getByText("Drawing…").first()).toBeVisible();
  await expect(page.locator("svg.recharts-surface")).toHaveCount(0);
  await expect(page.getByText("Couldn't draw")).toHaveCount(0);

  // Once its fence closes it is drawn, while the rest is still arriving.
  await expect(
    page.getByLabel("line chart: NPV against the discount rate"),
  ).toBeVisible({ timeout: 20_000 });
  await page.getByTitle("Stop").click();
});

test("pictures come back, redrawn from the saved text, when the chat reopens", async ({
  page,
}) => {
  await startChat(page, "reopen charts");
  await expect(page.getByLabel("pie chart: Portfolio weights")).toBeVisible();

  await page.reload();

  await expect(
    page.getByLabel("line chart: NPV against the discount rate"),
  ).toBeVisible();
  await expect(page.getByLabel("pie chart: Portfolio weights")).toBeVisible();
});

test("a chart inside a From the web block keeps the blue label", async ({
  page,
}) => {
  await startChat(page, "a bluechart please");

  const web = page.locator("aside", { hasText: "From the web" });
  await expect(web.getByText("From the web", { exact: true })).toBeVisible();
  await expect(
    web.getByLabel("line chart: NPV against the discount rate"),
  ).toBeVisible();
});

test("the page doesn't scroll sideways for a wide chart or diagram", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1024, height: 800 });
  await startChat(page, "show me diagrams");
  await expect(page.getByRole("img", { name: "Diagram" })).toHaveCount(3);

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test("text in a diagram or chart can't be quoted with Ask about this", async ({
  page,
}) => {
  await startChat(page, "show me charts");
  const chart = page.getByLabel("bar chart: Revenue and costs");
  await expect(chart).toBeVisible();

  await page.evaluate(() => {
    const figure = document.querySelector("figure")!;
    const range = document.createRange();
    range.selectNodeContents(figure);
    const selection = window.getSelection()!;
    selection.removeAllRanges();
    selection.addRange(range);
  });

  await expect(
    page.getByRole("button", { name: "Ask about this", exact: true }),
  ).toHaveCount(0);
});
