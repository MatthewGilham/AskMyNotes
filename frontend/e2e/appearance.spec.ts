import { expect, test, type Page } from "@playwright/test";

// Phase 34: the Appearance menu. Three colour themes and two effects levels,
// chosen from the sidebar or its rail and remembered by the browser, along
// with whether the sidebar is open in a wide window.

const STORAGE_KEY = "askmynotes-appearance";
const AURORA_ACCENT = "rgb(167, 139, 250)";

const html = (page: Page) => page.locator("html");
const messageBox = (page: Page) => page.getByLabel("Message");
const appearance = (page: Page) =>
  page.getByRole("button", { name: "Appearance" });
const choice = (page: Page, name: string) =>
  page.getByRole("menuitemradio", { name });

/** The accent token as the browser paints it. */
const accent = (page: Page) =>
  page.evaluate(() => {
    const probe = document.createElement("div");
    probe.style.background = "var(--color-accent)";
    document.body.append(probe);
    const colour = getComputedStyle(probe).backgroundColor;
    probe.remove();
    return colour;
  });

/** Collects anything the page reports as an error. */
function watchErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  return errors;
}

const backdropAnimations = (page: Page) =>
  page.evaluate(
    () =>
      document
        .querySelector("[data-backdrop]")!
        .getAnimations({ subtree: true }).length,
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

test("choosing Aurora changes the theme, and a reload opens in Aurora from the first moment", async ({
  page,
}) => {
  // Notes the theme when the page's content has loaded, before the app runs.
  await page.addInitScript(() => {
    document.addEventListener("readystatechange", () => {
      if (document.readyState === "interactive")
        (window as unknown as { themeAtLoad?: string }).themeAtLoad =
          document.documentElement.dataset.theme;
    });
  });
  await page.goto("/");
  await expect(html(page)).not.toHaveAttribute("data-theme");

  await appearance(page).click();
  await choice(page, "Aurora").click();
  await expect(html(page)).toHaveAttribute("data-theme", "aurora");
  expect(await accent(page)).toBe(AURORA_ACCENT);

  await page.reload();
  await expect(html(page)).toHaveAttribute("data-theme", "aurora");
  expect(
    await page.evaluate(
      () => (window as unknown as { themeAtLoad?: string }).themeAtLoad,
    ),
  ).toBe("aurora");
  await appearance(page).click();
  await expect(choice(page, "Aurora")).toBeChecked();
});

test("the menu works by keyboard and marks the current choices", async ({
  page,
}) => {
  await page.goto("/");
  await appearance(page).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("menu")).toBeVisible();
  await expect(choice(page, "Volt")).toBeChecked();
  await expect(choice(page, "Full")).toBeChecked();
  await expect(choice(page, "Aurora")).not.toBeChecked();

  await expect(choice(page, "Volt")).toBeFocused();
  await page.keyboard.press("ArrowDown");
  await expect(choice(page, "Aurora")).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(choice(page, "Aurora")).toBeChecked();
  await expect(choice(page, "Volt")).not.toBeChecked();
  await expect(html(page)).toHaveAttribute("data-theme", "aurora");

  await page.keyboard.press("Escape");
  await expect(page.getByRole("menu")).toHaveCount(0);
  await expect(appearance(page)).toBeFocused();
});

test("Calm stops the backdrop, removes the glass blur and the moving message box", async ({
  page,
}) => {
  await countViewTransitions(page);
  await page.goto("/");
  const sidebar = page.getByRole("navigation", { name: "Chats" });
  const box = messageBox(page).locator("..");
  // The page has loaded, but React may not have drawn the app yet.
  await expect(page.locator("[data-backdrop]")).toBeAttached();
  expect(await backdropAnimations(page)).toBe(3);
  await expect(sidebar).toHaveCSS("backdrop-filter", /blur/);
  await expect(box).toHaveCSS("backdrop-filter", /blur/);

  await appearance(page).click();
  await choice(page, "Calm").click();
  await page.keyboard.press("Escape");
  await expect(html(page)).toHaveAttribute("data-effects", "calm");
  expect(await backdropAnimations(page)).toBe(0);
  await expect(sidebar).toHaveCSS("backdrop-filter", "none");
  await expect(box).toHaveCSS("backdrop-filter", "none");

  await messageBox(page).fill("hello");
  await messageBox(page).press("Enter");
  await expect(page.getByTitle("Regenerate")).toBeVisible();
  expect(await viewTransitions(page)).toBe(0);

  // Calm is remembered too, and Full brings the motion back.
  await page.reload();
  await expect(html(page)).toHaveAttribute("data-effects", "calm");
  await appearance(page).click();
  await choice(page, "Full").click();
  await expect(html(page)).not.toHaveAttribute("data-effects");
  expect(await backdropAnimations(page)).toBe(3);
});

test("with reduced motion, Full effects still don't move", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await countViewTransitions(page);
  await page.goto("/");
  await appearance(page).click();
  await expect(choice(page, "Full")).toBeChecked();
  await page.keyboard.press("Escape");
  expect(await backdropAnimations(page)).toBe(0);

  await messageBox(page).fill("slow reply please");
  await messageBox(page).press("Enter");
  await expect(page.locator("[data-thinking]")).toHaveCount(1);
  const edgeAnimations = await messageBox(page)
    .locator("..")
    .evaluate(
      (e) =>
        e
          .getAnimations({ subtree: true })
          .filter((animation) => animation instanceof CSSAnimation).length,
    );
  expect(edgeAnimations).toBe(0);
  // The caret is there (8px wide) but doesn't blink.
  await expect
    .poll(() =>
      page.evaluate(() => {
        const paragraphs = document.querySelectorAll("[data-streaming] p");
        const last = paragraphs[paragraphs.length - 1];
        if (!last) return "no paragraph";
        const caret = getComputedStyle(last, "::after");
        return `${caret.width} ${caret.animationName}`;
      }),
    )
    .toBe("8px none");
  await page.getByTitle("Stop").click();
  expect(await viewTransitions(page)).toBe(0);
});

for (const [what, saved] of [
  ["text that isn't JSON", "{not json"],
  [
    "choices that don't exist",
    '{"theme":"neon","effects":7,"sidebarOpen":"no"}',
  ],
  ["a value that isn't an object", "5"],
]) {
  test(`a damaged saved value (${what}) leaves the app in Volt, with no error`, async ({
    page,
  }) => {
    const errors = watchErrors(page);
    await page.addInitScript(
      ([key, value]) => localStorage.setItem(key, value),
      [STORAGE_KEY, saved],
    );
    await page.goto("/");
    await expect(messageBox(page)).toBeEnabled();
    await expect(html(page)).not.toHaveAttribute("data-theme");
    await expect(html(page)).not.toHaveAttribute("data-effects");
    await expect(page.getByTitle("Close sidebar")).toBeVisible();
    expect(errors).toEqual([]);
  });
}

test("storage that refuses to be read leaves the app in Volt, with no error, and themes still change", async ({
  page,
}) => {
  const errors = watchErrors(page);
  await page.addInitScript(() => {
    Object.defineProperty(window, "localStorage", {
      get() {
        throw new DOMException("Storage is switched off", "SecurityError");
      },
    });
  });
  await page.goto("/");
  await expect(messageBox(page)).toBeEnabled();
  await expect(html(page)).not.toHaveAttribute("data-theme");

  await appearance(page).click();
  await choice(page, "Ice").click();
  await expect(html(page)).toHaveAttribute("data-theme", "ice");
  expect(errors).toEqual([]);
});

test("at 800px the menu opens from the rail and from the floating sidebar", async ({
  page,
}) => {
  await page.setViewportSize({ width: 800, height: 800 });
  await page.goto("/");
  await appearance(page).click();
  await expect(choice(page, "Volt")).toBeChecked();
  const menu = await page.getByRole("menu").boundingBox();
  expect(menu!.x).toBeGreaterThanOrEqual(0);
  expect(menu!.x + menu!.width).toBeLessThanOrEqual(800);
  expect(menu!.y + menu!.height).toBeLessThanOrEqual(800);
  await page.keyboard.press("Escape");

  await page.getByTitle("Open sidebar").click();
  const floating = page
    .getByRole("navigation", { name: "Chats" })
    .filter({ has: page.getByTitle("Close sidebar") });
  await floating.getByRole("button", { name: "Appearance" }).click();
  await choice(page, "Ice").click();
  await expect(html(page)).toHaveAttribute("data-theme", "ice");
  // Escape closes the menu, not the sidebar it was opened from.
  await page.keyboard.press("Escape");
  await expect(page.getByRole("menu")).toHaveCount(0);
  await expect(floating).toBeVisible();
});

// 34E: remembering the sidebar.

test("at 1280px the sidebar stays collapsed, or open, across a reload", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/");
  await page.getByTitle("Close sidebar").click();
  await expect(page.getByTitle("Open sidebar")).toBeVisible();

  await page.reload();
  await expect(page.getByTitle("Open sidebar")).toBeVisible();
  await expect(page.getByTitle("Close sidebar")).toHaveCount(0);

  await page.getByTitle("Open sidebar").click();
  await page.reload();
  await expect(page.getByTitle("Close sidebar")).toBeVisible();
});
