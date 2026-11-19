// Quote journeys use saved fake replies, browser ranges and real persistence.
import { expect, test, type Locator, type Page } from "@playwright/test";

async function start(page: Page, text = "A useful explanation") {
  const response = await page.request.post("/api/chats/send", {
    data: { text },
  });
  const events = (await response.text())
    .trim()
    .split("\n")
    .map((line) => JSON.parse(line));
  await page.goto(`/chat/${events[0].chat.id}`);
  const answer = page.locator("[data-quote-answer]").last();
  await expect(answer).toBeVisible();
  return {
    answer,
    chatId: events[0].chat.id,
    sourceId: events.at(-1).message.id,
  };
}

async function select(locator: Locator, partial = false) {
  await locator.evaluate((element, partial) => {
    const range = document.createRange();
    if (partial) {
      const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
      let node = walker.nextNode();
      while (node && !node.textContent?.trim()) node = walker.nextNode();
      range.setStart(node!, 0);
      range.setEnd(node!, 1);
    } else range.selectNodeContents(element);
    const selection = window.getSelection()!;
    selection.removeAllRanges();
    selection.addRange(range);
  }, partial);
}

async function attach(page: Page, locator: Locator, partial = false) {
  await select(locator, partial);
  await page
    .getByRole("button", { name: "Ask about this", exact: true })
    .click();
  await expect(page.getByLabel("Message")).toBeFocused();
}

test("selected prose is saved separately, reopens and links to its original answer", async ({
  page,
}) => {
  const { answer, chatId, sourceId } = await start(page);
  await attach(page, answer.locator("p").first());
  await expect(page.getByText("Regarding", { exact: true })).toBeVisible();
  await page.getByLabel("Message").fill("Which part matters?");
  await page.getByTitle("Send", { exact: true }).click();
  await expect(
    page.getByRole("link", { name: "Original answer" }),
  ).toBeVisible();
  await expect(page.getByTitle("Stop")).toBeHidden();
  const saved = await (await page.request.get(`/api/chats/${chatId}`)).json();
  expect(saved.messages.at(-2).content).toBe("Which part matters?");
  expect(saved.messages.at(-2).quotedContext).toEqual({
    sourceMessageId: sourceId,
    excerpt: "You said: A useful explanation",
  });
  await page.reload();
  await page.getByRole("link", { name: "Original answer" }).click();
  await expect(page.locator(`#message-${sourceId}`)).toBeFocused();
  await expect(page.getByText("Regarding", { exact: true })).toBeVisible();
});

test("editing a quoted question keeps its excerpt and original answer link", async ({
  page,
}) => {
  const { answer, chatId, sourceId } = await start(page);
  await attach(page, answer.locator("p").first());
  await page.getByLabel("Message").fill("Follow up about this");
  await page.getByTitle("Send", { exact: true }).click();
  await expect(page.getByTitle("Stop")).toBeHidden();
  const quotedQuestion = page
    .locator('[id^="message-"]')
    .filter({ hasText: "Follow up about this" })
    .first()
    .getByText("Follow up about this", { exact: true });
  await expect(quotedQuestion).toBeVisible();
  await quotedQuestion.hover();
  await page.getByRole("button", { name: "Edit latest question" }).click();
  await page
    .getByLabel("Edit your latest question")
    .fill("Corrected follow up");
  await expect(
    page.getByRole("link", { name: "Original answer" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Save & resend" }).click();

  const corrected = page.getByText("Corrected follow up", { exact: true });
  await expect(corrected).toBeVisible();
  await expect(page.getByTitle("Stop")).toBeHidden();
  await expect(
    page.getByRole("link", { name: "Original answer" }),
  ).toHaveAttribute("href", `/chat/${chatId}#message-${sourceId}`);
  const saved = await (await page.request.get(`/api/chats/${chatId}`)).json();
  expect(saved.messages.at(-2).content).toBe("Corrected follow up");
  expect(saved.messages.at(-2).quotedContext).toEqual({
    sourceMessageId: sourceId,
    excerpt: "You said: A useful explanation",
  });
  await page.reload();
  await expect(
    page.getByText("Corrected follow up", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Original answer" }),
  ).toHaveAttribute("href", `/chat/${chatId}#message-${sourceId}`);
});

test("partial inline and display maths expand to one complete rendered expression", async ({
  page,
}) => {
  const { chatId, sourceId } = await start(
    page,
    "Formula \\[x=\\frac{a}{b}\\]",
  );
  const answer = page.locator(`#message-${sourceId} [data-quote-answer]`);
  for (const [target, latex] of [
    [answer.locator(".katex-display .katex-html"), "\\[x=\\frac{a}{b}\\]"],
    [answer.locator("p .katex-html").last(), "\\(\\frac{1}{2}\\)"],
  ] as const) {
    await attach(page, target, true);
    const preview = page.locator('[class*="box"] [class*="quote_"]');
    await expect(preview.locator(".katex")).toHaveCount(1);
    const request = page.waitForRequest(
      (request) =>
        request.url().endsWith("/api/chats/send") &&
        request.method() === "POST",
    );
    await page.getByLabel("Message").fill("Describe the terms");
    await page.getByTitle("Send", { exact: true }).click();
    expect((await request).postDataJSON().quotedContext.excerpt).toBe(latex);
    await expect(page.getByTitle("Stop")).toBeHidden();
    // Return to the original answer, avoiding the echo's additional formulas.
    await page.goto(`/chat/${chatId}`);
  }
});

test("keyboard selection, Escape, replacing and removing quotes preserve drafts", async ({
  page,
}) => {
  const { answer } = await start(page);
  await page.getByLabel("Message").fill("My existing draft");
  await answer.focus();
  await page.keyboard.press("Control+a");
  const action = page.getByRole("button", {
    name: "Ask about this",
    exact: true,
  });
  await expect(action).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(action).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(action).toBeHidden();
  await select(answer.locator("p").first());
  await page.keyboard.press("Tab");
  await expect(action).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByLabel("Message")).toHaveValue("My existing draft");
  await expect(
    page.getByRole("button", { name: "Explain this", exact: true }),
  ).toBeDisabled();
  await attach(page, answer.locator(".katex-html"), true);
  await expect(page.getByLabel("Message")).toHaveValue("My existing draft");
  await page.getByRole("button", { name: "Remove excerpt" }).click();
  await expect(page.getByLabel("Message")).toHaveValue("My existing draft");
  await expect(page.getByText("Regarding", { exact: true })).toBeHidden();
});

test("shortcuts fill only an empty input, never send, and navigation clears quotes", async ({
  page,
}) => {
  const { answer } = await start(page);
  await attach(page, answer.locator("p").first());
  await page.getByRole("button", { name: "Explain this", exact: true }).click();
  await expect(page.getByLabel("Message")).toHaveValue("Explain this");
  await expect(page.getByRole("link", { name: "Original answer" })).toHaveCount(
    0,
  );
  await expect(
    page.getByRole("button", { name: "Show an example", exact: true }),
  ).toBeDisabled();
  await page.getByLabel("Message").fill("");
  await page
    .getByRole("button", { name: "Show an example", exact: true })
    .click();
  await expect(page.getByLabel("Message")).toHaveValue("Show an example");
  await page.getByRole("button", { name: /^New chat/ }).click();
  await expect(page.getByText("Regarding", { exact: true })).toBeHidden();
  await expect(page.getByRole("heading", { name: /^Happy/ })).toBeVisible();
});

test("refused send keeps the draft and excerpt; saved model failures retry without duplicate questions", async ({
  page,
}) => {
  const { answer, chatId } = await start(page);
  await attach(page, answer.locator("p").first());
  await page.getByLabel("Message").fill("please fail now");
  await page.route("**/api/chats/send", (route) =>
    route.fulfill({
      status: 422,
      json: { detail: "Select text from a saved answer in this chat." },
    }),
  );
  await page.getByTitle("Send", { exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("saved answer");
  await expect(page.getByLabel("Message")).toHaveValue("please fail now");
  await expect(
    page.getByRole("button", { name: "Remove excerpt" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry" })).toHaveCount(0);
  await page.unroute("**/api/chats/send");
  await page.getByTitle("Send", { exact: true }).click();
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
  await expect(page.getByLabel("Message")).toHaveValue("");
  await expect(
    page.getByRole("button", { name: "Remove excerpt" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
  const saved = await (await page.request.get(`/api/chats/${chatId}`)).json();
  expect(saved.messages).toHaveLength(4);
  expect(saved.messages.at(-2).quotedContext.excerpt).toBe(
    "You said: A useful explanation",
  );
});

test("cross-message and sources selections are rejected and copying still works", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const { answer } = await start(page, "Explain my notes");
  await page.getByText("Sources (1)", { exact: true }).click();
  await answer.evaluate((element) => {
    const range = document.createRange();
    range.setStart(element.firstChild!, 0);
    range.setEndAfter(element.parentElement!.lastChild!);
    const selection = window.getSelection()!;
    selection.removeAllRanges();
    selection.addRange(range);
  });
  await expect(
    page.getByRole("button", { name: "Ask about this", exact: true }),
  ).toBeHidden();
  await answer.evaluate((element) => {
    const user = document.querySelector('[id^="message-"]')!;
    const range = document.createRange();
    range.setStart(user, 0);
    range.setEnd(element, 1);
    const selection = window.getSelection()!;
    selection.removeAllRanges();
    selection.addRange(range);
  });
  await expect(
    page.getByRole("button", { name: "Ask about this", exact: true }),
  ).toBeHidden();
  await select(answer.locator("p").first());
  await page.keyboard.press("Control+c");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toContain(
    "Your notes say depreciation",
  );
});

test("oversized excerpts are refused visibly without truncation", async ({
  page,
}) => {
  const { answer } = await start(page, "long text " + "a".repeat(8100));
  await select(answer.locator("p").first());
  await page
    .getByRole("button", { name: "Ask about this", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "select a shorter passage",
  );
  await expect(
    page.getByRole("button", { name: "Remove excerpt" }),
  ).toHaveCount(0);
});

test("streaming and failed answers are excluded; saved stopped text is eligible", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("Message").fill("slow question");
  await page.getByLabel("Message").press("Enter");
  await expect(
    page.getByText("You said: slow question", { exact: true }),
  ).toBeVisible();
  await expect(page.locator("[data-quote-answer]")).toHaveCount(0);
  await page.getByTitle("Stop").click();
  await expect(page.getByText("Stopped", { exact: true })).toBeVisible();
  await expect(page.locator("[data-quote-answer]")).toHaveCount(1);
  await attach(page, page.locator("[data-quote-answer] p").first());
  await page.getByLabel("Message").fill("fail now");
  await page.getByTitle("Send", { exact: true }).click();
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
  await expect(page.locator("[data-quote-answer]")).toHaveCount(1);
});

test("saved snapshots stay readable when their original answer is missing", async ({
  page,
}) => {
  await page.route("**/api/chats/missing-source", (route) =>
    route.fulfill({
      json: {
        id: "missing-source",
        title: "Missing original",
        pinned: false,
        lastUsedAt: new Date().toISOString(),
        messages: [
          {
            id: 200,
            role: "user",
            content: "What does this mean?",
            status: "complete",
            error: null,
            sources: null,
            images: [],
            quotedContext: {
              sourceMessageId: 199,
              excerpt: "The saved snapshot remains.",
            },
          },
        ],
      },
    }),
  );
  await page.goto("/chat/missing-source");
  await expect(page.getByText("The saved snapshot remains.")).toBeVisible();
  await page.getByRole("link", { name: "Original answer" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "no longer available" }),
  ).toBeVisible();
  await expect(page.getByText("The saved snapshot remains.")).toBeVisible();
});

test("lists retain their text and complete maths, and selections of task controls are refused", async ({
  page,
}) => {
  const { answer } = await start(
    page,
    "List\n- First \\(a=b\\)\n- Second\n\nTasks\n- [ ] A task",
  );
  await attach(page, answer.locator("ul").first());
  const preview = page.locator('[class*="box"] [class*="quote_"]');
  await expect(preview.locator("li")).toHaveCount(2);
  await expect(preview.locator(".katex")).toHaveCount(1);
  await page.getByRole("button", { name: "Remove excerpt" }).click();
  await select(answer.locator("ul").last());
  await expect(
    page.getByRole("button", { name: "Ask about this", exact: true }),
  ).toBeHidden();
});

test("a refused first question remains in the new-chat composer", async ({
  page,
}) => {
  await page.goto("/");
  await page.route("**/api/chats/send", (route) =>
    route.fulfill({
      status: 409,
      json: { detail: "Notes are updating. Try again shortly." },
    }),
  );
  await page.getByLabel("Message").fill("Keep this question");
  await page.getByTitle("Send", { exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Notes are updating");
  await expect(page.getByLabel("Message")).toHaveValue("Keep this question");
  await expect(page.getByRole("heading", { name: /^Happy/ })).toBeVisible();
});
