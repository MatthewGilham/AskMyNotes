import { expect, test, type Page } from "@playwright/test";

// Phase 35: the whole-app review. Every core state, in each theme, at five
// widths: the page never scrolls sideways, and every button has an accessible
// name. With REVIEW_SCREENSHOTS=1 it also saves the screenshots the review
// looks at (all of them in Volt; Aurora and Ice at 600px and 1280px) under
// ignored data/phase35-check/screens/.

const WIDTHS = [600, 800, 1024, 1280, 1600];
const THEMES = ["volt", "aurora", "ice"] as const;
const SCREENSHOTS = process.env.REVIEW_SCREENSHOTS === "1";

const REVIEW_CHAT = {
  id: "review",
  title:
    "A made-up review chat with a long title that has to be shortened in a narrow window",
  pinned: false,
  lastUsedAt: new Date().toISOString(),
  messages: [
    ...Array.from({ length: 36 }, (_, i) => ({
      id: i + 1,
      role: i % 2 === 0 ? "user" : "assistant",
      content:
        i % 2 === 0
          ? `Made-up question ${i + 1}`
          : `Made-up explanation ${i + 1}. ` + "Study material. ".repeat(40),
      images: [],
      status: "complete",
      sources: null,
      error: null,
    })),
    {
      id: 37,
      role: "user",
      content: "Explain depreciation from my notes",
      images: [],
      status: "complete",
      sources: null,
      error: null,
    },
    {
      id: 38,
      role: "assistant",
      content:
        "Depreciation spreads the cost of an asset over its useful life.\n\n" +
        "| Year | Charge |\n|---|---|\n| 1 | 200 |\n| 2 | 200 |",
      images: [],
      status: "complete",
      error: null,
      sources: [
        {
          fileName:
            "Week 3 - Property, plant and equipment, impairment and the revaluation model.pptx",
          module: "AFA",
          location: "slide",
          number: 8,
        },
        {
          fileName: "Lecture 2.pdf",
          module: "FR",
          location: "page",
          number: 4,
        },
      ],
      webSearches: ["bank rate today"],
      webSources: [
        {
          title: "Bank Rate | Example Bank",
          site: "example-bank.test",
          url: "https://www.example-bank.test/rate",
          cited: true,
        },
        {
          title: "https://data.example.test/" + "series/rate/".repeat(12),
          site: "data.example.test",
          url: "https://data.example.test/" + "series/rate/".repeat(12),
          cited: false,
        },
      ],
      toolRuns: [
        {
          tool: "calculate",
          input: "1000 * (1 + 0.05)^2",
          result: "1102.5",
          ok: true,
          inputLatex: "1000 \\cdot (1 + 0.05)^{2}",
          resultLatex: "1102.5",
        },
      ],
    },
    {
      id: 39,
      role: "user",
      content: "And the reducing balance method?",
      images: [],
      status: "complete",
      sources: null,
      error: null,
    },
    {
      id: 40,
      role: "assistant",
      content: "",
      images: [],
      status: "error",
      sources: null,
      error: "Couldn't reach OpenAI. Check your internet connection.",
    },
  ],
};

const messageBox = (page: Page) => page.getByLabel("Message");

/** The checks for one state, and its screenshot when the review asks. */
async function review(page: Page, theme: string, width: number, state: string) {
  const where = `${theme} ${width}px ${state}`;
  const sideways = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(sideways, `${where}: sideways scroll`).toBeLessThanOrEqual(0);
  // One query for buttons whose accessible name is empty, so a button that
  // appears or goes meanwhile (Jump to latest, say) can't break the check.
  // While a menu or dialog is open, the page behind it is hidden and left out.
  // (Playwright's aria snapshot was tried first, but it drops very long names,
  // such as a chat titled with a single 5,000-character word.)
  if (state === "new-chat")
    expect(
      await page.getByRole("button").count(),
      `${where}: buttons found`,
    ).toBeGreaterThan(3);
  expect(
    await page.getByRole("button", { name: /^\s*$/ }).count(),
    `${where}: buttons with no name`,
  ).toBe(0);
  if (SCREENSHOTS && (theme === "volt" || width === 600 || width === 1280)) {
    // Lets menus and dialogs finish fading in, and the sidebar sliding.
    await page.waitForTimeout(400);
    await page.screenshot({
      path: `../data/phase35-check/screens/${theme}-${width}-${state}.png`,
    });
  }
}

test("the page has a tab icon, and it is an SVG", async ({ page, request }) => {
  await page.goto("/");
  const href = await page.locator('link[rel="icon"]').getAttribute("href");
  expect(href).toBe("/favicon.svg");
  const response = await request.get(href!);
  expect(response.ok()).toBe(true);
  expect(response.headers()["content-type"]).toContain("image/svg+xml");
  expect(await response.text()).toContain("<svg");
});

for (const theme of THEMES) {
  test(`${theme}: every core state fits each width and names every button`, async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await page.route("**/api/chats/review", (route) =>
      route.fulfill({ json: REVIEW_CHAT }),
    );
    await page.addInitScript(
      (name) =>
        localStorage.setItem(
          "askmynotes-appearance",
          JSON.stringify({ theme: name }),
        ),
      theme,
    );
    // One real chat, so the sidebar has a row with its menu.
    await page.goto("/");
    await messageBox(page).fill("hello");
    await messageBox(page).press("Enter");
    await expect(page.getByTitle("Regenerate")).toBeVisible();

    for (const width of WIDTHS) {
      await page.setViewportSize({ width, height: 860 });
      const check = (state: string) => review(page, theme, width, state);

      await page.goto("/");
      await expect(messageBox(page)).toBeEnabled();
      await check("new-chat");

      await messageBox(page).fill("slow reply please");
      await messageBox(page).press("Enter");
      await expect(page.getByText("You said: slow reply")).toBeVisible();
      await check("mid-reply");
      await page.getByTitle("Stop").click();
      await expect(page.getByText("Stopped", { exact: true })).toBeVisible();

      await page.goto("/chat/review");
      await expect(page.locator("#message-40")).toBeInViewport();
      await expect(page.getByRole("alert")).toBeVisible();
      await check("end-with-error");
      await page.locator("#message-1").scrollIntoViewIfNeeded();
      await check("top");
      await page.locator("#message-20").scrollIntoViewIfNeeded();
      await check("middle");

      const answer = page.locator("#message-38");
      await answer.scrollIntoViewIfNeeded();
      await answer.getByText(/^Sources \(/).click();
      await answer.getByText(/^Found online/).click();
      await answer.getByText(/^Working/).click();
      await expect(answer.getByRole("list", { name: "Sources" })).toBeVisible();
      await answer.getByText(/^Working/).scrollIntoViewIfNeeded();
      await check("panels-open");

      await page.getByRole("button", { name: "Edit latest question" }).click();
      await expect(page.getByRole("button", { name: "Cancel" })).toBeVisible();
      await check("editor");
      await page.getByRole("button", { name: "Cancel" }).click();

      await page.keyboard.press("Control+k");
      await expect(page.getByRole("dialog")).toBeVisible();
      await check("search");
      await page.keyboard.press("Escape");
      await expect(page.getByRole("dialog")).toHaveCount(0);

      if (width < 900) {
        await page.getByTitle("Open sidebar").click();
        await expect(page.getByTitle("Close sidebar")).toBeVisible();
        await check("floating-sidebar");
      }
      await page.getByTitle("Chat options").first().click();
      await expect(page.getByRole("menu")).toBeVisible();
      await check("chat-menu");
      await page.keyboard.press("Escape");
    }
  });
}
