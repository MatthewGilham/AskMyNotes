import { expect, test, type Page } from "@playwright/test";

// The test server's fake model answers a message containing "web" after two web
// searches, with a "From the web" block citing two pages (see fake_model.py).
// The searches also read five pages: the two cited, written differently, and
// three the answer doesn't cite.
// "mixed" also searches the notes and adds a "Beyond your notes" block.
// "slow" waits 0.6 seconds before each word, so the searching status shows.
// "slowsearch" makes each search take 1.5 seconds; "intro" writes a sentence
// before the searches; "uncited" and "nopages" answer without citing anything;
// "calc" searches once, calculates, and links its page in plain Markdown.

async function startChat(page: Page, text: string) {
  await page.goto("/");
  await page.getByLabel("Message").fill(text);
  await page.getByLabel("Message").press("Enter");
  await expect(page).toHaveURL(/\/chat\//);
}

const pill = (page: Page, site: string) =>
  page.getByRole("link", { name: site, exact: true });

const PANEL = "Found online (2 cited, 3 searched)";

test("a web reply shows the blue block, citation pills and Found online", async ({
  page,
}) => {
  await startChat(page, "what is the rate on the web");

  await expect(page.getByText("From the web", { exact: true })).toBeVisible();
  await expect(page.getByText("The rate is 3.75%")).toBeVisible();
  // The pill shows the site, and opens in a new tab.
  const bank = pill(page, "example-bank.test");
  await expect(bank).toHaveAttribute(
    "href",
    "https://www.example-bank.test/rate",
  );
  await expect(bank).toHaveAttribute("target", "_blank");
  await expect(bank).toHaveAttribute("rel", "noopener noreferrer");
  await expect(pill(page, "news.example.test")).toBeVisible();

  // The panel is collapsed until it is opened.
  const panel = page.getByText(PANEL);
  await expect(panel).toBeVisible();
  await expect(page.getByText("Bank Rate | Example Bank")).toBeHidden();
  await panel.click();
  const searched = page.getByRole("region", { name: "Searched for" });
  await expect(searched.getByText("fake search 1")).toBeVisible();
  await expect(searched.getByText("fake search 2")).toBeVisible();
  const cited = page.getByRole("region", { name: "Cited in the answer" });
  const page1 = cited.getByRole("link", { name: /Bank Rate \| Example Bank/ });
  await expect(page1).toHaveAttribute(
    "href",
    "https://www.example-bank.test/rate",
  );
  await expect(page1).toHaveAttribute("target", "_blank");
  await expect(
    cited.getByRole("link", { name: /Rates explained/ }),
  ).toBeVisible();
  // The pages the search read and the answer did not cite. The two it did cite
  // are not listed a second time.
  const uncited = page.getByRole("region", { name: "Searched, not cited" });
  await expect(uncited.getByRole("link")).toHaveCount(3);
  const policy = uncited.getByRole("link", {
    name: /regulator.example.test\/policy\/statement/,
  });
  await expect(policy).toHaveAttribute("target", "_blank");
  await expect(policy).toHaveAttribute("rel", "noopener noreferrer");
  // A web answer isn't a notes answer.
  await expect(page.getByText(/^Sources \(/)).toHaveCount(0);
  await expect(page.getByText("Beyond your notes")).toHaveCount(0);
});

test("a reply says it is searching the web while it does", async ({ page }) => {
  await startChat(page, "slow web question");

  await expect(page.getByText("Searching the web…")).toBeVisible();
  // The answer carrying on means the search has finished.
  await expect(page.getByText("The rate is 3.75%").first()).toBeVisible();
  await expect(page.getByText("Searching the web…")).toBeHidden();
  await page.getByTitle("Stop").click();
});

test("Searching the web shows from the start of the search, with the globe", async ({
  page,
}) => {
  await startChat(page, "slowsearch web question");

  // Each of the two searches takes 1.5 seconds. No text has arrived yet, and the
  // status is still showing well into the second search.
  const status = page
    .getByRole("status")
    .filter({ hasText: "Searching the web…" });
  await expect(status).toBeVisible();
  await expect(status.locator("svg")).toHaveCount(1);
  await page.waitForTimeout(2200);
  await expect(status).toBeVisible();
  await expect(page.getByText("The rate is 3.75%")).toBeHidden();

  // The answer carrying on means the searches are over.
  await expect(page.getByText("The rate is 3.75%")).toBeVisible();
  await expect(status).toBeHidden();
});

test("the status shows again for a search that comes after some text", async ({
  page,
}) => {
  await startChat(page, "intro web question");

  const status = page
    .getByRole("status")
    .filter({ hasText: "Searching the web…" });
  await expect(page.getByText("Let me check that for you.")).toBeVisible();
  await expect(status).toBeVisible();
  await expect(page.getByText("The rate is 3.75%")).toBeVisible();
  await expect(status).toBeHidden();
});

test("stopping during a web reply keeps it, marked as stopped", async ({
  page,
}) => {
  await startChat(page, "slow web stop");
  await expect(page.getByText("Searching the web…")).toBeVisible();

  await page.getByTitle("Stop").click();

  await expect(page.getByText("Stopped", { exact: true })).toBeVisible();
  await expect(page.getByText("Searching the web…")).toBeHidden();
  await page.reload();
  await expect(page.getByText("Stopped", { exact: true })).toBeVisible();
});

test("stopping in the middle of a search leaves nothing searching", async ({
  page,
}) => {
  await startChat(page, "slowsearch web stop");
  await expect(page.getByText("Searching the web…")).toBeVisible();

  await page.getByTitle("Stop").click();

  await expect(page.getByText("Stopped", { exact: true })).toBeVisible();
  await expect(page.getByText("Searching the web…")).toBeHidden();
  await page.reload();
  await expect(page.getByText("Searching the web…")).toBeHidden();
  await expect(page.getByText("Stopped", { exact: true })).toBeVisible();
});

test("one answer can mix notes, the web and outside knowledge", async ({
  page,
}) => {
  await startChat(page, "mixed web question");

  await expect(page.getByText("Your notes say depreciation")).toBeVisible();
  await expect(page.getByText("From the web", { exact: true })).toBeVisible();
  await expect(page.getByText("Beyond your notes")).toBeVisible();
  await expect(page.getByText("Sources (1)")).toBeVisible();
  await expect(page.getByText(PANEL)).toBeVisible();
  // Each kind sits where it belongs.
  const web = page.locator("aside", { hasText: "From the web" });
  await expect(web.getByText("The rate is 3.75%")).toBeVisible();
  await expect(web.getByText("reducing-balance")).toHaveCount(0);
  const beyond = page.locator("aside", { hasText: "Beyond your notes" });
  await expect(beyond.getByText("reducing-balance")).toBeVisible();
});

test("a web reply comes back when the chat is reopened", async ({ page }) => {
  await startChat(page, "reopen the web answer");
  await expect(page.getByText(PANEL)).toBeVisible();

  await page.reload();

  await expect(page.getByText("From the web", { exact: true })).toBeVisible();
  await expect(pill(page, "news.example.test")).toBeVisible();
  await expect(page.getByText(PANEL)).toBeVisible();
  await page.getByText(PANEL).click();
  await expect(page.getByText("fake search 2")).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Searched, not cited" }),
  ).toBeVisible();
});

test("regenerating and editing replace the web answer", async ({ page }) => {
  await startChat(page, "regenerate the web answer");
  await expect(page.getByText(PANEL)).toBeVisible();

  await page.getByTitle("Regenerate").click();
  await expect(page.getByText(PANEL)).toBeVisible();
  await expect(page.getByText(PANEL)).toHaveCount(1);

  await page
    .getByText("regenerate the web answer", { exact: true })
    .last()
    .hover();
  await page.getByRole("button", { name: "Edit latest question" }).click();
  await page.getByLabel("Edit your latest question").fill("a plain question");
  await page.getByRole("button", { name: "Save & resend" }).click();
  await expect(page.getByText("You said: a plain question")).toBeVisible();
  await expect(page.getByText("Found online")).toHaveCount(0);
  await expect(page.getByText("From the web", { exact: true })).toHaveCount(0);
});

test("a reply that searched the web and then failed shows the error and Retry", async ({
  page,
}) => {
  await startChat(page, "web search then fail");

  const error = page.getByRole("alert");
  await expect(error).toContainText("Couldn't reach OpenAI");
  await expect(error.getByRole("button", { name: "Retry" })).toBeVisible();
  await expect(page.getByText("Searching the web…")).toBeHidden();
  // The search it made before failing is kept.
  await expect(
    page.getByText("Found online (0 cited, 0 searched)"),
  ).toBeVisible();
  // The error and the text before it are saved.
  await page.reload();
  await expect(page.getByRole("alert")).toContainText("Couldn't reach OpenAI");
  await expect(page.getByText("The rate is")).toBeVisible();
});

test("the pills and the Found online panel work by keyboard", async ({
  page,
}) => {
  await startChat(page, "keyboard web answer");
  await expect(page.getByText(PANEL)).toBeVisible();

  const bank = pill(page, "example-bank.test");
  await bank.focus();
  await expect(bank).toBeFocused();

  const summary = page.getByText(PANEL);
  await summary.focus();
  await expect(summary).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("link", { name: /Rates explained/ }),
  ).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: /Bank Rate \| Example Bank/ }),
  ).toBeFocused();
});

test("the panel appears when pages were read but none were cited", async ({
  page,
}) => {
  await startChat(page, "web rate, uncited");

  const panel = page.getByText("Found online (0 cited, 5 searched)");
  await expect(panel).toBeVisible();
  await panel.click();
  await expect(
    page.getByRole("region", { name: "Cited in the answer" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("region", { name: "Searched, not cited" }).getByRole("link"),
  ).toHaveCount(5);
});

test("the panel appears with a note when a search returned no pages", async ({
  page,
}) => {
  await startChat(page, "search the web, nopages please");

  const panel = page.getByText("Found online (0 cited, 0 searched)");
  await expect(panel).toBeVisible();
  await panel.click();
  await expect(page.getByText("fake search 1")).toBeVisible();
  await expect(page.getByText("No pages were returned.")).toBeVisible();
});

test("a search and a calculation together show both panels", async ({
  page,
}) => {
  await startChat(page, "web rate then calc the interest");

  await expect(page.getByText("From the web", { exact: true })).toBeVisible();
  await expect(page.getByText("So 18 months of simple interest")).toBeVisible();
  // The page was linked in the text only, with no citation from OpenAI.
  const panel = page.getByText("Found online (1 cited, 4 searched)");
  await expect(panel).toBeVisible();
  await expect(page.getByText("Working (1)")).toBeVisible();
  await panel.click();
  await expect(
    page
      .getByRole("region", { name: "Cited in the answer" })
      .getByRole("link", { name: /example-bank.test/ }),
  ).toHaveAttribute("href", "https://www.example-bank.test/rate");
  // Both panels come back when the chat is reopened.
  await page.reload();
  await expect(
    page.getByText("Found online (1 cited, 4 searched)"),
  ).toBeVisible();
  await expect(page.getByText("Working (1)")).toBeVisible();
});

test("an answer saved before the panel shows only its cited count", async ({
  page,
}) => {
  await startChat(page, "web question to age");
  await expect(page.getByText(PANEL)).toBeVisible();
  // Show the chat as the app saved it before phase 26: only the cited pages,
  // with no flag, and no record of what was searched.
  await page.route(/\/api\/chats\/[0-9a-f]+$/, async (route) => {
    const response = await route.fetch();
    const chat = await response.json();
    for (const message of chat.messages) {
      if (message.webSources) {
        message.webSources = message.webSources
          .filter((source: { cited: boolean }) => source.cited)
          .map(({ title, site, url }: Record<string, string>) => ({
            title,
            site,
            url,
          }));
        delete message.webSearches;
      }
    }
    await route.fulfill({ response, json: chat });
  });

  await page.reload();

  const panel = page.getByText("Found online (2 cited)");
  await expect(panel).toBeVisible();
  await panel.click();
  await expect(page.getByText("Searched for")).toHaveCount(0);
  await expect(page.getByText("Searched, not cited")).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: /Rates explained/ }),
  ).toBeVisible();
});

test("the cost readout counts web searches", async ({ page }) => {
  await startChat(page, "cost of a web answer");
  await expect(page.getByText(PANEL)).toBeVisible();

  // The test price is $10 a search: two searches, plus a reply and a title.
  const cost = page.getByRole("button", { name: /^API cost of this chat/ });
  await expect(cost).toHaveText("$20.07");
  await cost.hover();
  await expect(page.getByRole("tooltip")).toContainText("Web searches $20.00");
});
