// Whether the browser window is narrow: below 900px wide, in CSS pixels, so
// browser zoom counts. In a narrow window the sidebar starts as its rail and,
// when opened, floats over the conversation instead of squeezing it.
import { useSyncExternalStore } from "react";

const NARROW_WINDOW = "(max-width: 899px)";

function watchWidth(onChange: () => void) {
  const query = window.matchMedia(NARROW_WINDOW);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

/** True while the window is narrower than 900px; updates as it is resized. */
export function useNarrowWindow(): boolean {
  return useSyncExternalStore(
    watchWidth,
    () => window.matchMedia(NARROW_WINDOW).matches,
  );
}
