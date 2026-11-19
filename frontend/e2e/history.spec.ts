import { expect, test, type Locator, type Page } from "@playwright/test";

// The fake model titles a chat with the first five words of its first message.
async function startChat(page: Page, text: string) {
  await page.goto("/");
  await page.getByLabel("Message").fill(text);
  await page.getByLabel("Message").press("Enter");
  await expect(page.getByText(`You said: ${text}`)).toBeVisible();
  // The address follows the text a moment later; later steps rely on it.
  await expect(page).toHaveURL(/\/chat\//);
}

const sidebarChat = (page: Page, title: string) =>
  page.getByRole("button", { name: title, exact: true });

async function openChatMenu(page: Page, title: string): Promise<Locator> {
  const row = sidebarChat(page, title).locator("..");
  await row.hover();
  await row.getByTitle("Chat options").click();
  return page.getByRole("menu");
}

test("a chat can be reopened from the sidebar with its messages", async ({
  page,
}) => {
  await startChat(page, "reopen alpha unique");
  await startChat(page, "reopen beta unique");

  await sidebarChat(page, "reopen alpha unique").click();

  await expect(page.getByText("You said: reopen alpha unique")).toBeVisible();
  await expect(page.getByText("You said: reopen beta unique")).toHaveCount(0);
  await expect(page).toHaveURL(/\/chat\/[0-9a-f]{32}$/);
});

test("a new chat appears under Today with a model-written title", async ({
  page,
}) => {
  await startChat(page, "today group check one two three");

  // The fake model's title is the first five words of the message.
  const title = "today group check one two";
  await expect(sidebarChat(page, title)).toBeVisible();
  const today = page.getByRole("heading", { name: "Today", exact: true });
  await expect(today).toBeVisible();
  await expect(page.getByRole("main").getByRole("heading")).toHaveText(title);
});

test("a chat can be pinned, renamed and unpinned from its menu", async ({
  page,
}) => {
  await startChat(page, "pin rename check one");
  const title = "pin rename check one";

  await (
    await openChatMenu(page, title)
  )
    .getByRole("menuitem", { name: "Pin", exact: true })
    .click();
  await expect(page.getByRole("heading", { name: "Pinned" })).toBeVisible();

  await (
    await openChatMenu(page, title)
  )
    .getByRole("menuitem", { name: "Rename" })
    .click();
  await page.getByLabel("Chat title").fill("A renamed chat");
  await page.getByLabel("Chat title").press("Enter");
  await expect(sidebarChat(page, "A renamed chat")).toBeVisible();

  await (
    await openChatMenu(page, "A renamed chat")
  )
    .getByRole("menuitem", { name: "Unpin" })
    .click();
  await expect(page.getByRole("heading", { name: "Pinned" })).toHaveCount(0);
});

test("deleting a chat asks first, then removes it for good", async ({
  page,
}) => {
  await startChat(page, "delete check two three");
  const title = "delete check two three";

  await (
    await openChatMenu(page, title)
  )
    .getByRole("menuitem", { name: "Delete" })
    .click();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(sidebarChat(page, title)).toBeVisible();

  await (
    await openChatMenu(page, title)
  )
    .getByRole("menuitem", { name: "Delete" })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Delete" })
    .click();

  await expect(sidebarChat(page, title)).toHaveCount(0);
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: /^Happy/ })).toBeVisible();
});

test("Ctrl+K finds a chat by a word that appears only in a message", async ({
  page,
}) => {
  // The word is the sixth, so it's in the message but not in the title.
  await startChat(page, "search check one two zxqwordzxq");
  await page.goto("/");
  // Shortcuts only work once the app has started, so wait for it.
  await expect(page.getByLabel("Message")).toBeVisible();

  await page.keyboard.press("Control+k");
  await page.getByRole("textbox", { name: "Search chats" }).fill("zxqword");

  const result = page.getByRole("dialog").getByRole("button", {
    name: /search check one two/,
  });
  await expect(result).toBeVisible();
  await result.click();
  await expect(
    page.getByText("You said: search check one two zxqwordzxq"),
  ).toBeVisible();
});

test("Ctrl+Shift+O starts a new chat", async ({ page }) => {
  await startChat(page, "shortcut check one two");

  await page.keyboard.press("Control+Shift+O");

  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: /^Happy/ })).toBeVisible();
});

test("opening the app shows a new, empty chat even when chats exist", async ({
  page,
}) => {
  await startChat(page, "empty open check one");

  await page.goto("/");

  await expect(page.getByRole("heading", { name: /^Happy/ })).toBeVisible();
  await expect(page.getByLabel("Message")).toHaveValue("");
});

test("an unsent new chat is not saved", async ({ page }) => {
  await page.goto("/");
  const before = await page.request.get("/api/chats");
  const countBefore = (await before.json()).length;

  await page.getByRole("button", { name: /New chat/ }).click();
  await page.keyboard.press("Control+Shift+O");

  const after = await page.request.get("/api/chats");
  expect((await after.json()).length).toBe(countBefore);
});

test("the sidebar groups chats by when they were last used, pinned first", async ({
  page,
}) => {
  // Chats of every age, as the server would list them.
  const daysAgo = (days: number) =>
    new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();
  // Noon yesterday is yesterday's date at any time of day, unlike "1.5 days
  // ago", which is the day before yesterday when the test runs before noon.
  const noonYesterday = new Date();
  noonYesterday.setDate(noonYesterday.getDate() - 1);
  noonYesterday.setHours(12, 0, 0, 0);
  const yesterdayDaysAgo = (Date.now() - noonYesterday.getTime()) / 86_400_000;
  const chat = (id: string, title: string, days: number, pinned = false) => ({
    id,
    title,
    pinned,
    createdAt: daysAgo(days),
    lastUsedAt: daysAgo(days),
  });
  await page.route("**/api/chats", (route) =>
    route.request().method() === "GET"
      ? route.fulfill({
          json: [
            chat("a", "Pinned old chat", 90, true),
            chat("b", "Used today", 0),
            chat("c", "Used yesterday", yesterdayDaysAgo),
            chat("d", "Used last week", 4),
            chat("e", "Used last month", 20),
            chat("f", "Used long ago", 60),
          ],
        })
      : route.continue(),
  );

  await page.goto("/");

  const headings = page.locator("h2");
  await expect(headings).toHaveText([
    "Pinned",
    "Today",
    "Yesterday",
    "Last 7 days",
    "Last 30 days",
    "Older",
  ]);
  const group = (label: string) =>
    page.locator("section", {
      has: page.getByRole("heading", { name: label }),
    });
  await expect(group("Pinned")).toContainText("Pinned old chat");
  await expect(group("Today")).toContainText("Used today");
  await expect(group("Yesterday")).toContainText("Used yesterday");
  await expect(group("Last 7 days")).toContainText("Used last week");
  await expect(group("Last 30 days")).toContainText("Used last month");
  await expect(group("Older")).toContainText("Used long ago");
});

test("the shortcut hints show ⌘ on a Mac and Ctrl otherwise", async ({
  browser,
  baseURL,
}) => {
  const macUserAgent =
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36";
  const mac = await browser.newContext({
    baseURL,
    userAgent: macUserAgent,
  });
  const macPage = await mac.newPage();
  await macPage.goto("/");
  await expect(macPage.getByText("⌘ ⇧ O")).toBeVisible();
  await expect(macPage.getByText("⌘ K")).toBeVisible();
  // The shortcut itself works with ⌘ too.
  await macPage.keyboard.press("Meta+K");
  await expect(macPage.getByRole("dialog")).toBeVisible();
  await mac.close();

  const windows = await browser.newContext({
    baseURL,
  });
  const windowsPage = await windows.newPage();
  await windowsPage.goto("/");
  await expect(windowsPage.getByText("Ctrl ⇧ O")).toBeVisible();
  await expect(windowsPage.getByText("Ctrl K")).toBeVisible();
  await windows.close();
});
