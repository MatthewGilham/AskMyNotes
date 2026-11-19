import { expect, test, type Page } from "@playwright/test";

// The test server's fake model answers a message containing "codeblocks" with
// Python, SQL and plain code blocks, and one containing "callouts" with all four
// callout boxes, one of them inside a "Beyond your notes" block (see
// fake_model.py). "slow" streams the callouts slowly.

async function startChat(page: Page, text: string) {
  await page.goto("/");
  await page.getByLabel("Message").fill(text);
  await page.getByLabel("Message").press("Enter");
  await expect(page).toHaveURL(/\/chat\//);
}

// Windows puts line breaks on the clipboard as CR LF, so they are turned back
// into plain line feeds before comparing.
async function readClipboard(page: Page) {
  const text = await page.evaluate(() => navigator.clipboard.readText());
  return text.split("\r\n").join("\n");
}

const PYTHON =
  "def npv(rate, flows):\n    return sum(cf / (1 + rate) ** t for t, cf in enumerate(flows))";

test("code blocks are highlighted and labelled with their language", async ({
  page,
}) => {
  await startChat(page, "show me codeblocks");

  const python = page.locator("code.language-python");
  await expect(python).toBeVisible();
  await expect(python.locator(".hljs-keyword").first()).toBeVisible();
  await expect(
    page.locator("code.language-sql .hljs-keyword").first(),
  ).toBeVisible();
  // The language names sit at the top of each block; a block with none says text.
  const labels = page.locator("[class*=_language_]");
  await expect(labels).toHaveText(["python", "sql", "text"]);
  // The highlighting really is coloured (a keyword differs from plain text).
  const keyword = await python
    .locator(".hljs-keyword")
    .first()
    .evaluate((element) => getComputedStyle(element).color);
  const plain = await python.evaluate(
    (element) => getComputedStyle(element).color,
  );
  expect(keyword).not.toBe(plain);
});

test("Copy copies the code exactly, and works by keyboard", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await startChat(page, "show me codeblocks");

  const copy = page.getByRole("button", { name: "Copy python code" });
  await copy.focus();
  await expect(copy).toBeFocused();
  await page.keyboard.press("Enter");

  await expect(page.getByRole("button", { name: "Copied" })).toBeVisible();
  expect(await readClipboard(page)).toBe(PYTHON);

  // The SQL block copies its own text, and the ::: in the plain block is code.
  await page.getByRole("button", { name: "Copy text code" }).click();
  expect(await readClipboard(page)).toBe("plain text\n:::");
});

test("all four callouts show, with their labels", async ({ page }) => {
  await startChat(page, "show me callouts");

  for (const label of [
    "Key formula",
    "Exam tip",
    "Common mistake",
    "Worked example",
  ]) {
    await expect(
      page.getByRole("complementary", { name: label }).first(),
    ).toBeVisible();
  }
  const example = page.getByRole("complementary", { name: "Worked example" });
  await expect(example.locator("ol > li")).toHaveCount(3);
  // The formula is drawn as maths.
  await expect(
    page
      .getByRole("complementary", { name: "Key formula" })
      .first()
      .locator(".katex"),
  ).toBeVisible();
});

test("a callout inside Beyond your notes keeps that label", async ({
  page,
}) => {
  await startChat(page, "show me callouts");

  const beyond = page
    .locator("aside", { hasText: "Beyond your notes" })
    .first();
  await expect(
    beyond.getByText("Beyond your notes", { exact: true }),
  ).toBeVisible();
  await expect(
    beyond.getByRole("complementary", { name: "Key formula" }),
  ).toBeVisible();
  // The top-level formula is not inside it.
  await expect(
    page.getByRole("complementary", { name: "Key formula" }),
  ).toHaveCount(2);
  await expect(
    page
      .locator("aside", { hasText: "Beyond your notes" })
      .first()
      .locator("aside"),
  ).toHaveCount(1);
});

test("a reply streaming with an open callout shows it, then closes it", async ({
  page,
}) => {
  await startChat(page, "slow show me callouts");

  // The first box is open while the reply is still arriving.
  await expect(
    page.getByRole("complementary", { name: "Key formula" }).first(),
  ).toBeVisible();
  await expect(page.getByTitle("Stop")).toBeVisible();
  await expect(
    page.getByRole("complementary", { name: "Worked example" }),
  ).toHaveCount(0);

  await expect(page.getByTitle("Send")).toBeVisible({ timeout: 30_000 });
  await expect(
    page.getByRole("complementary", { name: "Worked example" }),
  ).toBeVisible();
});

test("selecting text inside a callout still offers Ask about this", async ({
  page,
}) => {
  await startChat(page, "show me callouts");
  const tip = page.getByRole("complementary", { name: "Exam tip" });
  await expect(tip).toBeVisible();

  await tip.locator("p").evaluate((element) => {
    const range = document.createRange();
    range.selectNodeContents(element);
    const selection = window.getSelection()!;
    selection.removeAllRanges();
    selection.addRange(range);
  });

  await expect(
    page.getByRole("button", { name: "Ask about this", exact: true }),
  ).toBeVisible();
});

test("copying the reply still copies it as written, markers included", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await startChat(page, "show me callouts");
  await page.getByText("Exam tip").first().hover();

  await page.getByTitle("Copy", { exact: true }).click();

  const copied = await readClipboard(page);
  expect(copied).toContain(
    ":::tip\nWrite the formula before you put numbers in.\n:::",
  );
});
