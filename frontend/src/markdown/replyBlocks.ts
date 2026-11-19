// Splits a reply into ordinary Markdown and the boxes the model wraps content in.
//
// A box starts with a line of its own, such as `:::beyond`, and ends with a
// line `:::`:
//   - `:::beyond` is knowledge from outside the student's notes;
//   - `:::web` is something taken from the web;
//   - `:::formula`, `:::tip`, `:::mistake` and `:::example` are the four
//     callouts: a key formula, an exam tip, a common mistake and a worked
//     example.
// A callout can sit inside a `beyond` or `web` box (one level of nesting), so a
// formula from outside the notes is still labelled as outside them. Nothing
// else nests.
//
// Only a marker on a line of its own counts, and never inside a code block, so
// ordinary text such as `Note:This` is left alone, and so is an unknown
// `:::name`. While a reply is still streaming, the closing line may not have
// arrived yet, so an open box runs to the end.

export type SourceBox = "beyond" | "web";
export type Callout = "formula" | "tip" | "mistake" | "example";
export type BlockKind = SourceBox | Callout;

export type ReplyNode =
  | { kind: "markdown"; markdown: string }
  | { kind: BlockKind; children: ReplyNode[] };

const OPENERS: Record<string, BlockKind> = {
  ":::beyond": "beyond",
  ":::web": "web",
  ":::formula": "formula",
  ":::tip": "tip",
  ":::mistake": "mistake",
  ":::example": "example",
};
const CLOSE = ":::";
const FENCE = /^\s*(```+|~~~+)/;

type OpenBlock = { kind: BlockKind; children: ReplyNode[] };

function isSourceBox(kind: BlockKind): kind is SourceBox {
  return kind === "beyond" || kind === "web";
}

export function splitReplyBlocks(markdown: string): ReplyNode[] {
  const root: ReplyNode[] = [];
  const open: OpenBlock[] = [];
  let text = "";
  let fence: string | null = null;

  const container = () =>
    open.length > 0 ? open[open.length - 1].children : root;
  function flush() {
    if (text.trim() !== "")
      container().push({ kind: "markdown", markdown: text });
    text = "";
  }
  function close() {
    flush();
    const block = open.pop()!;
    if (block.children.length > 0) container().push(block);
  }

  for (const line of markdown.split("\n")) {
    const fenceMatch = FENCE.exec(line);
    if (fenceMatch) {
      if (fence === null) fence = fenceMatch[1][0];
      else if (fenceMatch[1][0] === fence) fence = null;
    }
    const marker = line.trim();
    const kind = fence === null ? OPENERS[marker] : undefined;
    const top = open.length > 0 ? open[open.length - 1].kind : null;
    // Source boxes only open at the top; callouts open at the top or directly
    // inside a source box.
    const canOpen =
      kind !== undefined &&
      (top === null || (!isSourceBox(kind) && isSourceBox(top)));
    if (canOpen) {
      flush();
      open.push({ kind, children: [] });
    } else if (fence === null && marker === CLOSE && open.length > 0) {
      close();
    } else {
      text += line + "\n";
    }
  }
  while (open.length > 0) close();
  flush();

  return root;
}
