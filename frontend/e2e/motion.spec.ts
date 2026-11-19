import { expect, test, type Locator, type Page } from "@playwright/test";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

// Phase 34: motion. While a reply is in progress the app "charges up" (its
// root carries data-thinking, and a band of light travels round the message
// box); the message box glides down on the first message of a new chat; and a
// caret blinks at the end of a streaming reply.

const messageBox = (page: Page) => page.getByLabel("Message");
const thinking = (page: Page) => page.locator("[data-thinking]");

async function ask(page: Page, text: string) {
  await messageBox(page).fill(text);
  await messageBox(page).press("Enter");
}

/** How many CSS animations (not transitions) run on an element or inside it. */
const cssAnimations = (element: Locator) =>
  element.evaluate(
    (e) =>
      e
        .getAnimations({ subtree: true })
        .filter((animation) => animation instanceof CSSAnimation).length,
  );

/** Counts the view transitions the page starts, from before it loads. */
async function countViewTransitions(page: Page) {
  await page.addInitScript(() => {
    const counter = window as unknown as { viewTransitions: number };
    counter.viewTransitions = 0;
    const start = document.startViewTransition.bind(document);
    document.startViewTransition = (update) => {
      counter.viewTransitions += 1;
      return start(update);
    };
  });
}

const viewTransitions = (page: Page) =>
  page.evaluate(
    () => (window as unknown as { viewTransitions: number }).viewTransitions,
  );

// 34A: the charge-up.

test("the app is charged from the start of a reply, through a search, to its end", async ({
  page,
}) => {
  await page.goto("/");
  await expect(messageBox(page)).toBeEnabled();
  await expect(thinking(page)).toHaveCount(0);

  await ask(page, "slowsearch the web");
  await expect(thinking(page)).toHaveCount(1);
  await expect(
    page.getByRole("status").filter({ hasText: "Searching the web…" }),
  ).toBeVisible();
  await expect(thinking(page)).toHaveCount(1);

  await expect(page.getByTitle("Regenerate")).toBeVisible({ timeout: 15_000 });
  await expect(thinking(page)).toHaveCount(0, { timeout: 500 });
});

test("the charge ends after Stop and after a failed reply", async ({
  page,
}) => {
  await page.goto("/");
  await ask(page, "slow reply please");
  await expect(page.getByText("You said: slow reply")).toBeVisible();
  await expect(thinking(page)).toHaveCount(1);
  await page.getByTitle("Stop").click();
  await expect(page.getByText("Stopped", { exact: true })).toBeVisible();
  await expect(thinking(page)).toHaveCount(0);

  await ask(page, "please fail now");
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(thinking(page)).toHaveCount(0);
});

test("a notes update alone doesn't charge the app", async ({ page }) => {
  await page.route("**/api/notes/status", (route) =>
    route.fulfill({
      json: {
        updating: true,
        new: 3,
        changed: 1,
        deleted: 0,
        done: 1,
        total: 4,
        fileCount: 0,
        unreadable: [],
        inUse: [],
        error: null,
      },
    }),
  );
  await page.goto("/");
  await expect(messageBox(page)).toBeDisabled();
  await expect(thinking(page)).toHaveCount(0);
});

test("the message box's edge is animated only while a reply is in progress", async ({
  page,
}) => {
  await page.goto("/");
  const box = messageBox(page).locator("..");
  await expect(messageBox(page)).toBeEnabled();
  expect(await cssAnimations(box)).toBe(0);

  await ask(page, "slow reply please");
  await expect(thinking(page)).toHaveCount(1);
  await expect
    .poll(() => cssAnimations(messageBox(page).locator("..")))
    .toBeGreaterThan(0);

  await page.getByTitle("Stop").click();
  await expect(thinking(page)).toHaveCount(0);
  expect(await cssAnimations(messageBox(page).locator(".."))).toBe(0);
});

// 34B: the moving message box.

test("the first send starts exactly one view transition, and the box can be typed in at once", async ({
  page,
}) => {
  await countViewTransitions(page);
  await page.goto("/");
  await ask(page, "hello");
  await expect(page).toHaveURL(/\/chat\//);
  await page.waitForTimeout(100);
  await messageBox(page).fill("typed during the glide");
  await expect(messageBox(page)).toHaveValue("typed during the glide");
  await expect(page.getByTitle("Regenerate")).toBeVisible();
  expect(await viewTransitions(page)).toBe(1);

  // A later message in the same chat starts none.
  await messageBox(page).press("Enter");
  await expect(page.getByText("You said: typed during")).toBeVisible();
  await expect(page.getByTitle("Regenerate")).toBeVisible();
  expect(await viewTransitions(page)).toBe(1);
});

test("with reduced motion the first send starts no view transition", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await countViewTransitions(page);
  await page.goto("/");
  await ask(page, "hello");
  await expect(page.getByTitle("Regenerate")).toBeVisible();
  expect(await viewTransitions(page)).toBe(0);
});

test("sending in a chat that was reopened starts no view transition", async ({
  page,
}) => {
  await countViewTransitions(page);
  await page.goto("/");
  await ask(page, "hello");
  await expect(page.getByTitle("Regenerate")).toBeVisible();
  await page.reload();
  await expect(page.getByText("You said: hello")).toBeVisible();

  await ask(page, "hello again");
  await expect(page.getByText("You said: hello again")).toBeVisible();
  await expect(page.getByTitle("Regenerate")).toBeVisible();
  expect(await viewTransitions(page)).toBe(0);
});

// 34C: small motions.

/** The caret is drawn after the last paragraph of the streaming reply. */
const caretWidth = (page: Page) =>
  page.evaluate(() => {
    const paragraphs = document.querySelectorAll("[data-streaming] p");
    const last = paragraphs[paragraphs.length - 1];
    return last ? getComputedStyle(last, "::after").width : "no paragraph";
  });

test("a caret shows while a reply streams, and goes when it is stopped or finishes", async ({
  page,
}) => {
  await page.goto("/");
  await ask(page, "slow reply please");
  await expect(page.getByText("You said: slow reply")).toBeVisible();
  await expect.poll(() => caretWidth(page)).toBe("8px");

  await page.getByTitle("Stop").click();
  await expect(page.getByText("Stopped", { exact: true })).toBeVisible();
  await expect(page.locator("[data-streaming]")).toHaveCount(0);

  await ask(page, "a quick one");
  await expect(page.getByTitle("Regenerate")).toBeVisible();
  await expect(page.locator("[data-streaming]")).toHaveCount(0);
});

test("with reduced motion nothing is animated after loading, opening a menu or opening Sources", async ({
  page,
}) => {
  const running = () => page.evaluate(() => document.getAnimations().length);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.getByText("Notes up to date · 1 file")).toBeVisible();
  await expect.poll(running).toBe(0);

  await ask(page, "What do my notes say about depreciation?");
  await expect(page.getByTitle("Regenerate")).toBeVisible();

  await page.getByRole("button", { name: "Appearance" }).click();
  await expect(page.getByRole("menu")).toBeVisible();
  await expect.poll(running).toBe(0);
  await page.keyboard.press("Escape");

  await page.getByText("Sources (1)").click();
  await expect(page.getByRole("list", { name: "Sources" })).toBeVisible();
  await expect.poll(running).toBe(0);
});

test("opening Sources deals the slide cards in", async ({ page }) => {
  await page.goto("/");
  await ask(page, "What do my notes say about depreciation?");
  await expect(page.getByTitle("Regenerate")).toBeVisible();
  await page.getByText("Sources (1)").click();
  const card = page
    .getByRole("list", { name: "Sources" })
    .getByRole("listitem")
    .first();
  expect(await cssAnimations(card)).toBe(1);
});

/** Every .css file under a folder. */
function stylesheets(folder: string): string[] {
  return readdirSync(folder, { withFileTypes: true }).flatMap((entry) => {
    const path = join(folder, entry.name);
    if (entry.isDirectory()) return stylesheets(path);
    return entry.name.endsWith(".css") ? [path] : [];
  });
}

test("keyframes only ever animate transform, opacity and background-position", () => {
  const allowed = new Set(["transform", "opacity", "background-position"]);
  const files = stylesheets("src");
  let keyframeBlocks = 0;
  for (const file of files) {
    const css = readFileSync(file, "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
    // One @keyframes block: its name, then steps that each hold declarations.
    for (const [, name, steps] of css.matchAll(
      /@keyframes\s+([\w-]+)\s*\{((?:[^{}]*\{[^{}]*\})*)\s*\}/g,
    )) {
      keyframeBlocks += 1;
      for (const [, property] of steps.matchAll(/([\w-]+)\s*:/g))
        expect(allowed, `${file}: @keyframes ${name}`).toContain(property);
    }
  }
  expect(keyframeBlocks).toBeGreaterThan(10);
});
