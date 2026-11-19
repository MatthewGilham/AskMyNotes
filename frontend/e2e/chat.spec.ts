import { expect, test, type Page } from "@playwright/test";

const messageBox = (page: Page) => page.getByLabel("Message");

async function startChat(page: Page, text: string) {
  await page.goto("/");
  await messageBox(page).fill(text);
  await messageBox(page).press("Enter");
}

test("sending a message streams the reply into the conversation", async ({
  page,
}) => {
  await startChat(page, "Explain EPS");

  await expect(page.getByText("You said: Explain EPS")).toBeVisible();
  // The fake reply has a table, a fraction and a dollar amount.
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.locator(".katex .mfrac")).toBeVisible();
  await expect(page.getByText("$5 is five dollars")).toBeVisible();
  await expect(page).toHaveURL(/\/chat\/[0-9a-f]{32}$/);
});

test("Shift+Enter adds a new line instead of sending", async ({ page }) => {
  await page.goto("/");
  await messageBox(page).fill("first line");
  await messageBox(page).press("Shift+Enter");
  await messageBox(page).pressSequentially("second line");

  await expect(messageBox(page)).toHaveValue("first line\nsecond line");
  await expect(page).toHaveURL(/\/$/);
});

test("a failed reply shows a plain amber error and keeps my message", async ({
  page,
}) => {
  await startChat(page, "please fail now");

  const error = page.getByRole("alert");
  await expect(error).toContainText("Couldn't reach OpenAI");
  await expect(error).not.toContainText("APIConnectionError");
  // The text is also the chat's title, so the bubble is the last match.
  await expect(page.getByText("please fail now").last()).toBeVisible();
  await expect(error.getByRole("button", { name: "Retry" })).toBeVisible();

  // The error is saved too, so it is still there after a refresh.
  await page.reload();
  await expect(page.getByRole("alert")).toContainText("Couldn't reach OpenAI");
});

test("stopping a reply keeps what was written, marked as stopped", async ({
  page,
}) => {
  await startChat(page, "slow reply please");
  await expect(page.getByText("You said: slow reply")).toBeVisible();

  await page.getByTitle("Stop").click();

  await expect(page.getByText("Stopped", { exact: true })).toBeVisible();
  await expect(page.getByText("You said: slow reply please")).toBeVisible();
  await page.reload();
  await expect(page.getByText("Stopped", { exact: true })).toBeVisible();
  await expect(page.getByText("You said: slow reply please")).toBeVisible();
});

test("regenerating replaces the latest reply", async ({ page }) => {
  await startChat(page, "regenerate me");
  await expect(page.getByText("You said: regenerate me")).toBeVisible();

  await page.getByText("You said: regenerate me").hover();
  await page.getByTitle("Regenerate").click();

  await expect(page.getByText("You said: regenerate me")).toHaveCount(1);
  await expect(page.getByTitle("Regenerate")).toBeAttached();
  await page.reload();
  await expect(page.getByText("You said: regenerate me")).toHaveCount(1);
});

test("copy puts the reply's Markdown on the clipboard", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await startChat(page, "copy this");
  await expect(page.getByText("You said: copy this")).toBeVisible();

  await page.getByText("You said: copy this").hover();
  await page.getByTitle("Copy").click();

  const copied = await page.evaluate(() => navigator.clipboard.readText());
  expect(copied).toContain("You said: copy this");
  expect(copied).toContain("| A | B |");
});

test("editing the latest question replaces its answer and survives refresh", async ({
  page,
}) => {
  await startChat(page, "First question");
  await expect(page.getByText("You said: First question")).toBeVisible();
  await messageBox(page).fill("Latest question");
  await messageBox(page).press("Enter");
  await expect(page.getByText("You said: Latest question")).toBeVisible();
  const replacedAnswerId = await page
    .getByText("You said: Latest question")
    .evaluate((element) =>
      element.closest("[id^='message-']")?.id.replace("message-", ""),
    );
  const chatId = new URL(page.url()).pathname.split("/").at(-1);
  await expect(
    page.getByRole("button", { name: "Edit latest question" }),
  ).toHaveCount(1);

  await page.getByText("Latest question", { exact: true }).hover();
  await page.getByRole("button", { name: "Edit latest question" }).click();
  const editor = page.getByLabel("Edit your latest question");
  await editor.fill("Corrected latest question");
  await editor.press("Enter");
  await expect(editor).toHaveValue("Corrected latest question\n");
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(
    page.getByText("Latest question", { exact: true }),
  ).toBeVisible();

  await page.getByText("Latest question", { exact: true }).hover();
  await page.getByRole("button", { name: "Edit latest question" }).click();
  await page
    .getByLabel("Edit your latest question")
    .fill("Corrected latest question");
  await page.getByRole("button", { name: "Save & resend" }).click();

  await expect(
    page.getByText("You said: Corrected latest question"),
  ).toBeVisible();
  await expect(page.getByText("You said: Latest question")).toHaveCount(0);
  await page.getByRole("button", { name: "Questions" }).click();
  await expect(
    page.getByRole("menuitem", { name: /Corrected latest question/ }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await page.goto(`/chat/${chatId}#message-${replacedAnswerId}`);
  await expect(
    page.getByText("This message is no longer available in this chat."),
  ).toBeVisible();
  await page.goto(`/chat/${chatId}`);
  await expect(
    page
      .locator('[id^="message-"]')
      .filter({ hasText: "First question" })
      .first()
      .getByText("First question", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("Corrected latest question", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("You said: Corrected latest question"),
  ).toBeVisible();
});

test("a stale edit keeps the correction in its editor", async ({ page }) => {
  await startChat(page, "Original question");
  await expect(page.getByText("You said: Original question")).toBeVisible();
  const question = page
    .locator('[id^="message-"]')
    .filter({ hasText: "Original question" })
    .first()
    .getByText("Original question", { exact: true });
  const messageId = await question.evaluate((element) =>
    element.closest("[id^='message-']")?.id.replace("message-", ""),
  );
  const chatId = new URL(page.url()).pathname.split("/").at(-1);
  await question.hover();
  await page.getByRole("button", { name: "Edit latest question" }).click();
  const editor = page.getByLabel("Edit your latest question");
  await editor.fill("My correction stays here");

  const competingEdit = await page.evaluate(
    async ({ chatId, messageId }) => {
      const response = await fetch(
        `/api/chats/${chatId}/messages/${messageId}/edit`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text: "Changed in another tab",
            expectedLatestMessageId: Number(messageId),
            expectedOriginalText: "Original question",
          }),
        },
      );
      await response.text();
      return response.status;
    },
    { chatId, messageId },
  );
  expect(competingEdit).toBe(200);
  await page.getByRole("button", { name: "Save & resend" }).click();
  await expect(editor).toHaveValue("My correction stays here");
  await expect(page.getByRole("alert")).toContainText("not saved");
});

test("stopping an edited reply saves the replacement and releases the chat", async ({
  page,
}) => {
  await startChat(page, "Original before stop");
  await expect(page.getByText("You said: Original before stop")).toBeVisible();
  await page.getByText("Original before stop", { exact: true }).last().hover();
  await page.getByRole("button", { name: "Edit latest question" }).click();
  await page
    .getByLabel("Edit your latest question")
    .fill("slow replacement reply");
  await page.getByRole("button", { name: "Save & resend" }).click();
  await expect(
    page.getByText("You said: slow replacement reply"),
  ).toBeVisible();
  await expect(page.getByTitle("Stop")).toBeVisible();
  await page.getByTitle("Stop").click();
  await expect(page.getByText("Stopped", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByText("Stopped", { exact: true })).toBeVisible();

  await page.getByText("slow replacement reply", { exact: true }).hover();
  await page.getByRole("button", { name: "Edit latest question" }).click();
  await expect(page.getByLabel("Edit your latest question")).toBeVisible();
});

test("a failed edited reply offers Retry for the corrected question", async ({
  page,
}) => {
  await startChat(page, "Question before correction");
  await expect(
    page.getByText("You said: Question before correction"),
  ).toBeVisible();
  await page
    .getByText("Question before correction", { exact: true })
    .last()
    .hover();
  await page.getByRole("button", { name: "Edit latest question" }).click();
  await page
    .getByLabel("Edit your latest question")
    .fill("please fail after edit");
  await page.getByRole("button", { name: "Save & resend" }).click();
  await expect(page.getByRole("alert")).toContainText("Couldn't reach OpenAI");
  await expect(
    page.getByText("please fail after edit", { exact: true }),
  ).toBeVisible();
  const retry = page.getByRole("button", { name: "Retry" });
  await expect(retry).toBeVisible();
  await retry.click();
  await expect(page.getByRole("alert")).toContainText("Couldn't reach OpenAI");
  await expect(
    page.getByText("please fail after edit", { exact: true }),
  ).toHaveCount(1);
});

test("leaving a chat cancels an unsaved edit", async ({ page }) => {
  await startChat(page, "Saved question before navigation");
  await expect(
    page.getByText("You said: Saved question before navigation"),
  ).toBeVisible();
  await page
    .getByText("Saved question before navigation", { exact: true })
    .last()
    .hover();
  await page.getByRole("button", { name: "Edit latest question" }).click();
  await page.getByLabel("Edit your latest question").fill("Unsaved correction");
  await page.getByRole("button", { name: /^New chat/ }).click();
  await expect(page.getByRole("heading", { name: /^Happy/ })).toBeVisible();
  await page
    .getByRole("button", { name: "Saved question before navigation" })
    .click();
  await expect(
    page.getByText("Saved question before navigation", { exact: true }).last(),
  ).toBeVisible();
  await expect(page.getByText("Unsaved correction")).toHaveCount(0);
  await expect(page.getByLabel("Edit your latest question")).toHaveCount(0);
});
