// The colour theme in use, read from the data-theme attribute on the <html>
// element ("volt" when there is none). Components that draw with colours worked
// out in code, such as diagrams, use it to draw again when the theme changes.
import { useSyncExternalStore } from "react";

function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"],
  });
  return () => observer.disconnect();
}

function currentTheme(): string {
  return document.documentElement.dataset.theme ?? "volt";
}

/** The colour theme's name, updated whenever it changes. */
export function useTheme(): string {
  return useSyncExternalStore(subscribe, currentTheme);
}
