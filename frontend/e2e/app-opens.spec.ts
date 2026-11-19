import { expect, test } from "@playwright/test";

test("the app opens on a new chat with the greeting", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: /^Happy \w+day, Matt$/ }),
  ).toBeVisible();
  await expect(page.getByLabel("Message")).toBeVisible();
});
