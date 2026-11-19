// Navigation uses made-up long chats, with stable targets and image-only questions.
import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/chats/navigation", (route) =>
    route.fulfill({
      json: {
        id: "navigation",
        title: "Navigation example",
        pinned: false,
        lastUsedAt: new Date().toISOString(),
        messages: Array.from({ length: 40 }, (_, i) => ({
          id: i + 1,
          role: i % 2 === 0 ? "user" : "assistant",
          content:
            i === 2
              ? ""
              : `Question or explanation ${i + 1} ` +
                "Study material. ".repeat(30),
          images: [],
          status: "complete",
          sources: null,
          error: null,
        })),
      },
    }),
  );
});

test("message links survive refresh, history and missing targets", async ({
  page,
}) => {
  await page.goto("/chat/navigation#message-1");
  await expect(page.locator("#message-1")).toBeFocused();
  await page.reload();
  await expect(page.locator("#message-1")).toBeFocused();
  await page.getByRole("button", { name: "Questions", exact: true }).click();
  await page.getByRole("menuitem", { name: "2. Image question" }).click();
  await expect(page.locator("#message-3")).toBeFocused();
  await page.goBack();
  await expect(page.locator("#message-1")).toBeFocused();
  await page.goForward();
  await expect(page.locator("#message-3")).toBeFocused();
  await page.goto("/chat/navigation#message-999");
  await expect(
    page.getByRole("status").filter({ hasText: "no longer available" }),
  ).toBeVisible();
});

test("jump to latest and keyboard question navigation", async ({ page }) => {
  await page.goto("/chat/navigation");
  await expect(page.locator("#message-40")).toBeInViewport();
  await page.locator("#message-1").evaluate((el) => el.scrollIntoView());
  const latest = page.getByRole("button", { name: "Jump to latest" });
  await expect(latest).toBeVisible();
  await latest.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#message-40")).toBeInViewport();
  await expect(latest).toBeHidden();
  const questions = page.getByRole("button", {
    name: "Questions",
    exact: true,
  });
  await questions.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("menuitem")).toHaveCount(20);
  await page.keyboard.press("Escape");
  await expect(questions).toBeFocused();
});

test("search opens its exact message and title matches have no target", async ({
  page,
}) => {
  await page.route("**/api/chats/search?*", (route) =>
    route.fulfill({
      json: [
        {
          chatId: "navigation",
          title: "Target result",
          snippet: "matching phrase",
          messageId: 1,
        },
        {
          chatId: "navigation",
          title: "Title result",
          snippet: "title",
          messageId: null,
        },
      ],
    }),
  );
  await page.goto("/");
  await page.getByRole("button", { name: /^Search chats/ }).click();
  await page.getByRole("textbox", { name: "Search chats" }).fill("matching");
  await page.getByRole("button", { name: /Target result/ }).click();
  await expect(page.locator("#message-1")).toBeFocused();
  await page.getByRole("button", { name: /^Search chats/ }).click();
  await page.getByRole("textbox", { name: "Search chats" }).fill("title");
  await page.getByRole("button", { name: /Title result/ }).click();
  await expect(page).toHaveURL(/navigation$/);
});

test("reading earlier messages during streaming preserves position and same-chat jumps keep running", async ({
  page,
}) => {
  const response = await page.request.post("/api/chats/send", {
    data: { text: "Long introduction " + "Study content. ".repeat(200) },
  });
  const events = (await response.text())
    .trim()
    .split("\n")
    .map((line) => JSON.parse(line));
  const id = events[0].chat.id;
  await page.goto(`/chat/${id}`);
  await page.getByLabel("Message").fill("slow reply please");
  await page.getByLabel("Message").press("Enter");
  await expect(page.getByTitle("Stop")).toBeVisible();
  await page.getByRole("button", { name: "Questions", exact: true }).click();
  await page.getByRole("menuitem").first().click();
  await expect(page.getByTitle("Stop")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Jump to latest" }),
  ).toBeVisible();
  await page.getByTitle("Stop").click();
  await expect(page.getByText("Stopped", { exact: true })).toBeVisible();
  await page.getByLabel("Message").fill("slow second question");
  await page.getByLabel("Message").press("Enter");
  await expect(page.getByTitle("Stop")).toBeVisible();
  await page.getByRole("button", { name: /^New chat/ }).click();
  await expect(page.getByRole("heading", { name: /^Happy/ })).toBeVisible();
  await expect(page.getByLabel("Message")).toHaveValue("");
  await expect(page.getByText("Stopped", { exact: true })).toHaveCount(0);
});

test("layout follows resized content at desktop widths and reduced motion", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  // Each width starts like a first visit: the browser remembers a closed
  // sidebar (phase 34), and this test closes it at each width.
  await page.addInitScript(() =>
    localStorage.removeItem("askmynotes-appearance"),
  );
  for (const width of [1280, 1600]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/chat/navigation");
    await expect(page.locator("#message-40")).toBeInViewport();
    await page.locator("#message-39").evaluate((el) => {
      const image = document.createElement("div");
      image.style.height = "500px";
      el.append(image);
    });
    await expect(page.locator("#message-40")).toBeInViewport();
    await page.getByTitle("Close sidebar").click();
    await page.getByRole("button", { name: "Questions", exact: true }).click();
    await expect(page.getByRole("menuitem").first()).toBeVisible();
    await page.screenshot({ path: `../data/navigation-${width}.png` });
    await page.keyboard.press("Escape");
  }
});
