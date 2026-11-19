// The appearance choices: the colour theme, the effects level, and whether the
// sidebar is open in a wide window. They are kept in the browser's storage
// under one key, so each browser on each computer remembers its own.
//
// The theme and effects are shown by two attributes on the <html> element,
// which the stylesheets respond to: data-theme ("aurora" or "ice"; none for
// Volt) and data-effects ("calm"; none for Full). A few lines in index.html
// set them from the saved value before the page first draws.
import { useState } from "react";

export const THEMES = ["volt", "aurora", "ice"] as const;
export const EFFECTS = ["full", "calm"] as const;
export type Theme = (typeof THEMES)[number];
export type Effects = (typeof EFFECTS)[number];

export type Appearance = {
  theme: Theme;
  effects: Effects;
  sidebarOpen: boolean;
};

const STORAGE_KEY = "askmynotes-appearance";

/** The saved choices. Anything missing, damaged or unreadable falls back to
 * Volt, Full and an open sidebar. */
function loadAppearance(): Appearance {
  let saved: Record<string, unknown> | null;
  try {
    saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null");
  } catch {
    // The value isn't JSON, or the browser refuses access to its storage.
    saved = null;
  }
  return {
    theme: THEMES.find((theme) => theme === saved?.theme) ?? "volt",
    effects: EFFECTS.find((effects) => effects === saved?.effects) ?? "full",
    sidebarOpen: saved?.sidebarOpen !== false,
  };
}

function saveAppearance(appearance: Appearance) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(appearance));
  } catch {
    // The browser refuses access to its storage, so the choice lasts only
    // until the page is closed.
  }
}

function showOnPage({ theme, effects }: Appearance) {
  const page = document.documentElement.dataset;
  if (theme === "volt") delete page.theme;
  else page.theme = theme;
  if (effects === "full") delete page.effects;
  else page.effects = effects;
}

/** The appearance choices, and a function that changes some of them: it
 * updates the page and saves the new choices. */
export function useAppearance() {
  const [appearance, setAppearance] = useState(loadAppearance);

  function changeAppearance(changes: Partial<Appearance>) {
    const changed = { ...appearance, ...changes };
    setAppearance(changed);
    showOnPage(changed);
    saveAppearance(changed);
  }

  return { appearance, changeAppearance };
}
