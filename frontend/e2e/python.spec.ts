import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

// The test server's fake model runs "Python" for a message containing "python"
// (when the Python button is on): one run that prints 100.5, an answer pointing
// to a chart (amounts.png) and a CSV (summary.csv). "slow" slows the answer;
// "bigfile", "manyfiles" and "svgfile" point to files the limits or the safety
// rules refuse; "longoutput" prints 250 lines; "pyfail" loses the connection.
// A fake sandbox stands in for OpenAI's, so nothing is paid for. The test prices
// make each sandbox cost $20.00 (see e2e_setup.py).
const documentsDir = join(process.env.E2E_DATA_DIR ?? "", "documents");

const pythonButton = (page: Page) =>
  page.getByRole("button", { name: "Python", exact: true });

async function askWithPython(page: Page, text: string) {
  await page.goto("/");
  await pythonButton(page).click();
  await page.getByLabel("Message").fill(text);
  await page.getByLabel("Message").press("Enter");
  await expect(page).toHaveURL(/\/chat\//);
}

test("the Python button toggles by click and by keyboard, and switches off after sending", async ({
  page,
}) => {
  await page.goto("/");
  const button = pythonButton(page);
  await expect(button).toHaveAttribute("aria-pressed", "false");

  await button.click();
  await expect(button).toHaveAttribute("aria-pressed", "true");
  await button.click();
  await expect(button).toHaveAttribute("aria-pressed", "false");

  // By keyboard: focus it, then Space, then Enter.
  await button.focus();
  await page.keyboard.press("Space");
  await expect(button).toHaveAttribute("aria-pressed", "true");
  await page.keyboard.press("Enter");
  await expect(button).toHaveAttribute("aria-pressed", "false");

  await page.keyboard.press("Space");
  await page.getByLabel("Message").fill("python once");
  await page.getByLabel("Message").press("Enter");
  await expect(page.getByText("Working (1)")).toBeVisible();
  await expect(pythonButton(page)).toHaveAttribute("aria-pressed", "false");
});

test("a message sent with the button off runs no Python", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Message").fill("python but not switched on");
  await page.getByLabel("Message").press("Enter");

  // The fake model answers as if it had run Python, but with the button off the
  // app offered it nothing, so no run, no panel and no files are kept.
  await expect(page.getByText("The average amount was 100.5.")).toBeVisible();
  await expect(page.getByText("Working (")).toHaveCount(0);
  await expect(page.getByRole("img", { name: "amounts.png" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: /\(1 KB\)/ })).toHaveCount(0);
});

test("Running Python… shows while it works, then the answer, code and output", async ({
  page,
}) => {
  await askWithPython(page, "slow python run");

  await expect(page.getByText("Running Python…")).toBeVisible();
  await expect(page.getByText("The average amount was 100.5.")).toBeVisible();
  await expect(page.getByText("Running Python…")).toHaveCount(0);

  // The links to files inside the sandbox are gone from the answer.
  await expect(page.getByRole("link", { name: /summary\.csv/ })).toHaveCount(1);
  await expect(page.getByText("sandbox:")).toHaveCount(0);

  await page.getByText("Working (1)").click();
  const panel = page.locator("details", { hasText: "Working (1)" });
  await expect(panel.locator("code.language-python")).toContainText(
    'pd.read_excel("/mnt/data/figures.xlsx")',
  );
  await expect(panel.locator(".hljs-keyword").first()).toBeVisible();
  await expect(panel.getByText("Output", { exact: true })).toBeVisible();
  await expect(panel.locator("pre", { hasText: /^100\.5$/ })).toBeVisible();
  await expect(
    panel.getByRole("button", { name: "Copy python code" }),
  ).toBeVisible();
});

test("a generated chart shows under the answer and opens full size", async ({
  page,
}) => {
  await askWithPython(page, "python chart");

  const picture = page.getByRole("img", { name: "amounts.png" });
  await expect(picture).toBeVisible();
  expect(
    await picture.evaluate((image: HTMLImageElement) => image.naturalWidth),
  ).toBe(240);

  await page
    .getByRole("button", { name: "Open amounts.png full size" })
    .click();
  const viewer = page.getByRole("dialog", { name: "amounts.png" });
  await expect(viewer).toBeVisible();
  await expect(viewer.getByRole("img", { name: "amounts.png" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(viewer).toHaveCount(0);
  // Focus returns to the picture, so the keyboard carries on from there.
  await expect(
    page.getByRole("button", { name: "Open amounts.png full size" }),
  ).toBeFocused();
});

test("a CSV chip downloads the file", async ({ page }) => {
  await askWithPython(page, "python table");

  const chip = page.getByRole("link", { name: /^Download summary\.csv/ });
  await expect(chip).toBeVisible();
  await expect(chip).toContainText("1 KB");

  const downloading = page.waitForEvent("download");
  await chip.click();
  const download = await downloading;

  expect(download.suggestedFilename()).toBe("summary.csv");
  const path = await download.path();
  expect(readFileSync(path, "utf-8").split("\r\n").join("\n")).toBe(
    "Year,Amount\n2024,100.5\n",
  );
});

test("a download chip can be reached and used by keyboard", async ({
  page,
}) => {
  await askWithPython(page, "python keys");
  const chip = page.getByRole("link", { name: /^Download summary\.csv/ });
  await expect(chip).toBeVisible();

  await chip.focus();
  const downloading = page.waitForEvent("download");
  await page.keyboard.press("Enter");

  expect((await downloading).suggestedFilename()).toBe("summary.csv");
});

test("an SVG file is only a download, never shown", async ({ page }) => {
  await askWithPython(page, "python svgfile");

  await expect(
    page.getByRole("link", { name: /^Download figure\.svg/ }),
  ).toBeVisible();
  await expect(page.getByRole("img", { name: "figure.svg" })).toHaveCount(0);
});

test("files over the size or number limits are left out, with a note", async ({
  page,
}) => {
  await askWithPython(page, "python bigfile");
  await expect(
    page.getByText("big.csv was left out: it is larger than 1 MB."),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: /summary\.csv/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /big\.csv/ })).toHaveCount(0);

  await page.goto("/");
  await pythonButton(page).click();
  await page.getByLabel("Message").fill("python manyfiles");
  await page.getByLabel("Message").press("Enter");
  await expect(
    page.getByText(
      "three.csv was left out: a reply can include at most 2 files.",
    ),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: /one\.csv/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /three\.csv/ })).toHaveCount(0);
});

test("long output is cut, with a note", async ({ page }) => {
  await askWithPython(page, "python longoutput");

  await page.getByText("Working (1)").click();
  await expect(
    page.getByText("Only the first 200 lines of the output are shown."),
  ).toBeVisible();
  const output = page.locator("pre", { hasText: "line 200" });
  await expect(output).toBeVisible();
  await expect(output).not.toContainText("line 201");
});

test("a Python run that failed on the way keeps its code and offers Retry", async ({
  page,
}) => {
  await askWithPython(page, "python pyfail");

  await expect(page.getByText("The reply didn't come through")).toBeVisible();
  await expect(page.getByText("The average is")).toBeVisible();
  await page.getByText("Working (1)").click();
  await expect(page.locator("code.language-python")).toBeVisible();

  // Retry repeats the question, with Python still on for it.
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByText("The reply didn't come through")).toBeVisible();
  await expect(page.getByText("Working (1)")).toBeVisible();
});

test("Stop while Python works keeps what it had run", async ({ page }) => {
  await askWithPython(page, "slow python stop");
  await expect(page.getByText("Running Python…")).toBeVisible();

  await page.getByTitle("Stop").click();

  await expect(page.getByText("Stopped", { exact: true })).toBeVisible();
  await expect(page.getByText("Working (1)")).toBeVisible();
  // Nothing is left running: the next message works as usual.
  await expect(page.getByTitle("Stop")).toHaveCount(0);
});

test("regenerating repeats Python, and the chat reopens with its files", async ({
  page,
}) => {
  await askWithPython(page, "python again");
  await expect(page.getByRole("img", { name: "amounts.png" })).toBeVisible();

  await page.getByTitle("Regenerate").click();
  await expect(page.getByText("Working (1)")).toBeVisible();
  await expect(page.getByRole("img", { name: "amounts.png" })).toHaveCount(1);
  await expect(page.getByRole("link", { name: /summary\.csv/ })).toHaveCount(1);

  await page.reload();
  await expect(page.getByRole("img", { name: "amounts.png" })).toBeVisible();
  await expect(page.getByRole("link", { name: /summary\.csv/ })).toBeVisible();
  await expect(page.getByText("Working (1)")).toBeVisible();
});

test("an attached Excel file goes with the question", async ({ page }) => {
  await page.goto("/");
  await page
    .getByLabel("Attach files or images")
    .setInputFiles(join(documentsDir, "figures.xlsx"));
  await pythonButton(page).click();
  await page.getByLabel("Message").fill("python on my spreadsheet");
  await page.getByLabel("Message").press("Enter");

  await expect(page.getByTitle("figures.xlsx", { exact: true })).toContainText(
    "2 sheets",
  );
  await expect(page.getByText("The average amount was 100.5.")).toBeVisible();
  await expect(page.getByRole("img", { name: "amounts.png" })).toBeVisible();
});

test("the chat's cost shows the Python sandbox", async ({ page }) => {
  await askWithPython(page, "python cost");
  await expect(page.getByText("Working (1)")).toBeVisible();

  const cost = page.getByRole("button", { name: /^API cost of this chat/ });
  await cost.focus();

  // The reply and title ($0.066) and one $20.00 sandbox.
  await expect(page.getByText("Python $20.00")).toBeVisible();
  await expect(cost).toContainText("$20.07");
});

test("the page doesn't scroll sideways for long code and output", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1024, height: 800 });
  await askWithPython(page, "python longoutput");
  await page.getByText("Working (1)").click();
  await expect(page.locator("code.language-python")).toBeVisible();

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});
