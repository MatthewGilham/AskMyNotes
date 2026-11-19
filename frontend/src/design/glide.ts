// The moving message box. On the first message of a new chat the new chat
// screen is swapped for the conversation, and the message box glides from the
// middle of the screen to the bottom instead of jumping there.
//
// The browser does the gliding, through its View Transitions feature: it
// notes where the message box is, lets the page change, then moves a picture
// of the box from the old place to the new one. Which element glides, and how
// fast, is set in CSS (MessageBox.module.css and tokens.css).
import { flushSync } from "react-dom";

/** Changes the page, gliding the message box to its new place. Resolves once
 * the change is on the page. With Calm effects, reduced motion, or a browser
 * without the feature, the change is simply made at once. */
export function glideMessageBox(change: () => void): Promise<void> {
  const still =
    document.documentElement.dataset.effects === "calm" ||
    matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (still || !("startViewTransition" in document)) {
    change();
    return Promise.resolve();
  }
  // flushSync: the browser needs the page changed by the time this returns.
  return document.startViewTransition(() => flushSync(change))
    .updateCallbackDone;
}
