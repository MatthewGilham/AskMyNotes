// Citation cleanup across arbitrary stream boundaries and real browser journeys.
import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import { withoutCitationMarkers } from "../src/chat/citationMarkers";

const marker = "\ue200cite\ue202turn0search0\ue201";
const examples: [string, string][] = JSON.parse(
  readFileSync("../backend/tests/fixtures/citation_markers.json", "utf8"),
);

test("shared cleanup examples and every stream boundary", () => {
  for (const [raw, clean] of examples) {
    expect(withoutCitationMarkers(raw)).toBe(clean);
    expect(withoutCitationMarkers(clean)).toBe(clean);
  }
  for (let split = 1; split <= marker.length; split++) {
    expect(withoutCitationMarkers("Before " + marker.slice(0, split))).toBe(
      "Before ",
    );
    expect(
      withoutCitationMarkers(
        "Before " + marker.slice(0, split) + marker.slice(split) + "after",
      ),
    ).toBe("Before after");
  }
  expect(withoutCitationMarkers("A\ue200cit ordinary")).toBe(
    "A\ue200cit ordinary",
  );
});

async function start(page: Page, prompt: string) {
  await page.goto("/");
  // Watch rendered reply mutations, so a marker flashing between assertions
  // cannot pass simply because the saved answer was cleaned later.
  await page.evaluate(() => {
    const seen: string[] = [];
    (window as unknown as { citationLeaks: string[] }).citationLeaks = seen;
    new MutationObserver(() => {
      for (const answer of document.querySelectorAll(
        '[class*="reply"] [class*="markdown"]',
      )) {
        const text = answer.textContent ?? "";
        if (text.includes("\ue200") || text.includes("turn0search"))
          seen.push(text);
      }
    }).observe(document.body, {
      subtree: true,
      childList: true,
      characterData: true,
    });
  });
  await page.getByLabel("Message", { exact: true }).fill(prompt);
  await page.getByTitle("Send", { exact: true }).click();
  await expect(page.getByTitle("Stop", { exact: true })).toBeVisible();
}

async function noLeaks(page: Page) {
  expect(
    await page.evaluate(
      () => (window as unknown as { citationLeaks: string[] }).citationLeaks,
    ),
  ).toEqual([]);
}

test("split markers never render; copy, selection and reopening use clean text", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await start(page, "citationcheck");
  await expect(page.getByTitle("Stop", { exact: true })).toBeHidden();
  const answer = page.locator("[data-quote-answer]").last();
  await expect(answer).toHaveText("Before after.");
  await noLeaks(page);
  await expect(page.getByText(/Found online/)).toHaveCount(0);
  await answer.hover();
  await page.getByTitle("Copy", { exact: true }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(
    "Before after.",
  );
  await page.reload();
  await expect(answer).toHaveText("Before after.");
  await answer.focus();
  await page.keyboard.press("Control+a");
  await page
    .getByRole("button", { name: "Ask about this", exact: true })
    .click();
  await page
    .getByLabel("Message", { exact: true })
    .fill("Explain the selected sentence");
  await page.getByTitle("Send", { exact: true }).click();
  await expect(page.getByTitle("Stop", { exact: true })).toBeHidden();
  await page.reload();
  await expect(
    page.getByRole("link", { name: "Original answer" }),
  ).toBeVisible();
  const saved = await (
    await page.request.get(
      new URL(page.url()).pathname.replace("/chat/", "/api/chats/"),
    )
  ).json();
  expect(saved.messages.at(-2).quotedContext.excerpt).toBe("Before after.");
});

test("Stop inside a marker saves clean partial text and can regenerate", async ({
  page,
}) => {
  await start(page, "citationcheck");
  await expect(page.getByText("Before", { exact: true })).toBeVisible();
  // At 0.12 seconds per character this lands inside the citation opening.
  await page.waitForTimeout(600);
  await page.getByTitle("Stop", { exact: true }).click();
  await expect(page.getByText("Stopped", { exact: true })).toBeVisible();
  await noLeaks(page);
  await page.reload();
  await expect(page.locator("[data-quote-answer]").last()).toHaveText("Before");
  await page.getByTitle("Regenerate", { exact: true }).click();
  await expect(page.getByTitle("Stop", { exact: true })).toBeHidden();
  await expect(page.locator("[data-quote-answer]").last()).toHaveText(
    "Before after.",
  );
});

test("failure inside a marker leaves clean prose and Retry works", async ({
  page,
}) => {
  await start(page, "citationcheck partial fail");
  await expect(
    page.getByRole("button", { name: "Retry", exact: true }),
  ).toBeVisible();
  await noLeaks(page);
  await page.reload();
  await expect(page.getByText("Before", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByTitle("Stop", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Retry", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Before", { exact: true })).toBeVisible();
});
