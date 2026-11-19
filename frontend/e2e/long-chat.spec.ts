import { expect, test } from "@playwright/test";

// The test server sends the model at most about 300 tokens (around 1,200
// characters) of a chat, so a few long messages push it into summarising.
test("a long chat keeps getting replies and shows every message", async ({
  page,
}) => {
  await page.goto("/");
  const box = page.getByLabel("Message");
  const questions = [1, 2, 3, 4, 5].map(
    (n) => `long chat question ${n} ` + "words ".repeat(40),
  );

  for (const [index, question] of questions.entries()) {
    await box.fill(question);
    await box.press("Enter");
    // Wait for this reply to finish before sending the next message.
    await expect(page.getByText("You said: long chat question")).toHaveCount(
      index + 1,
    );
    await expect(page.getByTitle("Send")).toBeVisible();
  }

  // Every message, including the oldest, is still on screen.
  for (const n of [1, 2, 3, 4, 5]) {
    await expect(
      page.getByText(`long chat question ${n} words`, { exact: false }),
    ).not.toHaveCount(0);
  }
  await page.reload();
  await expect(page.getByText("You said: long chat question 1")).toBeVisible();
  await expect(page.getByText("You said: long chat question 5")).toBeVisible();
});
