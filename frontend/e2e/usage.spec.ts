import { expect, test, type Page } from "@playwright/test";

// The test server's fake model reports the same usage for every call, and the
// test prices make one call cost $0.033 (see e2e_setup.py). A new chat's reply
// and its title are two calls: $0.066. The test budget is 300 tokens.
const chatCost = (page: Page) =>
  page.getByRole("button", { name: /^API cost of this chat/ });
const contextRing = (page: Page) =>
  page.getByRole("button", { name: /^Context used/ });
const totalCost = (page: Page) =>
  page.getByRole("button", { name: /^API cost of everything/ });

async function sendMessage(page: Page, text: string) {
  await page.getByLabel("Message").fill(text);
  await page.getByLabel("Message").press("Enter");
  await expect(page.getByTitle("Send")).toBeVisible();
}

async function startChat(page: Page, text: string) {
  await page.goto("/");
  await sendMessage(page, text);
  await expect(page).toHaveURL(/\/chat\//);
}

test("a chat shows its cost and context, with the detail on hover and focus", async ({
  page,
}) => {
  await startChat(page, "usage readout check");

  await expect(chatCost(page)).toHaveText("$0.066");
  await chatCost(page).hover();
  await expect(page.getByRole("tooltip")).toContainText("$0.066 for this chat");
  await expect(page.getByRole("tooltip")).toContainText("Replies $0.033");
  await expect(page.getByRole("tooltip")).toContainText("Titles $0.033");

  // The same detail by keyboard, and the context detail.
  await page.mouse.move(0, 0);
  await contextRing(page).focus();
  await expect(page.getByRole("tooltip")).toContainText("of 300 tokens");
  await expect(page.getByRole("tooltip")).toContainText(
    "Instructions and notes search results aren't counted.",
  );
  await expect(page.getByRole("tooltip")).not.toContainText("summarise");
});

test("a new chat shows neither chat readout", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: /^Happy/ })).toBeVisible();
  await expect(chatCost(page)).toHaveCount(0);
  await expect(contextRing(page)).toHaveCount(0);
});

test("a notes answer adds its two calls and the search to the chat's cost", async ({
  page,
}) => {
  await startChat(page, "what do my notes say");

  // Two calls for the answer, one for the title, and the search query's
  // embedding ($0.101).
  await expect(chatCost(page)).toHaveText("$0.101");
  await chatCost(page).hover();
  await expect(page.getByRole("tooltip")).toContainText("Replies $0.066");
  await expect(page.getByRole("tooltip")).toContainText("Titles $0.033");
  await expect(page.getByRole("tooltip")).toContainText("Searches $0.001");
});

test("the sidebar total grows with every reply and keeps deleted chats", async ({
  page,
}) => {
  await startChat(page, "usage total check");
  const before = await totalCost(page).innerText();
  await sendMessage(page, "one more question");
  await expect(totalCost(page)).not.toHaveText(before);
  const afterReply = await totalCost(page).innerText();

  await totalCost(page).hover();
  await expect(page.getByRole("tooltip")).toContainText("Notes updates $0.003");
  await page.mouse.move(0, 0);

  // Delete the chat from the sidebar.
  const row = page
    .getByRole("button", { name: "usage total check", exact: true })
    .locator("..");
  await row.hover();
  await row.getByTitle("Chat options").click();
  await page.getByRole("menuitem", { name: "Delete" }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Delete" })
    .click();
  await expect(row).toHaveCount(0);

  await expect(totalCost(page)).toHaveText(afterReply);
  await totalCost(page).hover();
  await expect(page.getByRole("tooltip")).not.toContainText(
    "Deleted chats $0.000",
  );
  await expect(page.getByRole("tooltip")).toContainText("Deleted chats");
});

test("stopping a reply shows the cost as an estimate", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Message").fill("slow usage check");
  await page.getByLabel("Message").press("Enter");
  await expect(page.getByText("You said: slow usage")).toBeVisible();

  await page.getByTitle("Stop").click();
  await expect(page.getByText("Stopped", { exact: true })).toBeVisible();

  await expect(chatCost(page)).toBeVisible();
  await chatCost(page).hover();
  await expect(page.getByRole("tooltip")).toContainText("Includes an estimate");
});

test("a chat over the budget turns the ring amber and warns of a summary", async ({
  page,
}) => {
  await startChat(page, "one huge message " + "words ".repeat(250));

  await contextRing(page).focus();
  await expect(page.getByRole("tooltip")).toContainText(
    "The next message will summarise the older messages.",
  );
  await expect(contextRing(page).locator("circle").nth(1)).toHaveCSS(
    "stroke",
    "rgb(245, 158, 11)",
  );
});

test("once older messages are summarised the tooltip says so", async ({
  page,
}) => {
  await startChat(page, "summary one " + "words ".repeat(40));
  await sendMessage(page, "summary two " + "words ".repeat(40));
  await sendMessage(page, "summary three " + "words ".repeat(40));
  await sendMessage(page, "summary four " + "words ".repeat(40));

  await contextRing(page).focus();
  await expect(page.getByRole("tooltip")).toContainText(
    "Older messages have been summarised.",
  );
});

test("the cost and context readouts survive a reload", async ({ page }) => {
  await startChat(page, "usage reload check");
  await expect(chatCost(page)).toHaveText("$0.066");

  await page.reload();

  await expect(chatCost(page)).toHaveText("$0.066");
  await expect(contextRing(page)).toBeVisible();
  await expect(totalCost(page)).toBeVisible();
});

test("regenerating and editing a question each add a reply to the cost", async ({
  page,
}) => {
  await startChat(page, "usage regenerate check");
  await expect(chatCost(page)).toHaveText("$0.066");

  await page.getByTitle("Regenerate").click();
  // A third call: $0.0996.
  await expect(chatCost(page)).toHaveText("$0.100");

  await page.getByRole("button", { name: "Edit latest question" }).click();
  await page.getByLabel("Edit your latest question").fill("edited question");
  await page.getByRole("button", { name: "Save & resend" }).click();
  // A fourth call: $0.1328.
  await expect(chatCost(page)).toHaveText("$0.133");
});

test("the readouts can be reached and read by keyboard", async ({ page }) => {
  await startChat(page, "usage keyboard check");
  await expect(chatCost(page)).toHaveText("$0.066");

  await chatCost(page).focus();
  await expect(page.getByRole("tooltip")).toContainText("for this chat");
  await page.keyboard.press("Tab");
  await expect(contextRing(page)).toBeFocused();
  await expect(page.getByRole("tooltip")).toContainText("tokens");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Questions" })).toBeFocused();
  // Hidden tooltips aren't matched, so none is showing now.
  await expect(page.getByRole("tooltip")).toHaveCount(0);
});
