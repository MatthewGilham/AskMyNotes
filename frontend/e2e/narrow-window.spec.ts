import { expect, test, type Locator, type Page } from "@playwright/test";
import { join } from "node:path";

// Phase 27: the app in narrow windows. Widths are CSS pixels, which is what a
// zoomed-in browser gives the page too. Below 900px the sidebar is a rail, and
// opening it floats it over the conversation.

const documentsDir = join(process.env.E2E_DATA_DIR ?? "", "documents");
const LONG_TITLE = "Long title ".repeat(11).trim(); // 120 characters
const WIDTHS = [600, 800, 1024, 1280, 1600];

const messageBox = (page: Page) => page.getByLabel("Message");

async function send(page: Page, text: string) {
  const messages = page.locator('[id^="message-"]');
  const before = await messages.count();
  await messageBox(page).fill(text);
  await messageBox(page).press("Enter");
  // The question and its reply are on screen, and the reply offers Regenerate
  // once it has finished.
  await expect(messages).toHaveCount(before + 2);
  await expect(page.getByTitle("Regenerate")).toHaveCount(1);
}

/** A chat with a table, diagrams, code, a document chip and a long title. */
async function openFullConversation(page: Page) {
  await page.goto("/");
  await send(page, "narrow layout check");
  await expect(page).toHaveURL(/\/chat\//);
  await send(page, "show me diagrams");
  await send(page, "codeblocks please");
  await page
    .getByLabel("Attach files or images")
    .setInputFiles(join(documentsDir, "essay.docx"));
  await send(page, "Summarise my essay");
  const chatId = page.url().split("/chat/")[1];
  await page.request.patch(`/api/chats/${chatId}`, {
    data: { title: LONG_TITLE },
  });
  await page.reload();
  await expect(page.getByRole("img", { name: "Diagram" })).toHaveCount(3);
  return chatId;
}

const sidewaysScroll = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);

/**
 * How far an element's centre is from the centre of what you can see beside
 * the sidebar: from the left of `main` to the window's right edge (`main`
 * itself could be wider than the window, which was the original bug).
 */
async function offCentre(page: Page, element: Locator) {
  const main = (await page.locator("main").boundingBox())!;
  const visibleCentre = (main.x + page.viewportSize()!.width) / 2;
  const box = (await element.boundingBox())!;
  return Math.abs(box.x + box.width / 2 - visibleCentre);
}

async function expectInsideWindow(page: Page, element: Locator) {
  const box = (await element.boundingBox())!;
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(page.viewportSize()!.width);
}

// The new chat screen's column: the greeting row, the message box, the prompts.
const newChatParts = (page: Page) =>
  page.locator("main h1").locator("..").locator("..").locator(":scope > div");

const floatingSidebar = (page: Page) => page.getByTitle("Close sidebar");
const openSidebarButton = (page: Page) => page.getByTitle("Open sidebar");
// The rail is still underneath, so look inside the floating sidebar itself.
const floatingNav = (page: Page) =>
  page
    .getByRole("navigation", { name: "Chats" })
    .filter({ has: floatingSidebar(page) });

test("the page never scrolls sideways, from 600px to 1600px", async ({
  page,
}) => {
  const chatId = await openFullConversation(page);
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 800 });
    await page.goto("/");
    await expect(messageBox(page)).toBeVisible();
    expect(await sidewaysScroll(page), `new chat at ${width}px`).toBe(0);

    await page.goto(`/chat/${chatId}`);
    await expect(page.getByRole("img", { name: "Diagram" })).toHaveCount(3);
    await expect(page.getByTitle("essay.docx", { exact: true })).toBeVisible();
    expect(await sidewaysScroll(page), `conversation at ${width}px`).toBe(0);
  }
});

test("the new chat screen and the conversation are centred in narrow windows", async ({
  page,
}) => {
  const chatId = await openFullConversation(page);
  for (const width of [600, 800, 1024]) {
    await page.setViewportSize({ width, height: 800 });
    await page.goto("/");
    const [greeting, composer, prompts] = [0, 1, 2].map((index) =>
      newChatParts(page).nth(index),
    );
    await expect(prompts).toBeVisible();
    for (const part of [greeting, composer, prompts])
      expect(await offCentre(page, part)).toBeLessThanOrEqual(1);

    await page.goto(`/chat/${chatId}`);
    const column = page.locator('[id^="message-"]').first().locator("..");
    const dock = page
      .locator("main header")
      .locator("..")
      .locator(":scope > div")
      .last();
    await expect(column).toBeVisible();
    expect(await offCentre(page, column)).toBeLessThanOrEqual(1);
    expect(await offCentre(page, dock)).toBeLessThanOrEqual(1);
  }
});

test("at 600px the greeting and prompts fit; the greeting is poster-sized in wide windows", async ({
  page,
}) => {
  await page.setViewportSize({ width: 600, height: 800 });
  await page.goto("/");
  await expect(page.locator("main h1")).toBeVisible();
  await expectInsideWindow(page, newChatParts(page).first());
  const size = (px: string) => Number(px.replace("px", ""));
  const fontSize = () =>
    page.locator("main h1").evaluate((e) => getComputedStyle(e).fontSize);
  expect(size(await fontSize())).toBeGreaterThanOrEqual(34);
  const prompts = newChatParts(page).nth(2).locator("button");
  for (const prompt of await prompts.all())
    await expectInsideWindow(page, prompt);

  // Redesign, phase 31: the greeting is deliberately larger. It is 6.2% of the
  // window's width, up to 84px.
  await page.setViewportSize({ width: 1280, height: 800 });
  expect(size(await fontSize())).toBeCloseTo(79.36, 1);
  await page.setViewportSize({ width: 1600, height: 800 });
  await expect(page.locator("main h1")).toHaveCSS("font-size", "84px");
});

test("at 600px a long title is shortened and the header controls still work", async ({
  page,
}) => {
  await openFullConversation(page);
  await page.setViewportSize({ width: 600, height: 800 });

  const title = page.getByRole("heading", { name: LONG_TITLE });
  await expect(title).toHaveText(LONG_TITLE);
  await expect(title).toHaveCSS("text-overflow", "ellipsis");
  expect(
    await title.evaluate((e) => e.scrollWidth > e.clientWidth),
    "the title is cut short",
  ).toBe(true);

  const cost = page.getByRole("button", { name: /API cost of this chat/ });
  const ring = page.getByRole("button", { name: /Context used/ });
  const questions = page.getByRole("button", { name: "Questions" });
  for (const control of [cost, ring, questions])
    await expectInsideWindow(page, control);

  await cost.hover();
  await expectInsideWindow(page, page.getByRole("tooltip").first());
  await page.mouse.move(0, 400);
  await ring.focus();
  // Hidden tooltips aren't found by role, so this is the ring's.
  await expect(page.getByRole("tooltip")).toContainText("tokens");
  await expectInsideWindow(page, page.getByRole("tooltip"));

  await questions.click();
  await expect(page.getByRole("menuitem").first()).toBeVisible();
  await expectInsideWindow(page, page.getByRole("menu"));
});

test("at 600px the edit box fits inside the conversation", async ({ page }) => {
  await page.setViewportSize({ width: 600, height: 800 });
  await page.goto("/");
  await send(page, "a question to edit");
  await page.getByRole("button", { name: "Edit latest question" }).click();
  const editor = page.locator("textarea").first();
  await expect(editor).toBeVisible();
  await expectInsideWindow(page, editor);
  expect(await sidewaysScroll(page)).toBe(0);
});

test("a narrow window starts with the rail, a wide one with the full sidebar", async ({
  page,
}) => {
  await page.setViewportSize({ width: 800, height: 800 });
  await page.goto("/");
  await expect(openSidebarButton(page)).toBeVisible();
  await expect(floatingSidebar(page)).toHaveCount(0);

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/");
  await expect(floatingSidebar(page)).toBeVisible();
});

test("narrowing collapses the sidebar, and widening restores your choice", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/");
  await expect(page.getByTitle("Close sidebar")).toBeVisible();

  await page.setViewportSize({ width: 800, height: 800 });
  await expect(openSidebarButton(page)).toBeVisible();
  await expect(page.getByTitle("Close sidebar")).toHaveCount(0);
  await page.setViewportSize({ width: 1280, height: 800 });
  await expect(page.getByTitle("Close sidebar")).toBeVisible();

  // Collapsed by you at 1280px, it stays collapsed after the same round trip.
  await page.getByTitle("Close sidebar").click();
  await page.setViewportSize({ width: 800, height: 800 });
  await page.setViewportSize({ width: 1280, height: 800 });
  await expect(openSidebarButton(page)).toBeVisible();
  await expect(page.getByTitle("Close sidebar")).toHaveCount(0);

  // Left open in a narrow window, it is closed the next time the window narrows.
  await page.setViewportSize({ width: 800, height: 800 });
  await openSidebarButton(page).click();
  await expect(floatingSidebar(page)).toBeVisible();
  await page.setViewportSize({ width: 1280, height: 800 });
  // Wide again, with the sidebar collapsed as you left it.
  await expect(floatingSidebar(page)).toHaveCount(0);
  await page.setViewportSize({ width: 800, height: 800 });
  await expect(openSidebarButton(page)).toBeVisible();
  await expect(floatingSidebar(page)).toHaveCount(0);
});

test("at 800px the floating sidebar covers the conversation without moving it", async ({
  page,
}) => {
  await page.setViewportSize({ width: 800, height: 800 });
  await page.goto("/");
  await send(page, "floating sidebar check");
  const column = page.locator('[id^="message-"]').first().locator("..");
  const before = await column.boundingBox();

  await openSidebarButton(page).click();
  await expect(floatingSidebar(page)).toBeVisible();
  expect(await column.boundingBox()).toEqual(before);
  // The backdrop is on top of the conversation: the message box can't be reached.
  const blocked = await page.evaluate(() => {
    const box = document.querySelector("textarea")!.getBoundingClientRect();
    const top = document.elementFromPoint(box.x + 20, box.y + 10);
    return top?.tagName !== "TEXTAREA";
  });
  expect(blocked).toBe(true);
});

test("Escape, the backdrop, a chat, New chat and Search each close the floating sidebar", async ({
  page,
}) => {
  await page.setViewportSize({ width: 800, height: 800 });
  await page.goto("/");
  await send(page, "first floating chat");
  const firstChat = page.url();
  await page.goto("/");
  await send(page, "second floating chat");

  await openSidebarButton(page).click();
  await expect(floatingSidebar(page)).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(floatingSidebar(page)).toHaveCount(0);
  await expect(openSidebarButton(page)).toBeFocused();

  await openSidebarButton(page).click();
  await page.mouse.click(700, 400);
  await expect(floatingSidebar(page)).toHaveCount(0);
  await expect(openSidebarButton(page)).toBeFocused();

  await openSidebarButton(page).click();
  await floatingNav(page).getByText("first floating chat").click();
  await expect(floatingSidebar(page)).toHaveCount(0);
  await expect(page).toHaveURL(firstChat);

  await openSidebarButton(page).click();
  await floatingNav(page)
    .getByRole("button", { name: /^New chat/ })
    .click();
  await expect(floatingSidebar(page)).toHaveCount(0);
  await expect(page.locator("main h1")).toContainText("Happy");

  await openSidebarButton(page).click();
  await floatingNav(page)
    .getByRole("button", { name: /^Search chats/ })
    .click();
  await expect(floatingSidebar(page)).toHaveCount(0);
  await expect(page.getByRole("dialog")).toBeVisible();
});

test("at 800px the floating sidebar works by keyboard, with its menu and dialogs on top", async ({
  page,
}) => {
  await page.setViewportSize({ width: 800, height: 800 });
  await page.goto("/");
  await send(page, "keyboard floating chat");
  await page.goto("/");

  await openSidebarButton(page).focus();
  await page.keyboard.press("Enter");
  await expect(floatingSidebar(page)).toBeFocused();

  // The chat menu opens above the sidebar; Escape closes the menu, not the sidebar.
  const chat = floatingNav(page)
    .locator("div", { hasText: "keyboard floating chat" })
    .last();
  await chat.hover();
  await chat.getByTitle("Chat options").focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("menuitem", { name: "Rename" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("menu")).toHaveCount(0);
  await expect(floatingSidebar(page)).toBeVisible();

  // Rename: Escape cancels the rename box and leaves the sidebar open. (Choosing
  // Rename with the mouse doesn't focus the box, in the docked sidebar too, so
  // click into it first.)
  await chat.getByTitle("Chat options").click();
  await page.getByRole("menuitem", { name: "Rename" }).click();
  await page.getByLabel("Chat title").click();
  await page.keyboard.press("Escape");
  await expect(page.getByLabel("Chat title")).toHaveCount(0);
  await expect(floatingSidebar(page)).toBeVisible();

  // Delete: the dialog is on top (its button can be clicked) and Escape closes
  // the dialog first.
  await chat.getByTitle("Chat options").click();
  await page.getByRole("menuitem", { name: "Delete" }).click();
  await expect(
    page.getByRole("alertdialog").or(page.getByRole("dialog")),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("alertdialog")).toHaveCount(0);
  await expect(floatingSidebar(page)).toBeVisible();
  await chat.getByTitle("Chat options").click();
  await page.getByRole("menuitem", { name: "Delete" }).click();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(floatingSidebar(page)).toBeVisible();
});
