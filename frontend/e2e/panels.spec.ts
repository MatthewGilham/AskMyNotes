import { expect, test, type Locator, type Page } from "@playwright/test";

// Phase 33: what sits under an answer, and the pictures inside one. Sources
// open into a row of slide-shaped cards; Found online and Working are glass
// panels; diagrams and charts are drawn in the colours of the theme in use.
// Made-up chats are served by routes, as in conversation.spec.ts.

// 80 characters.
const LONG_NAME =
  "A very long lecture file name that goes on and on, well past eighty, okay!!.pptx";
const LONG_ADDRESS =
  "https://data.example.test/" + "series/rate/".repeat(15) + "end";
const SOURCES = Array.from({ length: 12 }, (_, i) => ({
  fileName: i === 1 ? LONG_NAME : `Lecture ${i + 1}.pptx`,
  module: i % 2 ? "IPA" : "AFA",
  location: i % 3 ? "slide" : "page",
  number: i + 3,
}));
const LINE_CHART = JSON.stringify({
  type: "line",
  title: "NPV against the rate",
  series: ["NPV"],
  data: [
    { x: "0%", NPV: 120 },
    { x: "5%", NPV: 80 },
    { x: "10%", NPV: 41 },
  ],
});
const PICTURES = [
  "A flowchart:",
  "",
  "```mermaid",
  "flowchart TD",
  "    A[Offer] --> B[Acceptance]",
  "```",
  "",
  "A chart:",
  "",
  "```chart",
  LINE_CHART,
  "```",
].join("\n");

async function servePanels(page: Page) {
  await page.route("**/api/chats/panels", (route) =>
    route.fulfill({
      json: {
        id: "panels",
        title: "Made-up panels",
        pinned: false,
        lastUsedAt: new Date().toISOString(),
        messages: [
          {
            id: 1,
            role: "user",
            content: "Show me every panel",
            images: [],
            status: "complete",
            sources: null,
            error: null,
          },
          {
            id: 2,
            role: "assistant",
            content: "Here is everything.\n\n" + PICTURES,
            images: [],
            status: "complete",
            error: null,
            sources: SOURCES,
            webSearches: ["bank rate today"],
            webSources: [
              {
                title: "Bank Rate | Example Bank",
                site: "example-bank.test",
                url: "https://www.example-bank.test/rate",
                cited: true,
              },
              {
                title: LONG_ADDRESS,
                site: "data.example.test",
                url: LONG_ADDRESS,
                cited: false,
              },
            ],
            toolRuns: [
              {
                tool: "calculate",
                input: "1000 * 1.05",
                result: "1050",
                ok: true,
                inputLatex: "1000 \\cdot 1.05",
                resultLatex: "1050",
              },
            ],
          },
        ],
      },
    }),
  );
}

/** Volt is the default theme, so it has no attribute. */
async function setTheme(page: Page, theme: string) {
  await page.evaluate((name) => {
    if (name === "volt") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", name);
  }, theme);
}

const sourcesSummary = (page: Page) => page.getByText("Sources (12)");
const slideRow = (page: Page) => page.getByRole("list", { name: "Sources" });
const sidewaysScroll = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
const box = async (element: Locator) => (await element.boundingBox())!;

// 33A: Sources as slides.

test("Sources stay closed until clicked, and open by keyboard", async ({
  page,
}) => {
  await servePanels(page);
  await page.goto("/chat/panels");
  await expect(sourcesSummary(page)).toBeVisible();
  await expect(slideRow(page)).toBeHidden();
  await sourcesSummary(page).focus();
  await page.keyboard.press("Enter");
  await expect(slideRow(page)).toBeVisible();
});

test("each source is a list item reading file, module, then slide", async ({
  page,
}) => {
  await servePanels(page);
  await page.goto("/chat/panels");
  await sourcesSummary(page).click();
  const cards = slideRow(page).getByRole("listitem");
  await expect(cards).toHaveCount(12);
  expect((await cards.nth(2).innerText()).split("\n")).toEqual([
    "Lecture 3.pptx",
    "AFA",
    "Slide 5",
  ]);
  expect((await cards.nth(0).innerText()).split("\n")).toEqual([
    "Lecture 1.pptx",
    "AFA",
    "Page 3",
  ]);
  // The module is drawn first, as a tag above the file name.
  const card = cards.nth(2);
  const [tag, file] = [
    await box(card.getByText("AFA", { exact: true })),
    await box(card.getByText("Lecture 3.pptx")),
  ];
  expect(tag.y).toBeLessThan(file.y);
});

test("at 600px twelve slides scroll inside their row, also by arrow keys", async ({
  page,
}) => {
  await page.setViewportSize({ width: 600, height: 800 });
  await servePanels(page);
  await page.goto("/chat/panels");
  await sourcesSummary(page).click();
  const row = slideRow(page);
  expect(await row.evaluate((e) => e.scrollWidth > e.clientWidth)).toBe(true);
  await row.focus();
  for (let i = 0; i < 5; i++) await page.keyboard.press("ArrowRight");
  await expect.poll(() => row.evaluate((e) => e.scrollLeft)).toBeGreaterThan(0);
  expect(await sidewaysScroll(page)).toBe(0);
});

test("a long file name leaves its card the same size as a short one", async ({
  page,
}) => {
  await servePanels(page);
  await page.goto("/chat/panels");
  await sourcesSummary(page).click();
  const cards = slideRow(page).getByRole("listitem");
  const [short, long] = [await box(cards.nth(0)), await box(cards.nth(1))];
  expect(long.height).toBe(short.height);
  expect(long.width).toBe(short.width);
});

// 33B: Found online, Working and files.

test("at 600px a long address in Searched, not cited wraps inside the panel", async ({
  page,
}) => {
  await page.setViewportSize({ width: 600, height: 800 });
  await servePanels(page);
  await page.goto("/chat/panels");
  await page.getByText(/^Found online/).click();
  const link = page.getByRole("link", { name: LONG_ADDRESS });
  await expect(link).toBeVisible();
  const panel = page.getByRole("region", { name: "Searched, not cited" });
  const [a, b] = [await box(link), await box(panel)];
  expect(a.x + a.width).toBeLessThanOrEqual(b.x + b.width + 0.5);
  expect(a.height).toBeGreaterThan(30); // more than one line
  expect(await sidewaysScroll(page)).toBe(0);
});

test("Found online and Working open into glass panels", async ({ page }) => {
  await servePanels(page);
  await page.goto("/chat/panels");
  for (const heading of [/^Found online/, /^Working/]) {
    const summary = page.getByText(heading);
    await expect(summary).toHaveCSS("border-top-left-radius", "999px");
    await summary.click();
    const panel = summary.locator("xpath=following-sibling::*[1]");
    await expect(panel).toBeVisible();
    await expect(panel).toHaveCSS("border-top-left-radius", "16px");
    expect(
      await panel.evaluate((e) => getComputedStyle(e).backgroundColor),
    ).not.toBe("rgba(0, 0, 0, 0)");
  }
});

// 33C: diagrams and charts follow the theme.

const THEMES = {
  volt: { accent: "rgb(204, 255, 51)", chart1: "rgb(204, 255, 51)" },
  aurora: { accent: "rgb(167, 139, 250)", chart1: "rgb(167, 139, 250)" },
  ice: { accent: "rgb(242, 246, 255)", chart1: "rgb(242, 246, 255)" },
};

test("changing the theme redraws a diagram and recolours a chart", async ({
  page,
}) => {
  await servePanels(page);
  await page.goto("/chat/panels");
  const node = page
    .getByRole("img", { name: "Diagram" })
    .locator(".node rect, .node polygon")
    .first();
  const line = page.locator(".recharts-line-curve").first();
  await expect(node).toBeVisible();
  await expect(line).toBeVisible();
  const stroke = (element: Locator) =>
    element.evaluate((e) => getComputedStyle(e).stroke);

  for (const [theme, { accent, chart1 }] of Object.entries({
    aurora: THEMES.aurora,
    ice: THEMES.ice,
    volt: THEMES.volt,
  })) {
    await setTheme(page, theme);
    await expect.poll(() => stroke(node), theme).toBe(accent);
    await expect.poll(() => stroke(line), theme).toBe(chart1);
  }
});
