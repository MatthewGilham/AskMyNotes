// Phase 29: text must stay readable in every colour theme. The app's surfaces
// are dark glass over moving light, so what is behind the text changes. These
// tests take the worst case: the brightest of the backdrop's lights, at its
// full strength, directly behind the text. No browser is needed: the colours
// are read straight from tokens.css.
import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import {
  contrast,
  luminance,
  over,
  parseColour,
  readThemes,
  withOpacity,
  type Colour,
} from "./contrast";

const themes = readThemes(
  readFileSync(join("src", "design", "tokens.css"), "utf8"),
);

// WCAG's levels: 7:1 is "enhanced" for body text, 4.5:1 the minimum for text.
const BODY_TEXT = 7;
const OTHER_TEXT = 4.5;

// Each reserved colour's label, and the tint it sits on.
const RESERVED = [
  ["--color-beyond", "--color-beyond-tint"],
  ["--color-web", "--color-web-tint"],
  ["--color-error", "--color-error-tint"],
  ["--color-violet-bright", "--color-violet-tint"],
  ["--color-aqua", "--color-aqua-tint"],
];

test("tokens.css defines the three themes", () => {
  expect(Object.keys(themes).sort()).toEqual(["aurora", "ice", "volt"]);
});

for (const [name, tokens] of Object.entries(themes)) {
  const colour = (token: string) => parseColour(tokens[token]);

  /** The base with the brightest light behind it, at the given strength. */
  const litBase = (strength: number): Colour =>
    ["--glow-1", "--glow-2", "--glow-3"]
      .map((glow) =>
        over(withOpacity(colour(glow), strength), colour("--color-base")),
      )
      .sort((a, b) => luminance(b) - luminance(a))[0];

  const charged = litBase(Number(tokens["--glow-charged"]));
  const idle = litBase(Number(tokens["--glow-idle"]));
  const pane = over(colour("--color-panel"), charged);

  test(`${name}: text straight on the backdrop is readable at full strength`, () => {
    expect(contrast(colour("--color-text"), charged)).toBeGreaterThanOrEqual(
      BODY_TEXT,
    );
    expect(contrast(colour("--color-muted"), charged)).toBeGreaterThanOrEqual(
      OTHER_TEXT,
    );
  });

  test(`${name}: text on a glass pane is readable at full strength`, () => {
    expect(contrast(colour("--color-text"), pane)).toBeGreaterThanOrEqual(
      BODY_TEXT,
    );
    for (const token of ["--color-muted", "--color-faint"])
      expect(contrast(colour(token), pane), token).toBeGreaterThanOrEqual(
        OTHER_TEXT,
      );
  });

  test(`${name}: text on a pane stays readable under the pointer's light`, () => {
    // The light is a wash of the accent, strongest right under the pointer.
    const lit = over(
      withOpacity(
        colour("--color-accent"),
        Number(tokens["--spotlight-strength"]),
      ),
      pane,
    );
    expect(contrast(colour("--color-text"), lit)).toBeGreaterThanOrEqual(
      BODY_TEXT,
    );
    for (const token of ["--color-muted", "--color-faint"])
      expect(contrast(colour(token), lit), token).toBeGreaterThanOrEqual(
        OTHER_TEXT,
      );
  });

  test(`${name}: text on something hovered or chosen on a pane is readable`, () => {
    // A white wash over the pane: a chip, a hovered row, the chosen result.
    for (const wash of ["--color-wash", "--color-wash-strong"])
      expect(
        contrast(colour("--color-muted"), over(colour(wash), pane)),
        wash,
      ).toBeGreaterThanOrEqual(OTHER_TEXT);
  });

  test(`${name}: each reserved colour's label is readable on its tint`, () => {
    for (const [label, tint] of RESERVED) {
      // On a pane, at full strength: where labelled blocks sit from phase 32.
      expect(
        contrast(colour(label), over(colour(tint), pane)),
        `${label} on a pane`,
      ).toBeGreaterThanOrEqual(OTHER_TEXT);
      // Straight on the backdrop at rest: where they sit until then.
      expect(
        contrast(colour(label), over(colour(tint), idle)),
        `${label} on the backdrop at rest`,
      ).toBeGreaterThanOrEqual(OTHER_TEXT);
    }
  });

  // Phase 33: each theme has its own six chart colours.
  test(`${name}: six chart colours, none reserved, each 3:1 on a pane`, () => {
    const reserved = ["--color-beyond", "--color-error", "--color-web"].map(
      (token) => tokens[token].toLowerCase(),
    );
    for (const series of [1, 2, 3, 4, 5, 6]) {
      const token = `--chart-${series}`;
      expect(tokens[token], token).toBeDefined();
      expect(reserved, token).not.toContain(tokens[token].toLowerCase());
      // WCAG's minimum for lines and shapes is 3:1.
      expect(contrast(colour(token), pane), token).toBeGreaterThanOrEqual(3);
    }
  });

  test(`${name}: text on the accent is readable`, () => {
    for (const accent of ["--color-accent", "--color-accent-2"])
      expect(
        contrast(colour("--color-on-accent"), colour(accent)),
        accent,
      ).toBeGreaterThanOrEqual(OTHER_TEXT);
  });
}
