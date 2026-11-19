import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

// Made-up documents written by askmynotes/e2e_setup.py before the server starts.
const documentsDir = join(process.env.E2E_DATA_DIR ?? "", "documents");
const file = (name: string) => join(documentsDir, name);

const messageBox = (page: Page) => page.getByLabel("Message");
const attachInput = (page: Page) => page.getByLabel("Attach files or images");

test("an attached document shows as a chip, is read, sent and survives a refresh", async ({
  page,
}) => {
  await page.goto("/");

  await attachInput(page).setInputFiles(file("essay.docx"));
  await expect(page.getByText("essay.docx")).toBeVisible();
  await messageBox(page).fill("Summarise my essay");
  await messageBox(page).press("Enter");

  // The fake model echoes what it was sent, so this proves it received the text.
  await expect(
    page.getByText("Goodwill is an intangible asset.").first(),
  ).toBeVisible();
  // The sent message keeps a chip, with no remove button, and the composer's is gone.
  const chip = page.getByTitle("essay.docx", { exact: true });
  await expect(chip).toHaveCount(1);
  await expect(chip).toContainText("Word document");
  await expect(page.getByLabel("Remove essay.docx")).toHaveCount(0);

  await page.reload();
  await expect(page.getByTitle("essay.docx", { exact: true })).toContainText(
    "Word document",
  );
  await expect(page.getByTitle("essay.docx", { exact: true })).toHaveCount(1);
});

test("a spreadsheet and a pdf show their sheet and page counts", async ({
  page,
}) => {
  await page.goto("/");

  await attachInput(page).setInputFiles([
    file("figures.xlsx"),
    file("lecture.pdf"),
  ]);
  await page.getByTitle("Send").click();

  await expect(page.getByTitle("figures.xlsx", { exact: true })).toContainText(
    "2 sheets",
  );
  await expect(page.getByTitle("lecture.pdf", { exact: true })).toContainText(
    "1 page",
  );
});

test("a document can be removed before sending, and sent with no text", async ({
  page,
}) => {
  await page.goto("/");
  await attachInput(page).setInputFiles([
    file("essay.docx"),
    file("lecture.pdf"),
  ]);

  await page.getByLabel("Remove essay.docx").click();
  await expect(page.getByTitle("essay.docx", { exact: true })).toHaveCount(0);
  await page.getByTitle("Send").click();

  await expect(page.getByTitle("lecture.pdf", { exact: true })).toContainText(
    "1 page",
  );
  await expect(
    page.getByText("Depreciation spreads the cost.").first(),
  ).toBeVisible();
});

test("a document dragged onto the chat is attached", async ({ page }) => {
  await page.goto("/");
  const bytes = readFileSync(file("essay.docx")).toString("base64");
  const transfer = await page.evaluateHandle((base64) => {
    const data = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(new File([data], "dropped.docx"));
    return dataTransfer;
  }, bytes);

  await messageBox(page).dispatchEvent("dragenter", { dataTransfer: transfer });
  const cover = page.getByText("Drop files to attach");
  await expect(cover).toBeVisible();
  await cover.dispatchEvent("drop", { dataTransfer: transfer });

  await expect(page.getByTitle("dropped.docx", { exact: true })).toBeVisible();
});

test("a document with too much text is refused and the draft and file are kept", async ({
  page,
}) => {
  await page.goto("/");
  await attachInput(page).setInputFiles(file("long.docx"));
  await messageBox(page).fill("Read this");

  await messageBox(page).press("Enter");

  await expect(page.getByRole("alert")).toContainText(
    "more than the 100 allowed",
  );
  await expect(messageBox(page)).toHaveValue("Read this");
  await expect(page.getByTitle("long.docx", { exact: true })).toBeVisible();
});

test("unsupported files and too many documents are refused with a message", async ({
  page,
}) => {
  await page.goto("/");

  await attachInput(page).setInputFiles({
    name: "program.exe",
    mimeType: "application/octet-stream",
    buffer: Buffer.from("MZ"),
  });
  await expect(page.getByRole("alert")).toContainText(
    "program.exe isn't a supported file type",
  );

  // The e2e server allows 5 documents per message (see askmynotes/e2e_setup.py).
  await attachInput(page).setInputFiles(
    Array.from({ length: 6 }, (_, i) => ({
      name: `copy-${i}.pdf`,
      mimeType: "application/pdf",
      buffer: readFileSync(file("lecture.pdf")),
    })),
  );
  await expect(page.getByRole("alert")).toContainText("up to 5 documents");
  await expect(page.getByTitle(/^copy-\d\.pdf$/)).toHaveCount(5);
});

test("the Questions menu names a document-only question by its file", async ({
  page,
}) => {
  await page.goto("/");
  await attachInput(page).setInputFiles(file("lecture.pdf"));
  await page.getByTitle("Send").click();
  await expect(page.getByTitle("lecture.pdf", { exact: true })).toContainText(
    "1 page",
  );

  await page.getByRole("button", { name: "Questions" }).click();

  await expect(
    page.getByRole("menuitem", { name: "1. lecture.pdf" }),
  ).toBeVisible();
});

test("editing a question keeps its document attached", async ({ page }) => {
  await page.goto("/");
  await attachInput(page).setInputFiles(file("essay.docx"));
  await messageBox(page).fill("First wording");
  await messageBox(page).press("Enter");
  await expect(page.getByTitle("essay.docx", { exact: true })).toContainText(
    "Word document",
  );

  await page.getByRole("button", { name: /Edit/ }).first().click();
  await page.getByLabel("Edit your latest question").fill("Second wording");
  await page.getByRole("button", { name: "Save & resend" }).click();

  await expect(
    page.getByText("You said: Attached document").first(),
  ).toBeVisible();
  await expect(page.getByTitle("essay.docx", { exact: true })).toHaveCount(1);
  await expect(page.getByText(/Second wording/).first()).toBeVisible();
});
