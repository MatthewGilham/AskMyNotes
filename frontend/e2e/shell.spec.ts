import { expect, test, type Locator, type Page } from "@playwright/test";

// Phase 30: the shell of the redesign. The sidebar and its rail are a pane of
// glass floating 12px inside the window, the chat header is a centred glass
// pill the conversation scrolls under, and menus and dialogs are glass too.

const GUTTER = 12;
// Menus and dialogs have a stronger edge than the sidebar: white at 16%.
const STRONG_EDGE = "rgba(255, 255, 255, 0.16)";
const WIDTHS = [600, 800, 1024, 1280, 1600];
const LONG_TITLE = "Long title ".repeat(11).trim(); // 120 characters
const ACCENTS = {
  volt: { accent: "rgb(204, 255, 51)", onAccent: "rgb(18, 25, 0)" },
  aurora: { accent: "rgb(167, 139, 250)", onAccent: "rgb(10, 7, 20)" },
  ice: { accent: "rgb(242, 246, 255)", onAccent: "rgb(10, 12, 16)" },
};

const sidebar = (page: Page) =>
  page
    .getByRole("navigation", { name: "Chats" })
    .filter({ has: page.getByTitle("Close sidebar") });
const pill = (page: Page) => page.locator("main header");

/** Volt is the default theme, so it has no attribute. */
async function useTheme(page: Page, theme: string) {
  await page.evaluate((name) => {
    if (name === "volt") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", name);
  }, theme);
}

async function send(page: Page, text: string) {
  const messages = page.locator('[id^="message-"]');
  const before = await messages.count();
  await page.getByLabel("Message").fill(text);
  await page.getByLabel("Message").press("Enter");
  await expect(messages).toHaveCount(before + 2);
  await expect(page.getByTitle("Regenerate")).toHaveCount(1);
}

/** Starts a chat, gives it a title, and leaves it open. */
async function openChat(page: Page, title: string, questions = ["hello"]) {
  await page.goto("/");
  for (const question of questions) await send(page, question);
  const chatId = page.url().split("/chat/")[1];
  await page.request.patch(`/api/chats/${chatId}`, { data: { title } });
  await page.reload();
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  return chatId;
}

/** In a narrow window the sidebar is the rail until it is opened. */
async function showSidebar(page: Page) {
  if (page.viewportSize()!.width < 900)
    await page.getByTitle("Open sidebar").click();
  await expect(sidebar(page)).toBeVisible();
}

async function expectInsideWindow(page: Page, element: Locator) {
  const box = (await element.boundingBox())!;
  const { width, height } = page.viewportSize()!;
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(width);
  expect(box.y + box.height).toBeLessThanOrEqual(height);
}

/** Holds the notes status at whatever the test wants to see. */
async function fakeNotesStatus(page: Page, status: object) {
  await page.route("**/api/notes/status", (route) =>
    route.fulfill({
      json: {
        updating: false,
        new: 0,
        changed: 0,
        deleted: 0,
        done: 0,
        total: 0,
        fileCount: 1,
        unreadable: [],
        inUse: [],
        error: null,
        ...status,
      },
    }),
  );
}

// 30A: the sidebar and its rail.

test("the sidebar and the rail float 12px inside the window; main reaches the right edge", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/");
  // The same checks for the open sidebar, then for the rail it collapses to.
  const pane = page.getByRole("navigation", { name: "Chats" });
  for (const width of [284, 60]) {
    const box = (await pane.boundingBox())!;
    expect(box.width).toBe(width);
    expect(box.x).toBe(GUTTER);
    expect(box.y).toBe(GUTTER);
    expect(box.y + box.height).toBe(800 - GUTTER);
    await expect(pane).toHaveCSS("backdrop-filter", /blur/);
    const main = (await page.locator("main").boundingBox())!;
    expect(main.x + main.width).toBe(1280);
    if (width === 284) await page.getByTitle("Close sidebar").click();
  }
});

for (const [theme, { accent }] of Object.entries(ACCENTS)) {
  test(`${theme}: the open chat is marked with an accent wash and a glowing bar`, async ({
    page,
  }) => {
    await openChat(page, `Other ${theme} chat`);
    await openChat(page, `Open ${theme} chat`);
    await useTheme(page, theme);

    const row = (title: string) =>
      sidebar(page).getByRole("button", { name: title }).locator("..");
    const look = (title: string) =>
      row(title).evaluate((element) => {
        const bar = getComputedStyle(element, "::before");
        return {
          wash: getComputedStyle(element).backgroundImage,
          bar: bar.content === "none" ? "none" : bar.backgroundColor,
          glow: bar.content === "none" ? "none" : bar.boxShadow,
        };
      });

    const open = await look(`Open ${theme} chat`);
    expect(open.wash).toContain("linear-gradient");
    expect(open.bar).toBe(accent);
    expect(open.glow).toContain(accent);
    expect(await look(`Other ${theme} chat`)).toEqual({
      wash: "none",
      bar: "none",
      glow: "none",
    });
  });
}

test("a long chat title in the sidebar ends in …, and its menu shows on hover and on focus", async ({
  page,
}) => {
  // 120 characters, and unlike any title another test leaves behind.
  const title = "Sidebar long title ".repeat(7).slice(0, 120);
  await openChat(page, title);
  await page.goto("/");
  const text = sidebar(page).getByText(title);
  await expect(text).toHaveCSS("text-overflow", "ellipsis");
  expect(await text.evaluate((e) => e.scrollWidth > e.clientWidth)).toBe(true);

  const row = sidebar(page).getByRole("button", { name: title }).locator("..");
  const menu = row.getByTitle("Chat options");
  await expect(menu).toHaveCSS("opacity", "0");
  await row.hover();
  await expect(menu).toHaveCSS("opacity", "1");
  await page.mouse.move(800, 400);
  await expect(menu).toHaveCSS("opacity", "0");

  await sidebar(page).getByRole("button", { name: title }).focus();
  await page.keyboard.press("Tab");
  await expect(menu).toBeFocused();
  await expect(menu).toHaveCSS("opacity", "1");
});

test("the notes status shows progress while updating, and a failure in the error colour", async ({
  page,
}) => {
  await fakeNotesStatus(page, {
    updating: true,
    new: 3,
    changed: 1,
    done: 1,
    total: 4,
  });
  await page.goto("/");
  const label = page.getByText("Updating notes: 3 new, 1 changed, 0 deleted");
  await expect(label).toBeVisible();
  // The bar is a quarter of its track: one file done of four.
  const track = label.locator("../..").locator(":scope > div").nth(1);
  const bar = track.locator("div");
  await expect
    .poll(async () => {
      const [whole, done] = [
        (await track.boundingBox())!,
        (await bar.boundingBox())!,
      ];
      return Math.round((done.width / whole.width) * 100);
    })
    .toBe(25);
  await expect(page.getByTitle("Refresh notes")).toBeDisabled();

  await page.unroute("**/api/notes/status");
  await fakeNotesStatus(page, { error: "The notes folder couldn't be found." });
  await page.goto("/");
  await expect(
    page.getByText("Your notes didn't finish updating"),
  ).toBeVisible();
  await expect(page.getByRole("alert")).toHaveText(
    "The notes folder couldn't be found.",
  );
  await expect(page.getByRole("alert")).toHaveCSS("color", "rgb(245, 158, 11)");
});

test("the API cost tooltip in the sidebar stays inside the window, from 600px to 1600px", async ({
  page,
}) => {
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 800 });
    await page.goto("/");
    await showSidebar(page);
    const cost = sidebar(page).getByRole("button", {
      name: /API cost of everything/,
    });
    await cost.hover();
    const tooltip = sidebar(page).getByRole("tooltip");
    await expect(tooltip).toBeVisible();
    await expectInsideWindow(page, tooltip);
  }
});

// 30B: the chat header.

test("the header is a glass pill, centred and inside the main area, from 600px to 1600px", async ({
  page,
}) => {
  await openChat(page, LONG_TITLE);
  for (const title of [LONG_TITLE, "Short"]) {
    const chatId = page.url().split("/chat/")[1];
    await page.request.patch(`/api/chats/${chatId}`, { data: { title } });
    for (const width of WIDTHS) {
      await page.setViewportSize({ width, height: 800 });
      await page.reload();
      await expect(page.getByRole("heading", { name: title })).toBeVisible();
      const [main, box] = [
        (await page.locator("main").boundingBox())!,
        (await pill(page).boundingBox())!,
      ];
      const where = `"${title.slice(0, 10)}" at ${width}px`;
      expect(box.x, where).toBeGreaterThanOrEqual(main.x);
      expect(box.x + box.width, where).toBeLessThanOrEqual(width);
      expect(
        Math.abs(box.x + box.width / 2 - (main.x + width) / 2),
        where,
      ).toBeLessThanOrEqual(1);
      // A pill only as wide as what it holds, not a bar across the page.
      expect(box.width, where).toBeLessThanOrEqual(760);
    }
  }
  await expect(pill(page)).toHaveCSS("backdrop-filter", /blur/);
  await expect(pill(page)).toHaveCSS("border-radius", "999px");
});

test("the conversation starts below the pill and fades out before passing under it", async ({
  page,
}) => {
  await openChat(page, "Fade check", ["codeblocks please", "callouts please"]);
  const first = page.locator('[id^="message-"]').first();
  const scroller = first.locator("../..");
  await scroller.evaluate((element) => (element.scrollTop = 0));

  const pillBottom = await pill(page).evaluate(
    (element) => element.getBoundingClientRect().bottom,
  );
  expect((await first.boundingBox())!.y).toBeGreaterThanOrEqual(pillBottom);

  // The fade is a mask, see-through from the top down to the pill's bottom
  // edge, so nothing behind the pill can be read through it.
  const mask = await scroller.evaluate(
    (element) => getComputedStyle(element).maskImage,
  );
  expect(mask).toMatch(
    new RegExp(`^linear-gradient\\(.*rgba\\(0, 0, 0, 0\\) ${pillBottom}px`),
  );

  // A question jumped to from the Questions menu stops below the pill too.
  await page.getByRole("button", { name: "Questions" }).click();
  await page.getByRole("menuitem", { name: /callouts please/ }).click();
  const target = page.locator('[id^="message-"]').nth(2);
  await expect(target).toBeFocused();
  expect((await target.boundingBox())!.y).toBeGreaterThanOrEqual(pillBottom);
});

test("the Questions menu opens under the pill, inside the window, and Escape returns focus", async ({
  page,
}) => {
  await openChat(page, LONG_TITLE, ["first question", "second question"]);
  for (const width of [600, 1280]) {
    await page.setViewportSize({ width, height: 800 });
    const questions = page.getByRole("button", { name: "Questions" });
    await questions.click();
    const menu = page.getByRole("menu");
    await expect(menu).toBeVisible();
    await expect(menu).toHaveCSS("backdrop-filter", /blur/);
    await expect(menu).toHaveCSS("border-top-color", STRONG_EDGE);
    await expectInsideWindow(page, menu);
    const pillBox = (await pill(page).boundingBox())!;
    expect((await menu.boundingBox())!.y).toBeGreaterThanOrEqual(
      pillBox.y + pillBox.height,
    );
    await page.keyboard.press("Escape");
    await expect(menu).toHaveCount(0);
    await expect(questions).toBeFocused();
  }
});

// 30C: menus and dialogs.

for (const [theme, { accent, onAccent }] of Object.entries(ACCENTS)) {
  test(`${theme}: search matches are marked with the accent, like a highlighter`, async ({
    page,
  }) => {
    await openChat(page, `Highlighter ${theme}`, ["marking zebras"]);
    await useTheme(page, theme);
    await page.keyboard.press("Control+k");
    const dialog = page.getByRole("dialog");
    await expect(dialog).toHaveCSS("backdrop-filter", /blur/);
    await expect(dialog).toHaveCSS("border-top-color", STRONG_EDGE);

    // "highl" finds the title; only the letters typed are marked.
    await dialog.getByRole("textbox").fill("highl");
    const result = dialog.getByRole("button", {
      name: `Highlighter ${theme}`,
    });
    await expect(result).toBeVisible();
    const match = result.locator("mark");
    await expect(match).toHaveText("Highl");
    await expect(match).toHaveCSS("background-color", accent);
    await expect(match).toHaveCSS("color", onAccent);

    // Two words, found in the message: each is marked in the snippet.
    await dialog.getByRole("textbox").fill("zeb mark");
    await expect(result.locator("mark")).toHaveText(["mark", "zeb"]);
  });
}

test("at 600px the search and delete dialogs fit, and delete opens above the floating sidebar", async ({
  page,
}) => {
  await openChat(page, "Dialog check");
  await page.setViewportSize({ width: 600, height: 800 });

  await page.keyboard.press("Control+k");
  await expect(page.getByRole("dialog")).toBeVisible();
  await expectInsideWindow(page, page.getByRole("dialog"));
  await page.keyboard.press("Escape");

  await showSidebar(page);
  const row = sidebar(page)
    .getByRole("button", { name: "Dialog check" })
    .locator("..");
  await row.hover();
  await row.getByTitle("Chat options").click();
  const menu = page.getByRole("menu");
  await expect(menu).toHaveCSS("backdrop-filter", /blur/);
  await expect(menu).toHaveCSS("border-top-color", STRONG_EDGE);
  await expectInsideWindow(page, menu);
  await page.getByRole("menuitem", { name: "Delete" }).click();

  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expectInsideWindow(page, dialog);
  // The sidebar is still open underneath, and the dialog is what is on top.
  await expect(page.getByTitle("Close sidebar")).toBeVisible();
  const onTop = await dialog.evaluate((element) => {
    const box = element.getBoundingClientRect();
    const top = document.elementFromPoint(
      box.x + box.width / 2,
      box.y + box.height / 2,
    );
    return element.contains(top);
  });
  expect(onTop).toBe(true);
});
