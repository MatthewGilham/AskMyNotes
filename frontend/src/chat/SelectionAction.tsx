// Capture selection before focus moves; Tab reaches the action and Escape dismisses it.
import { useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { readAnswerSelection, type AnswerSelection } from "./selection";
import type { QuotedContext } from "./types";
import styles from "./SelectionAction.module.css";

export function SelectionAction({
  onQuote,
}: {
  onQuote: (quote: QuotedContext) => void;
}) {
  const [selection, setSelection] = useState<AnswerSelection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const action = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    function capture() {
      if (document.activeElement === action.current) return;
      setSelection(readAnswerSelection());
      setError(null);
    }
    function keyboard(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setSelection(null);
        setError(null);
        window.getSelection()?.removeAllRanges();
      } else if (
        event.key === "Tab" &&
        !event.shiftKey &&
        readAnswerSelection() &&
        document.activeElement !== action.current
      ) {
        event.preventDefault();
        // Tab can arrive before selectionchange has committed the new button.
        flushSync(() => setSelection(readAnswerSelection()));
        action.current?.focus({ preventScroll: true });
      }
    }
    function dismiss() {
      setSelection(null);
      setError(null);
    }
    document.addEventListener("selectionchange", capture);
    document.addEventListener("keydown", keyboard);
    document.addEventListener("scroll", dismiss, true);
    window.addEventListener("resize", dismiss);
    return () => {
      document.removeEventListener("selectionchange", capture);
      document.removeEventListener("keydown", keyboard);
      document.removeEventListener("scroll", dismiss, true);
      window.removeEventListener("resize", dismiss);
    };
  }, []);
  if (!selection) return null;
  return (
    <div
      className={styles.action}
      style={{ left: selection.left, top: selection.top }}
    >
      <button
        ref={action}
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => {
          if (Array.from(selection.quote.excerpt).length > 8000) {
            setError(
              "Please select a shorter passage (maximum 8,000 characters).",
            );
            return;
          }
          onQuote(selection.quote);
          setSelection(null);
          window.getSelection()?.removeAllRanges();
          document
            .querySelector<HTMLTextAreaElement>(
              'textarea[aria-label="Message"]',
            )
            ?.focus();
        }}
      >
        Ask about this
      </button>
      {error && (
        <div role="alert" className={styles.error}>
          {error}
        </div>
      )}
    </div>
  );
}
