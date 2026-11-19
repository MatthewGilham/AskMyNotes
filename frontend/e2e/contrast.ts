// Colour maths for the contrast tests: reading the themes out of tokens.css,
// laying one colour over another, and working out the WCAG contrast ratio
// between two colours. Only the tests use this; the app itself doesn't.

/** A colour as red, green and blue from 0 to 255, and opacity from 0 to 1. */
export type Colour = { r: number; g: number; b: number; a: number };

/** Each theme's tokens by name, with the default theme's values filled in. */
export type Themes = Record<string, Record<string, string>>;

/** Reads `#rrggbb`, `rgb(r, g, b)` and `rgba(r, g, b, a)`. */
export function parseColour(value: string): Colour {
  const hex = /^#([0-9a-f]{6})$/i.exec(value.trim());
  if (hex) {
    const number = parseInt(hex[1], 16);
    return {
      r: number >> 16,
      g: (number >> 8) & 255,
      b: number & 255,
      a: 1,
    };
  }
  const parts = /^rgba?\(([^)]+)\)$/.exec(value.trim());
  if (!parts) throw new Error(`Not a colour this test can read: ${value}`);
  const [r, g, b, a = 1] = parts[1].split(",").map(Number);
  return { r, g, b, a };
}

/** The same colour at another opacity. */
export function withOpacity(colour: Colour, a: number): Colour {
  return { ...colour, a };
}

/** What you see when `top` is laid over a solid `bottom`. */
export function over(top: Colour, bottom: Colour): Colour {
  const blend = (above: number, below: number) =>
    top.a * above + (1 - top.a) * below;
  return {
    r: blend(top.r, bottom.r),
    g: blend(top.g, bottom.g),
    b: blend(top.b, bottom.b),
    a: 1,
  };
}

/** How light a solid colour is, from 0 (black) to 1 (white), as WCAG defines. */
export function luminance(colour: Colour): number {
  const linear = (channel: number) => {
    const share = channel / 255;
    return share <= 0.04045 ? share / 12.92 : ((share + 0.055) / 1.055) ** 2.4;
  };
  return (
    0.2126 * linear(colour.r) +
    0.7152 * linear(colour.g) +
    0.0722 * linear(colour.b)
  );
}

/** The WCAG contrast ratio between two solid colours, from 1 to 21. */
export function contrast(first: Colour, second: Colour): number {
  const [lighter, darker] = [luminance(first), luminance(second)].sort(
    (a, b) => b - a,
  );
  return (lighter + 0.05) / (darker + 0.05);
}

/** Every `--name: value;` inside one `{ ... }` block. */
function tokensIn(block: string): Record<string, string> {
  const tokens: Record<string, string> = {};
  for (const [, name, value] of block.matchAll(/(--[\w-]+):\s*([^;]+);/g))
    tokens[name] = value.replace(/\s+/g, " ").trim();
  return tokens;
}

/** The themes in tokens.css: "volt" from :root, the others from data-theme. */
export function readThemes(css: string): Themes {
  const root = /:root\s*\{([^}]*)\}/.exec(css);
  if (!root) throw new Error("tokens.css has no :root block");
  const volt = tokensIn(root[1]);
  const themes: Themes = { volt };
  for (const [, name, block] of css.matchAll(
    /\[data-theme="(\w+)"\]\s*\{([^}]*)\}/g,
  ))
    themes[name] = { ...volt, ...tokensIn(block) };
  return themes;
}
