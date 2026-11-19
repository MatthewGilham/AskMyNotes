// Unit tests for the block reader. No browser is needed: Playwright runs the
// TypeScript directly, and the reader is plain text in, a tree out.
import { expect, test } from "@playwright/test";
import { splitReplyBlocks, type ReplyNode } from "../src/markdown/replyBlocks";

/** The tree as a compact string, to make the expectations readable. */
function shape(nodes: ReplyNode[]): string {
  return nodes
    .map((node) =>
      node.kind === "markdown"
        ? `"${node.markdown.trim()}"`
        : `${node.kind}[${shape(node.children)}]`,
    )
    .join(" ");
}

const read = (text: string) => shape(splitReplyBlocks(text));

test("plain Markdown is one node", () => {
  expect(read("Hello\n\nthere")).toBe('"Hello\n\nthere"');
});

for (const kind of ["formula", "tip", "mistake", "example", "beyond", "web"]) {
  test(`a ${kind} block is read`, () => {
    expect(read(`Before\n:::${kind}\nInside\n:::\nAfter`)).toBe(
      `"Before" ${kind}["Inside"] "After"`,
    );
  });
}

test("a callout nests inside a Beyond your notes block", () => {
  expect(
    read(":::beyond\nOutside.\n:::formula\nE = mc^2\n:::\nMore\n:::"),
  ).toBe('beyond["Outside." formula["E = mc^2"] "More"]');
});

test("a callout nests inside a From the web block", () => {
  expect(read(":::web\nA page says:\n:::tip\nTip\n:::\n:::\nDone")).toBe(
    'web["A page says:" tip["Tip"]] "Done"',
  );
});

test("a callout can't hold another box, and a source box can't nest", () => {
  // Inside a callout, `:::tip` is just text and the first `:::` closes it.
  expect(read(":::formula\nA\n:::tip\nB\n:::\nC")).toBe(
    'formula["A\n:::tip\nB"] "C"',
  );
  // `:::web` inside `:::beyond` is just text too.
  expect(read(":::beyond\nA\n:::web\nB\n:::")).toBe('beyond["A\n:::web\nB"]');
});

test("an unclosed block while streaming runs to the end", () => {
  expect(read("Intro\n:::tip\nHalf a tip")).toBe('"Intro" tip["Half a tip"]');
  expect(read(":::beyond\nOutside\n:::formula\nHalf a form")).toBe(
    'beyond["Outside" formula["Half a form"]]',
  );
});

test("text that only looks like a marker is left alone", () => {
  expect(read("Note:This is fine\nand so is :::tip in a line")).toBe(
    '"Note:This is fine\nand so is :::tip in a line"',
  );
  // Not on a line of its own.
  expect(read("see :::beyond here")).toBe('"see :::beyond here"');
});

test("an unknown :::name stays as text", () => {
  // The stray closer has no box to close, so it is text too.
  expect(read("A\n:::banana\nB\n:::\nC")).toBe('"A\n:::banana\nB\n:::\nC"');
});

test("markers inside a code block are left alone", () => {
  const text = "Code:\n\n```text\n:::tip\n:::\n```\n\nAfter";
  expect(read(text)).toBe(`"${text}"`);
  // And a tilde fence works the same way.
  const tilde = "~~~\n:::beyond\n~~~";
  expect(read(tilde)).toBe(`"${tilde}"`);
});

test("a box opens normally after a code block closes", () => {
  expect(read("```js\nx\n```\n:::tip\nT\n:::")).toBe(
    '"```js\nx\n```" tip["T"]',
  );
});

test("empty boxes disappear", () => {
  expect(read("A\n:::tip\n:::\nB")).toBe('"A" "B"');
});

test("markers may have spaces round them", () => {
  expect(read("  :::tip  \nT\n  :::  ")).toBe('tip["T"]');
});
