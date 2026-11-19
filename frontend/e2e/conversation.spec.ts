import { expect, test, type Locator, type Page } from "@playwright/test";

// Phase 32: the conversation in the redesign. Your messages are glass
// bubbles; answers keep their reserved colours on the panel colour; the
// status lines, Jump to latest, the missing-message notice and Ask about this
// are restyled. Made-up chats are served by routes, as in navigation.spec.ts.

const ACCENTS = {
  volt: "rgb(204, 255, 51)",
  aurora: "rgb(167, 139, 250)",
  ice: "rgb(242, 246, 255)",
};
const RESERVED = {
  "Beyond your notes": "rgb(251, 113, 133)",
  "From the web": "rgb(96, 165, 250)",
  "Key formula": "rgb(167, 139, 250)",
  "Exam tip": "rgb(34, 211, 238)",
};

const COLUMNS = Array.from({ length: 12 }, (_, i) => `Column${i + 1}`);
const BLOCKS_ANSWER = [
  "## A heading",
  "",
  "Body text with a [plain link](https://example.test/page).",
  "",
  `| ${COLUMNS.join(" | ")} |`,
  `|${"---|".repeat(12)}`,
  `| ${COLUMNS.map(() => "Depreciation").join(" | ")} |`,
  "",
  ":::beyond",
  "Something from outside your notes.",
  ":::",
  "",
  ":::web",
  "A figure from a page ([example.test](https://example.test/rate)).",
  ":::",
  "",
  ":::formula",
  "\\( a = b + c \\)",
  ":::",
  "",
  ":::tip",
  "Write the formula first.",
  ":::",
].join("\n");

/** A made-up chat, served at /api/chats/<id>. */
async function serveChat(
  page: Page,
  id: string,
  messages: { role: "user" | "assistant"; content: string }[],
) {
  await page.route(`**/api/chats/${id}`, (route) =>
    route.fulfill({
      json: {
        id,
        title: `Made-up ${id}`,
        pinned: false,
        lastUsedAt: new Date().toISOString(),
        messages: messages.map((message, index) => ({
          id: index + 1,
          images: [],
          status: "complete",
          sources: null,
          error: null,
          ...message,
        })),
      },
    }),
  );
}

const serveBlocks = (page: Page) =>
  serveChat(page, "blocks", [
    { role: "user", content: "Show me everything" },
    { role: "assistant", content: BLOCKS_ANSWER },
  ]);

const serveLong = (page: Page) =>
  serveChat(
    page,
    "long",
    Array.from({ length: 40 }, (_, i) => ({
      role: i % 2 === 0 ? ("user" as const) : ("assistant" as const),
      content: `Message ${i + 1}. ` + "Study material. ".repeat(30),
    })),
  );

/** Volt is the default theme, so it has no attribute. */
async function useTheme(page: Page, theme: string) {
  await page.evaluate((name) => {
    if (name === "volt") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", name);
  }, theme);
}

async function bounds(element: Locator) {
  return (await element.boundingBox())!;
}

async function expectWithin(inner: Locator, outer: Locator) {
  const [a, b] = [await bounds(inner), await bounds(outer)];
  expect(a.x).toBeGreaterThanOrEqual(b.x);
  expect(a.y).toBeGreaterThanOrEqual(b.y);
  expect(a.x + a.width).toBeLessThanOrEqual(b.x + b.width + 0.5);
  expect(a.y + a.height).toBeLessThanOrEqual(b.y + b.height + 0.5);
}

const sidewaysScroll = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);

const messageBox = (page: Page) => page.getByLabel("Message");

// 32A: your messages.

for (const width of [600, 1280, 1600]) {
  test(`at ${width}px the edit box and its buttons fit inside the bubble`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 800 });
    await page.goto("/");
    await messageBox(page).fill("a question to edit");
    await messageBox(page).press("Enter");
    await expect(page.getByTitle("Regenerate")).toBeVisible();
    await page.getByRole("button", { name: "Edit latest question" }).click();

    const editor = page.getByLabel("Edit your latest question");
    const bubble = editor.locator("../..");
    await expectWithin(editor, bubble);
    for (const name of ["Cancel", "Save & resend"])
      await expectWithin(page.getByRole("button", { name }), bubble);
    expect(await sidewaysScroll(page)).toBe(0);
  });
}

test("your message is a glass bubble with one tight corner, and Edit shows on focus", async ({
  page,
}) => {
  await page.goto("/");
  await messageBox(page).fill("a bubble");
  await messageBox(page).press("Enter");
  await expect(page.getByTitle("Regenerate")).toBeVisible();
  const bubble = page
    .locator('[id^="message-"]')
    .first()
    .getByText("a bubble", { exact: true })
    .locator("..");
  await expect(bubble).toHaveCSS("background-image", /linear-gradient/);
  await expect(bubble).toHaveCSS("border-bottom-right-radius", "8px");
  await expect(bubble).toHaveCSS("border-top-left-radius", "24px");

  // The bubble is only as tall as its text: Edit sits outside it.
  const edit = page.getByRole("button", { name: "Edit latest question" });
  await expect(edit).toHaveCSS("opacity", "0");
  const [button, box] = [await bounds(edit), await bounds(bubble)];
  expect(button.x + button.width).toBeLessThanOrEqual(box.x);
  await edit.focus();
  await expect(edit).toHaveCSS("opacity", "1");
});

// 32B: answers.

for (const theme of Object.keys(ACCENTS)) {
  test(`${theme}: labelled blocks and callouts keep their reserved colours, on a pane`, async ({
    page,
  }) => {
    await serveBlocks(page);
    await page.goto("/chat/blocks");
    await useTheme(page, theme);
    for (const [label, colour] of Object.entries(RESERVED)) {
      const text = page.getByText(label, { exact: true });
      await expect(text).toHaveCSS("color", colour);
      // The block behind the label lies on the panel colour, not the bare
      // backdrop.
      const block = text.locator("xpath=ancestor::aside[1]");
      expect(
        await block.evaluate((e) => getComputedStyle(e).backgroundColor),
      ).not.toBe("rgba(0, 0, 0, 0)");
    }
  });
}

test("at 600px a 12-column table scrolls inside its own box", async ({
  page,
}) => {
  await page.setViewportSize({ width: 600, height: 800 });
  await serveBlocks(page);
  await page.goto("/chat/blocks");
  const table = page.locator("table");
  await expect(table).toBeVisible();
  expect(await table.evaluate((e) => e.scrollWidth > e.clientWidth)).toBe(true);
  const box = await bounds(table);
  expect(box.x + box.width).toBeLessThanOrEqual(600);
  expect(await sidewaysScroll(page)).toBe(0);
});

test("a link in an answer opens in a new tab", async ({ page }) => {
  await serveBlocks(page);
  await page.goto("/chat/blocks");
  const link = page.getByRole("link", { name: "plain link" });
  await expect(link).toHaveAttribute("target", "_blank");
  await expect(link).toHaveAttribute("rel", "noopener noreferrer");
});

test("code sits in a darker inset with its language and Copy", async ({
  page,
}) => {
  await page.goto("/");
  await messageBox(page).fill("show me codeblocks");
  await messageBox(page).press("Enter");
  const python = page.locator("code.language-python");
  await expect(python).toBeVisible();
  const block = python.locator("xpath=ancestor::div[pre][1]");
  await expect(block).toHaveCSS("background-image", /linear-gradient/);
  await expect(block).toHaveCSS("border-top-left-radius", "16px");
  await expect(
    block.getByRole("button", { name: "Copy python code" }),
  ).toBeVisible();
});

// 32C: states and actions.

for (const width of [600, 1280]) {
  test(`at ${width}px Jump to latest is a glass pill above the message box`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 800 });
    await serveLong(page);
    await page.goto("/chat/long");
    await expect(page.locator("#message-40")).toBeInViewport();
    await page.locator("#message-1").evaluate((e) => e.scrollIntoView());
    const latest = page.getByRole("button", { name: "Jump to latest" });
    await expect(latest).toBeVisible();
    await expect(latest).toHaveCSS("backdrop-filter", /blur/);
    const [pill, box] = [
      await bounds(latest),
      await bounds(messageBox(page).locator("..")),
    ];
    expect(pill.y + pill.height).toBeLessThanOrEqual(box.y);
  });
}

test("tabbing to Copy shows the answer's actions", async ({ page }) => {
  await serveLong(page);
  await page.goto("/chat/long");
  const answer = page.locator("#message-40 [data-quote-answer]");
  await answer.focus();
  const copy = page.locator("#message-40").getByTitle("Copy", { exact: true });
  await expect(copy.locator("..")).toHaveCSS("opacity", "0");
  await page.keyboard.press("Tab");
  await expect(copy).toBeFocused();
  await expect(copy.locator("..")).toHaveCSS("opacity", "1");
});

test("the missing-message notice is styled, inside the column and below the header", async ({
  page,
}) => {
  await serveLong(page);
  await page.goto("/chat/long#message-999");
  const notice = page
    .getByRole("status")
    .filter({ hasText: "no longer available" });
  await expect(notice).toBeVisible();
  await expect(notice).toHaveCSS("border-top-style", "solid");
  expect(
    await notice.evaluate((e) => getComputedStyle(e).backgroundColor),
  ).not.toBe("rgba(0, 0, 0, 0)");

  const [box, header, column] = [
    await bounds(notice),
    await bounds(page.locator("main header")),
    await bounds(page.locator("#message-1").locator("..")),
  ];
  expect(box.y).toBeGreaterThanOrEqual(header.y + header.height);
  expect(box.x).toBeGreaterThanOrEqual(column.x);
  expect(box.x + box.width).toBeLessThanOrEqual(column.x + column.width);
});

/** How many animations are running on an element and inside it. */
const animations = (element: Locator) =>
  element.evaluate((e) => e.getAnimations({ subtree: true }).length);

test("a status line has a light passing through it, and none with reduced motion", async ({
  page,
}) => {
  const searching = page
    .getByRole("status")
    .filter({ hasText: "Searching the web…" });
  await page.goto("/");
  await messageBox(page).fill("slowsearch the web");
  await messageBox(page).press("Enter");
  await expect(searching).toBeVisible();
  expect(await animations(searching)).toBeGreaterThan(0);
  await expect(page.getByTitle("Send")).toBeVisible({ timeout: 15_000 });

  await page.emulateMedia({ reducedMotion: "reduce" });
  await messageBox(page).fill("slowsearch the web again");
  await messageBox(page).press("Enter");
  await expect(searching).toBeVisible();
  expect(await animations(searching)).toBe(0);
  await expect(searching).toHaveCSS("color", "rgb(181, 174, 198)");
});

test("at 600px Ask about this is an accent pill inside the window", async ({
  page,
}) => {
  await page.setViewportSize({ width: 600, height: 800 });
  await serveLong(page);
  await page.goto("/chat/long");
  const ask = page.getByRole("button", { name: "Ask about this", exact: true });
  // Any scroll hides the action, and the chat may still be settling at its
  // end as it opens, so the selection is made again until the action stays.
  await expect(async () => {
    await page.locator("#message-40 [data-quote-answer] p").evaluate((e) => {
      const range = document.createRange();
      range.selectNodeContents(e);
      const selection = window.getSelection()!;
      selection.removeAllRanges();
      selection.addRange(range);
    });
    await expect(ask).toHaveCSS("background-color", ACCENTS.volt, {
      timeout: 1000,
    });
  }).toPass();
  const box = await bounds(ask);
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(600);
  expect(box.y + box.height).toBeLessThanOrEqual(800);
});
