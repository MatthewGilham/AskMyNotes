// Read one answer selection, expanding touched KaTeX expressions in a cloned range.
import type { QuotedContext } from "./types";

export type AnswerSelection = {
  quote: QuotedContext;
  left: number;
  top: number;
};

function elementOf(node: Node): Element | null {
  return node instanceof Element ? node : node.parentElement;
}

function equationAt(node: Node): Element | null {
  const math = elementOf(node)?.closest(".katex");
  return math?.closest(".katex-display") ?? math ?? null;
}

function renderedText(node: Node): string {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent ?? "";
  if (node instanceof Element) {
    if (node.matches(".katex-display, .katex")) {
      const latex = node.querySelector(
        'annotation[encoding="application/x-tex"]',
      )?.textContent;
      if (latex)
        return node.matches(".katex-display")
          ? `\\[${latex}\\]`
          : `\\(${latex}\\)`;
    }
    if (node.tagName === "BR") return "\n";
  }
  const text = Array.from(node.childNodes).map(renderedText).join("");
  if (node instanceof Element && node.tagName === "LI")
    return "- " + text + "\n";
  return node instanceof Element &&
    /^(P|DIV|LI|TR|H[1-6]|PRE|BLOCKQUOTE)$/.test(node.tagName)
    ? text + "\n"
    : text;
}

export function readAnswerSelection(): AnswerSelection | null {
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed || selection.rangeCount !== 1)
    return null;
  const original = selection.getRangeAt(0);
  const body = elementOf(original.startContainer)?.closest<HTMLElement>(
    "[data-quote-answer]",
  );
  if (
    !body ||
    !body.contains(original.endContainer) ||
    !body.contains(original.commonAncestorContainer)
  )
    return null;
  // Controls, and drawn diagrams and charts, can't be quoted.
  if (
    Array.from(
      body.querySelectorAll(
        "button, input, textarea, select, [role=button], [data-no-quote]",
      ),
    ).some((control) => original.intersectsNode(control))
  )
    return null;
  const range = original.cloneRange();
  const startMath = equationAt(range.startContainer);
  const endMath = equationAt(range.endContainer);
  if (startMath) range.setStartBefore(startMath);
  if (endMath) range.setEndAfter(endMath);
  const excerpt = renderedText(range.cloneContents()).trim();
  if (!excerpt) return null;
  const rect = original.getBoundingClientRect();
  return {
    quote: { sourceMessageId: Number(body.dataset.quoteAnswer), excerpt },
    left: Math.max(12, Math.min(rect.left, window.innerWidth - 210)),
    top: Math.max(12, Math.min(rect.bottom + 8, window.innerHeight - 160)),
  };
}
