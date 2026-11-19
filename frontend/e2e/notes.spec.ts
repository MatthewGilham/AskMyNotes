import { expect, test } from "@playwright/test";

// The test server's notes are one made-up PDF (see askmynotes/e2e_setup.py).

test("the notes status shows the notes are up to date", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText("Notes up to date · 1 file")).toBeVisible();
  await expect(page.getByLabel("Message")).toBeEnabled();
});

test("Refresh notes checks again and stays up to date", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Notes up to date · 1 file")).toBeVisible();

  await page.getByTitle("Refresh notes").click();

  // Nothing changed, so it ends up exactly where it was.
  await expect(page.getByText("Notes up to date · 1 file")).toBeVisible();
  const status = await (await page.request.get("/api/notes/status")).json();
  expect([status.new, status.changed, status.deleted]).toEqual([0, 0, 0]);
});

test("the message box waits while the notes update", async ({ page }) => {
  // Hold the status at "updating" to see what the page does meanwhile.
  await page.route("**/api/notes/status", (route) =>
    route.fulfill({
      json: {
        updating: true,
        new: 3,
        changed: 1,
        deleted: 0,
        done: 1,
        total: 4,
        fileCount: 0,
        unreadable: [],
        inUse: [],
        error: null,
      },
    }),
  );
  await page.goto("/");

  await expect(
    page.getByText("Updating notes: 3 new, 1 changed, 0 deleted"),
  ).toBeVisible();
  await expect(page.getByLabel("Message")).toBeDisabled();
  await expect(page.getByLabel("Message")).toHaveAttribute(
    "placeholder",
    "Waiting for your notes to finish updating…",
  );
});

test("a file open in another app is named, with what to do", async ({
  page,
}) => {
  await page.route("**/api/notes/status", (route) =>
    route.fulfill({
      json: {
        updating: false,
        new: 0,
        changed: 0,
        deleted: 0,
        done: 0,
        total: 0,
        fileCount: 3,
        unreadable: [],
        inUse: ["TM/Lecture 7.pptx"],
        error: null,
      },
    }),
  );
  await page.goto("/");

  await expect(page.getByText("Notes up to date · 3 files")).toBeVisible();
  await expect(
    page.getByText(
      "Skipped because it's open in another app: TM/Lecture 7.pptx. Close it, then refresh.",
    ),
  ).toBeVisible();
  await expect(page.getByLabel("Message")).toBeEnabled();
});

test("a notes answer shows its sources, collapsed until clicked", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByText("Notes up to date · 1 file")).toBeVisible();

  // "my notes" makes the fake model search, then answer naming S1.
  await page
    .getByLabel("Message")
    .fill("What do my notes say about depreciation?");
  await page.getByLabel("Message").press("Enter");

  await expect(page.getByText("Your notes say depreciation")).toBeVisible();
  await expect(page.getByText("Beyond your notes")).toBeVisible();
  await expect(page.getByText("reducing-balance method")).toBeVisible();
  // The line naming the sources is never shown.
  await expect(page.getByText("Sources used")).toHaveCount(0);

  const sources = page.getByText("Sources (1)");
  await expect(sources).toBeVisible();
  await expect(page.getByText("Lecture 1.pdf")).toBeHidden();
  await sources.click();
  await expect(page.getByText("Lecture 1.pdf")).toBeVisible();
  await expect(page.getByText("TM", { exact: true })).toBeVisible();
  await expect(page.getByText(/^Page [12]$/)).toBeVisible();

  // Saved with the answer, so they are still there after a refresh.
  await page.reload();
  await expect(page.getByText("Sources (1)")).toBeVisible();
});
