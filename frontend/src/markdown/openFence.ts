// Which code block, if any, is still being written.
//
// While a reply streams, a fenced block whose closing fence hasn't arrived yet
// is "open", and can only be the last thing in the text. Diagrams and charts
// aren't drawn until their block closes, so half-written code is never drawn.
import { createContext } from "react";

const FENCE = /^\s*(```+|~~~+)/;

/** The line number (counting from 1) of the fence that opens a block with no
 * closing fence yet, or null if every block is closed. */
export function openFenceLine(markdown: string): number | null {
  let fence: string | null = null;
  let openedAt = 0;
  for (const [index, line] of markdown.split("\n").entries()) {
    const match = FENCE.exec(line);
    if (!match) continue;
    if (fence === null) {
      fence = match[1][0];
      openedAt = index + 1;
    } else if (match[1][0] === fence) {
      fence = null;
    }
  }
  return fence === null ? null : openedAt;
}

/** The open block's first line in the Markdown being drawn, shared with the
 * code block components below it. */
export const OpenFence = createContext<number | null>(null);
