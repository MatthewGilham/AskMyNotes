import { expect, test, type Page } from "@playwright/test";

// The test server's fake model answers a message containing "calc" by calling
// the real calculator twice (1000 * (1 + 0.05)^2, then solving 1100 = 1000 *
// (1 + r) for r) and then answering. "wrong" first asks for 1 / 0, which is
// refused. "slow" makes the answer slow, so "Calculating…" can be seen.

async function startChat(page: Page, text: string) {
  await page.goto("/");
  await page.getByLabel("Message").fill(text);
  await page.getByLabel("Message").press("Enter");
  await expect(page).toHaveURL(/\/chat\//);
}

test("a calculation shows its working, drawn as maths, in a collapsed panel", async ({
  page,
}) => {
  await startChat(page, "calc please");

  await expect(
    page.getByText("After two years it is worth 1102.5"),
  ).toBeVisible();
  const panel = page.getByText("Working (2)");
  await expect(panel).toBeVisible();
  // Collapsed: no maths on screen yet.
  await expect(page.locator("details .katex").first()).toBeHidden();

  await panel.click();

  const working = page.locator("details", { hasText: "Working (2)" });
  await expect(working.locator(".katex")).not.toHaveCount(0);
  // The first calculation, as written maths, and its result.
  await expect(working.locator("li").first()).toContainText("1000");
  await expect(working.locator("li").first()).toContainText("1102.5");
  await expect(working.locator("li").nth(1)).toContainText("r");
  await expect(working.locator("li").nth(1)).toContainText("0.1");
  // It is the working, not a notes or web source.
  await expect(page.getByText(/^Sources \(/)).toHaveCount(0);
  await expect(page.getByText("Beyond your notes")).toHaveCount(0);
});

test("a reply says it is calculating while it does", async ({ page }) => {
  await startChat(page, "slow calc question");

  await expect(page.getByText("Calculating…")).toBeVisible();
  await expect(page.getByText("After two years").first()).toBeVisible();
  await expect(page.getByText("Calculating…")).toBeHidden();
  await page.getByTitle("Stop").click();
});

test("stopping during a calculation keeps the reply, marked as stopped", async ({
  page,
}) => {
  await startChat(page, "slow calc stop");
  await expect(page.getByText("Calculating…")).toBeVisible();

  await page.getByTitle("Stop").click();

  await expect(page.getByText("Stopped", { exact: true })).toBeVisible();
  await expect(page.getByText("Calculating…")).toBeHidden();
  await page.reload();
  await expect(page.getByText("Stopped", { exact: true })).toBeVisible();
  await expect(page.getByText("Working (2)")).toBeVisible();
});

test("a refused calculation is listed with its reason and the reply carries on", async ({
  page,
}) => {
  await startChat(page, "calc wrong");

  await expect(
    page.getByText("After two years it is worth 1102.5"),
  ).toBeVisible();
  await page.getByText("Working (3)").click();
  const working = page.locator("details", { hasText: "Working (3)" });
  await expect(working.getByText("Refused: Division by zero.")).toBeVisible();
  await expect(working.locator("li")).toHaveCount(3);
});

test("the working comes back when the chat is reopened", async ({ page }) => {
  await startChat(page, "calc reopen");
  await expect(page.getByText("Working (2)")).toBeVisible();

  await page.reload();

  await page.getByText("Working (2)").click();
  await expect(
    page.locator("details", { hasText: "Working (2)" }).locator("li"),
  ).toHaveCount(2);
});

test("regenerating and editing replace the working", async ({ page }) => {
  await startChat(page, "calc regenerate");
  await expect(page.getByText("Working (2)")).toBeVisible();

  await page.getByTitle("Regenerate").click();
  await expect(page.getByText("Working (2)")).toHaveCount(1);

  await page.getByText("calc regenerate", { exact: true }).last().hover();
  await page.getByRole("button", { name: "Edit latest question" }).click();
  await page.getByLabel("Edit your latest question").fill("a plain question");
  await page.getByRole("button", { name: "Save & resend" }).click();
  await expect(page.getByText("You said: a plain question")).toBeVisible();
  await expect(page.getByText(/^Working \(/)).toHaveCount(0);
});

test("the panel opens and closes by keyboard", async ({ page }) => {
  await startChat(page, "calc keyboard");
  const summary = page.getByText("Working (2)");
  await expect(summary).toBeVisible();

  await summary.focus();
  await page.keyboard.press("Enter");
  const working = page.locator("details", { hasText: "Working (2)" });
  await expect(working.locator("li").first()).toBeVisible();

  await page.keyboard.press("Enter");
  await expect(working.locator("li").first()).toBeHidden();
});
