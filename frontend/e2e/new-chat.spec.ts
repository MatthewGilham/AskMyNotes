import { expect, test, type Locator, type Page } from "@playwright/test";
import { join } from "node:path";

// Phase 31: the new chat screen (the poster greeting and the prompt cards),
// the glass message box used on both screens, and the cover shown while files
// are dragged over the chat.

const documentsDir = join(process.env.E2E_DATA_DIR ?? "", "documents");
const PNG_BASE64 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";
const png = (name: string) => ({
  name,
  mimeType: "image/png",
  buffer: Buffer.from(PNG_BASE64, "base64"),
});
const ACCENTS = {
  volt: { accent: "rgb(204, 255, 51)", onAccent: "rgb(18, 25, 0)" },
  aurora: { accent: "rgb(167, 139, 250)", onAccent: "rgb(10, 7, 20)" },
  ice: { accent: "rgb(242, 246, 255)", onAccent: "rgb(10, 12, 16)" },
};
const ERROR_COLOUR = "rgb(245, 158, 11)";

const messageBox = (page: Page) => page.getByLabel("Message");
const attachInput = (page: Page) => page.getByLabel("Attach files or images");
const greeting = (page: Page) => page.locator("main h1");
// The glass box around the message field.
const box = (page: Page) => messageBox(page).locator("..");
const prompts = (page: Page) =>
  page.getByRole("button", {
    name: /^(Explain depreciation|Give me a recipe)$/,
  });

/** Volt is the default theme, so it has no attribute. */
async function useTheme(page: Page, theme: string) {
  await page.evaluate((name) => {
    if (name === "volt") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", name);
  }, theme);
}

async function expectInsideWindow(page: Page, element: Locator) {
  const bounds = (await element.boundingBox())!;
  const { width, height } = page.viewportSize()!;
  expect(bounds.x).toBeGreaterThanOrEqual(0);
  expect(bounds.y).toBeGreaterThanOrEqual(0);
  expect(bounds.x + bounds.width).toBeLessThanOrEqual(width);
  expect(bounds.y + bounds.height).toBeLessThanOrEqual(height);
}

const sidewaysScroll = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);

/** How many animations are running on the greeting right now. */
const greetingAnimations = (page: Page) =>
  greeting(page).evaluate((element) => element.getAnimations().length);

// 31A: the new chat screen.

test("the greeting reads as one sentence, set on two lines", async ({
  page,
}) => {
  await page.goto("/");
  const weekday = new Date().toLocaleDateString("en-GB", { weekday: "long" });
  expect(await greeting(page).evaluate((e) => e.textContent)).toBe(
    `Happy ${weekday}, Matt`,
  );
  await expect(
    page.getByRole("heading", { name: `Happy ${weekday}, Matt`, exact: true }),
  ).toBeVisible();

  // The name is on a line of its own, under "Happy <day>,".
  const [heading, name] = [
    (await greeting(page).boundingBox())!,
    (await greeting(page).locator("span").boundingBox())!,
  ];
  expect(name.y).toBeGreaterThan(heading.y + heading.height / 3);
  expect(name.x).toBe(heading.x);
});

test("at 600px the mark, both lines of the greeting and every prompt fit", async ({
  page,
}) => {
  await page.setViewportSize({ width: 600, height: 800 });
  await page.goto("/");
  await expect(prompts(page)).toHaveCount(2);
  for (const part of [
    greeting(page).locator("..").getByRole("img"),
    greeting(page),
    greeting(page).locator("span"),
    ...(await prompts(page).all()),
  ])
    await expectInsideWindow(page, part);
  // No letter is cut off or pushed onto a third line.
  expect(
    await greeting(page).evaluate((e) => e.scrollWidth <= e.clientWidth),
  ).toBe(true);
  expect(await sidewaysScroll(page)).toBe(0);
});

test("the light sweeps the greeting once as the screen loads, then stops", async ({
  page,
}) => {
  await page.goto("/");
  await expect(greeting(page)).toBeVisible();
  expect(await greetingAnimations(page)).toBe(1);
  await page.waitForTimeout(3000);
  expect(await greetingAnimations(page)).toBe(0);
  // It rests as plain text: the band of accent is off to one side.
  await expect(greeting(page)).toHaveCSS(
    "background-position",
    /^0(px|%) 0(px|%)$/,
  );
});

test("with reduced motion the greeting never animates", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(greeting(page)).toBeVisible();
  expect(await greetingAnimations(page)).toBe(0);
});

test("the prompts are cards: two columns, one below 700px", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/");
  await expect(prompts(page)).toHaveCount(2);
  const [first, second] = await Promise.all(
    (await prompts(page).all()).map(
      async (card) => (await card.boundingBox())!,
    ),
  );
  expect(second.y).toBe(first.y);
  expect(second.x).toBeGreaterThan(first.x + first.width);
  expect(second.width).toBeCloseTo(first.width, 0);

  for (const [width, columns] of [
    [700, 2],
    [699, 1],
    [600, 1],
  ]) {
    await page.setViewportSize({ width, height: 800 });
    const [top, next] = await Promise.all(
      (await prompts(page).all()).map(
        async (card) => (await card.boundingBox())!,
      ),
    );
    expect(next.y > top.y ? 1 : 2, `${width}px`).toBe(columns);
  }
});

test("prompts are disabled while the notes update, and send when clicked otherwise", async ({
  page,
}) => {
  await page.route("**/api/notes/status", (route) =>
    route.fulfill({
      json: {
        updating: true,
        new: 1,
        changed: 0,
        deleted: 0,
        done: 0,
        total: 1,
        fileCount: 0,
        unreadable: [],
        inUse: [],
        error: null,
      },
    }),
  );
  await page.goto("/");
  await expect(prompts(page)).toHaveCount(2);
  for (const prompt of await prompts(page).all()) {
    await expect(prompt).toBeDisabled();
    await expect(prompt).toHaveCSS("opacity", "0.5");
  }

  await page.unroute("**/api/notes/status");
  await page.reload();
  await expect(prompts(page).first()).toBeEnabled();
  await prompts(page).first().click();
  await expect(page).toHaveURL(/\/chat\//);
  await expect(page.getByText("You said: Explain depreciation")).toBeVisible();
});

// 31B: the message box.

test("the message box is glass with 26px corners, on both screens", async ({
  page,
}) => {
  await page.goto("/");
  for (const screen of ["new chat", "conversation"]) {
    await expect(box(page), screen).toHaveCSS("backdrop-filter", /blur/);
    await expect(box(page), screen).toHaveCSS("border-radius", "26px");
    if (screen === "new chat") {
      await messageBox(page).fill("hello");
      await messageBox(page).press("Enter");
      await expect(page.getByTitle("Regenerate")).toBeVisible();
    }
  }
});

for (const [theme, { accent, onAccent }] of Object.entries(ACCENTS)) {
  test(`${theme}: the box's edge is a hairline at rest and the accent gradient in use`, async ({
    page,
  }) => {
    await page.goto("/");
    await useTheme(page, theme);
    const edge = () =>
      box(page).evaluate(
        (element) => getComputedStyle(element, "::before").backgroundImage,
      );
    await messageBox(page).focus();
    expect(await edge()).toContain(`linear-gradient(135deg, ${accent}`);

    await messageBox(page).blur();
    expect(await edge()).toBe("none");
    expect(
      await box(page).evaluate(
        (element) => getComputedStyle(element, "::before").backgroundColor,
      ),
    ).toBe("rgba(255, 255, 255, 0.16)");
  });

  test(`${theme}: the Python button fills with the accent when on`, async ({
    page,
  }) => {
    await page.goto("/");
    await useTheme(page, theme);
    const python = page.getByRole("button", { name: "Python", exact: true });
    await expect(python).toHaveAttribute("aria-pressed", "false");
    await expect(python).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");

    await python.focus();
    await page.keyboard.press("Space");
    await expect(python).toHaveAttribute("aria-pressed", "true");
    await expect(python).toHaveCSS("background-color", accent);
    await expect(python).toHaveCSS("color", onAccent);
  });
}

test("the send button is Send, then Stop, and big enough to hit", async ({
  page,
}) => {
  await page.goto("/");
  const size = async (button: Locator) => {
    const bounds = (await button.boundingBox())!;
    return Math.min(bounds.width, bounds.height);
  };
  const send = page.getByTitle("Send");
  await expect(send).toBeDisabled();
  expect(await size(send)).toBeGreaterThanOrEqual(36);

  await messageBox(page).fill("slow reply please");
  await expect(send).toBeEnabled();
  await send.click();
  await expect(page.getByText("You said: slow reply")).toBeVisible();
  const stop = page.getByTitle("Stop");
  await expect(stop).toBeVisible();
  expect(await size(stop)).toBeGreaterThanOrEqual(36);
  await stop.click();
  await expect(page.getByTitle("Send")).toBeVisible();
});

test("thirty lines grow the box to its maximum height, then the text scrolls inside it", async ({
  page,
}) => {
  await page.goto("/");
  const height = async () => (await messageBox(page).boundingBox())!.height;
  const oneLine = await height();
  await messageBox(page).fill("line\n".repeat(4));
  const fiveLines = await height();
  expect(fiveLines).toBeGreaterThan(oneLine);

  await messageBox(page).fill("line\n".repeat(29));
  expect(await height()).toBe(240);
  await messageBox(page).fill("line\n".repeat(59));
  expect(await height()).toBe(240);
  expect(
    await messageBox(page).evaluate((e) => e.scrollHeight > e.clientHeight),
  ).toBe(true);
  await expectInsideWindow(page, box(page));
});

test("at 600px four images and five documents wrap onto new lines", async ({
  page,
}) => {
  await page.setViewportSize({ width: 600, height: 800 });
  await page.goto("/");
  await attachInput(page).setInputFiles(
    [1, 2, 3, 4].map((number) => png(`image-${number}.png`)),
  );
  await attachInput(page).setInputFiles(
    [1, 2, 3, 4, 5].map((number) => ({
      name: `a-document-with-quite-a-long-name-${number}.pdf`,
      mimeType: "application/pdf",
      buffer: Buffer.from("made-up text"),
    })),
  );
  const chips = page.getByTitle(/^a-document-with-quite-a-long-name-\d\.pdf$/);
  await expect(page.getByRole("img", { name: /image-\d\.png/ })).toHaveCount(4);
  await expect(chips).toHaveCount(5);

  expect(await sidewaysScroll(page)).toBe(0);
  const inside = (await box(page).boundingBox())!;
  const rows = new Set<number>();
  for (const chip of await chips.all()) {
    const bounds = (await chip.boundingBox())!;
    expect(bounds.x).toBeGreaterThanOrEqual(inside.x);
    expect(bounds.x + bounds.width).toBeLessThanOrEqual(
      inside.x + inside.width,
    );
    rows.add(bounds.y);
  }
  expect(rows.size).toBeGreaterThan(1);
});

test("a refused attachment and a failed send both show in the error colour", async ({
  page,
}) => {
  await page.goto("/");
  await attachInput(page).setInputFiles({
    name: "program.exe",
    mimeType: "application/octet-stream",
    buffer: Buffer.from("MZ"),
  });
  const refusal = page.getByRole("alert");
  await expect(refusal).toContainText("isn't a supported file type");
  await expect(refusal).toHaveCSS("color", ERROR_COLOUR);

  await page.goto("/");
  await attachInput(page).setInputFiles(join(documentsDir, "long.docx"));
  await messageBox(page).fill("Read this");
  await messageBox(page).press("Enter");
  const failure = page.getByRole("alert");
  await expect(failure).toContainText("more than the 100 allowed");
  await expect(failure).toHaveCSS("color", ERROR_COLOUR);
});

// 31C: dropping files.

test("the drop cover is glass with an accent outline, over the main area only", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/");
  const transfer = await page.evaluateHandle(() => {
    const data = new DataTransfer();
    data.items.add(new File(["x"], "dropped.txt", { type: "text/plain" }));
    return data;
  });
  await messageBox(page).dispatchEvent("dragenter", { dataTransfer: transfer });
  const cover = page.getByText("Drop files to attach");
  await expect(cover).toBeVisible();
  await expect(cover).toHaveCSS("backdrop-filter", /blur/);
  await expect(cover).toHaveCSS("outline-color", ACCENTS.volt.accent);
  await expect(cover).toHaveCSS("outline-style", "dashed");

  const [main, sidebar, bounds] = [
    (await page.locator("main").boundingBox())!,
    (await page.getByRole("navigation", { name: "Chats" }).boundingBox())!,
    (await cover.boundingBox())!,
  ];
  expect(bounds.x).toBeGreaterThanOrEqual(sidebar.x + sidebar.width);
  expect(bounds.x).toBeGreaterThanOrEqual(main.x);
  expect(bounds.x + bounds.width).toBeLessThanOrEqual(main.x + main.width);
  expect(bounds.width).toBeGreaterThan(main.width * 0.9);
});
