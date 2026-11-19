import { expect, test, type Page } from "@playwright/test";

// A real 1x1 pixel PNG.
const PNG_BASE64 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";
const png = (name = "screenshot.png") => ({
  name,
  mimeType: "image/png",
  buffer: Buffer.from(PNG_BASE64, "base64"),
});

const messageBox = (page: Page) => page.getByLabel("Message");
const attachInput = (page: Page) => page.getByLabel("Attach files or images");

/** Makes the browser create a file, as if it came from the clipboard or desktop. */
const newDataTransfer = (page: Page) =>
  page.evaluateHandle((base64) => {
    const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
    const transfer = new DataTransfer();
    transfer.items.add(new File([bytes], "dropped.png", { type: "image/png" }));
    return transfer;
  }, PNG_BASE64);

test("an attached image shows a preview, is sent, and survives a refresh", async ({
  page,
}) => {
  await page.goto("/");

  await attachInput(page).setInputFiles(png());
  await expect(page.getByRole("img", { name: "screenshot.png" })).toBeVisible();
  await messageBox(page).fill("What is in this picture?");
  await messageBox(page).press("Enter");

  await expect(page.getByText("I can see 1 image(s).")).toBeVisible();
  const sent = page.getByRole("img", { name: "Attached" });
  await expect(sent).toBeVisible();
  // Previews are cleared once the message is sent.
  await expect(page.getByRole("img", { name: "screenshot.png" })).toHaveCount(
    0,
  );

  await page.reload();
  const reopened = page.getByRole("img", { name: "Attached" });
  await expect(reopened).toBeVisible();
  // The image really loads from the server, not just a broken placeholder.
  await expect
    .poll(() => reopened.evaluate((img: HTMLImageElement) => img.naturalWidth))
    .toBeGreaterThan(0);
});

test("an image can be sent with no text", async ({ page }) => {
  await page.goto("/");

  await attachInput(page).setInputFiles(png());
  await page.getByTitle("Send").click();

  await expect(page.getByText("I can see 1 image(s).")).toBeVisible();
});

test("editing a question keeps its image visible and attached", async ({
  page,
}) => {
  await page.goto("/");
  await attachInput(page).setInputFiles(png());
  await messageBox(page).fill("Question with image");
  await messageBox(page).press("Enter");
  await expect(page.getByText("I can see 1 image(s).")).toBeVisible();
  const question = page
    .getByText("Question with image", { exact: true })
    .last();
  await question.hover();
  await page.getByRole("button", { name: "Edit latest question" }).click();
  await expect(page.getByRole("img", { name: "Attached" })).toBeVisible();
  await page
    .getByLabel("Edit your latest question")
    .fill("Corrected image question");
  await page.getByRole("button", { name: "Save & resend" }).click();
  await expect(page.getByText("I can see 1 image(s).")).toBeVisible();
  await expect(page.getByRole("img", { name: "Attached" })).toBeVisible();
  await expect(
    page.getByText("Corrected image question", { exact: true }),
  ).toBeVisible();
});

test("a pasted screenshot is attached", async ({ page }) => {
  await page.goto("/");
  await expect(messageBox(page)).toBeVisible();

  // Playwright can't build a paste event with a file, so make one by hand.
  await messageBox(page).evaluate((box, base64) => {
    const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
    const clipboardData = new DataTransfer();
    clipboardData.items.add(
      new File([bytes], "dropped.png", { type: "image/png" }),
    );
    box.dispatchEvent(
      new ClipboardEvent("paste", {
        clipboardData,
        bubbles: true,
        cancelable: true,
      }),
    );
  }, PNG_BASE64);

  await expect(page.getByRole("img", { name: "dropped.png" })).toBeVisible();
  await expect(messageBox(page)).toHaveValue("");
});

test("an image dragged onto the chat is attached", async ({ page }) => {
  await page.goto("/");
  const transfer = await newDataTransfer(page);

  await messageBox(page).dispatchEvent("dragenter", { dataTransfer: transfer });
  const cover = page.getByText("Drop files to attach");
  await expect(cover).toBeVisible();
  await cover.dispatchEvent("drop", { dataTransfer: transfer });

  await expect(page.getByRole("img", { name: "dropped.png" })).toBeVisible();
  await expect(cover).toHaveCount(0);
});

test("a preview can be removed before sending", async ({ page }) => {
  await page.goto("/");
  await attachInput(page).setInputFiles([png("one.png"), png("two.png")]);

  await page.getByTitle("Remove one.png").click();

  await expect(page.getByRole("img", { name: "one.png" })).toHaveCount(0);
  await expect(page.getByRole("img", { name: "two.png" })).toBeVisible();
});

test("files that aren't images, or are too many, are refused with a message", async ({
  page,
}) => {
  await page.goto("/");

  await attachInput(page).setInputFiles({
    name: "notes.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("not an image"),
  });
  await expect(page.getByRole("alert")).toContainText(
    "notes.txt isn't a supported file type",
  );

  // The e2e server allows 5 images per message (see askmynotes/e2e_setup.py).
  await attachInput(page).setInputFiles(
    Array.from({ length: 6 }, (_, i) => png(`image-${i}.png`)),
  );
  await expect(page.getByRole("alert")).toContainText("up to 5 images");
  await expect(page.getByRole("img", { name: /^image-\d\.png$/ })).toHaveCount(
    5,
  );
});
