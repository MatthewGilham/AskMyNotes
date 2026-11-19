import { expect, test, type Page } from "@playwright/test";

// Phase 29: the foundations of the redesign. Three colour themes defined as
// tokens, fonts that ship with the app, and the moving backdrop.

const THEMES = {
  volt: {
    "--color-base": "#0c0814",
    "--color-panel": "rgba(24, 16, 38, 0.66)",
    "--color-accent": "#ccff33",
    "--color-accent-2": "#3dffc0",
    "--color-on-accent": "#121900",
  },
  aurora: {
    "--color-base": "#07090f",
    "--color-panel": "rgba(15, 17, 28, 0.68)",
    "--color-accent": "#a78bfa",
    "--color-accent-2": "#22d3ee",
    "--color-on-accent": "#0a0714",
  },
  ice: {
    "--color-base": "#08090b",
    "--color-panel": "rgba(18, 20, 25, 0.7)",
    "--color-accent": "#f2f6ff",
    "--color-accent-2": "#a9bce0",
    "--color-on-accent": "#0a0c10",
  },
};

// The values the app had before the redesign. They must never change.
const RESERVED = {
  "--color-beyond": "#fb7185",
  "--color-web": "#60a5fa",
  "--color-error": "#f59e0b",
  "--color-violet": "#8b5cf6",
  "--color-violet-bright": "#a78bfa",
  "--color-aqua": "#22d3ee",
};

/** Volt is the default theme, so it has no attribute. */
async function useTheme(page: Page, theme: string) {
  await page.evaluate((name) => {
    if (name === "volt") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", name);
  }, theme);
}

/**
 * A colour token as the browser resolves it: red, green, blue and opacity.
 * The token is painted on a throwaway element, because the built stylesheet
 * may spell the same colour differently from tokens.css.
 */
async function tokenColour(page: Page, name: string) {
  const painted = await page.evaluate((tokenName) => {
    const probe = document.createElement("div");
    probe.style.background = `var(${tokenName})`;
    document.body.append(probe);
    const colour = getComputedStyle(probe).backgroundColor;
    probe.remove();
    return colour;
  }, name);
  return channels(painted);
}

/** The numbers in "#rrggbb", "rgb(r, g, b)" or "rgba(r, g, b, a)". */
function channels(colour: string): number[] {
  if (colour.startsWith("#")) {
    const number = parseInt(colour.slice(1), 16);
    return [number >> 16, (number >> 8) & 255, number & 255, 1];
  }
  const [r, g, b, a = 1] = colour.match(/[\d.]+/g)!.map(Number);
  return [r, g, b, a];
}

/** The token is the expected colour, allowing for rounding of its opacity. */
async function expectToken(page: Page, name: string, expected: string) {
  const [r, g, b, a] = await tokenColour(page, name);
  const [red, green, blue, opacity] = channels(expected);
  expect([r, g, b], name).toEqual([red, green, blue]);
  expect(Math.abs(a - opacity), name).toBeLessThan(0.02);
}

/** "#ccff33" as the browser reports a colour: "rgb(204, 255, 51)". */
function asRgb(hex: string) {
  const number = parseInt(hex.slice(1), 16);
  return `rgb(${number >> 16}, ${(number >> 8) & 255}, ${number & 255})`;
}

async function send(page: Page, text: string) {
  await page.getByLabel("Message").fill(text);
  await page.getByLabel("Message").press("Enter");
  await expect(page.getByTitle("Regenerate")).toHaveCount(1);
}

for (const [theme, tokens] of Object.entries(THEMES)) {
  test(`the ${theme} theme has its colours`, async ({ page }) => {
    await page.goto("/");
    await useTheme(page, theme);
    for (const [name, value] of Object.entries(tokens))
      await expectToken(page, name, value);
  });

  test(`the reserved colours are unchanged in ${theme}`, async ({ page }) => {
    await page.goto("/");
    await useTheme(page, theme);
    for (const [name, value] of Object.entries(RESERVED))
      await expectToken(page, name, value);
  });

  test(`the mark takes the ${theme} accent`, async ({ page }) => {
    await page.goto("/");
    await useTheme(page, theme);
    const stops = page
      .getByRole("img", { name: "AskMyNotes" })
      .first()
      .locator("stop");
    await expect(stops.nth(0)).toHaveCSS(
      "stop-color",
      asRgb(tokens["--color-accent"]),
    );
    await expect(stops.nth(1)).toHaveCSS(
      "stop-color",
      asRgb(tokens["--color-accent-2"]),
    );
  });
}

test("the three fonts ship with the app and are used", async ({ page }) => {
  // Every request the pages make, to prove no font is fetched from elsewhere.
  const hosts = new Set<string>();
  page.on("request", (request) => hosts.add(new URL(request.url()).host));

  await page.goto("/");
  await expect(page.locator("main h1")).toHaveCSS(
    "font-family",
    /^"Bricolage Grotesque Variable"/,
  );
  await send(page, "codeblocks please");
  await send(page, "a table please");
  await page.evaluate(() => document.fonts.ready);

  for (const family of [
    "Bricolage Grotesque Variable",
    "Geist Variable",
    "Geist Mono Variable",
  ])
    expect(
      await page.evaluate(
        (name) => document.fonts.check(`16px "${name}"`),
        family,
      ),
      family,
    ).toBe(true);
  await expect(page.locator("body")).toHaveCSS(
    "font-family",
    /^"Geist Variable"/,
  );
  await expect(page.locator("pre code").first()).toHaveCSS(
    "font-family",
    /^"Geist Mono Variable"/,
  );
  // Equal-width digits, so figures line up in tables.
  await expect(page.locator("td").first()).toHaveCSS(
    "font-variant-numeric",
    /tabular-nums/,
  );

  expect([...hosts]).toEqual([new URL(page.url()).host]);
});

test("the backdrop is decoration that stays out of the way", async ({
  page,
}) => {
  await page.goto("/");
  const backdrop = page.locator("[data-backdrop]");
  await expect(backdrop).toHaveAttribute("aria-hidden", "true");
  await expect(backdrop).toHaveCSS("pointer-events", "none");

  // Whatever is at the middle of the window, it isn't the backdrop.
  const inBackdrop = await page.evaluate(() => {
    const element = document.elementFromPoint(
      window.innerWidth / 2,
      window.innerHeight / 2,
    );
    return element?.closest("[data-backdrop]") != null;
  });
  expect(inBackdrop).toBe(false);
});

test("the backdrop only ever animates position and size", async ({ page }) => {
  await page.goto("/");
  const animated = await page.evaluate(() =>
    document
      .querySelector("[data-backdrop]")!
      .getAnimations({ subtree: true })
      .map((animation) =>
        (animation.effect as KeyframeEffect)
          .getKeyframes()
          .flatMap((keyframe) =>
            Object.keys(keyframe).filter(
              (key) =>
                !["offset", "easing", "composite", "computedOffset"].includes(
                  key,
                ),
            ),
          ),
      ),
  );
  expect(animated).toHaveLength(3);
  for (const properties of animated)
    expect(new Set(properties)).toEqual(new Set(["transform"]));
});

test("the backdrop is still when the computer asks for less motion", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.locator("[data-backdrop]")).toBeAttached();
  const running = await page.evaluate(
    () =>
      document
        .querySelector("[data-backdrop]")!
        .getAnimations({ subtree: true }).length,
  );
  expect(running).toBe(0);
});
