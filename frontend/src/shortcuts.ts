// App-wide keyboard shortcuts: Ctrl+Shift+O starts a new chat and Ctrl+K opens
// the chat search. (Enter and Shift+Enter belong to the message box, and Esc
// closes dialogs by itself.) Both Ctrl and ⌘ work, so the same code runs on
// Windows and on a Mac.
import { useEffect } from "react";

/** The key to show in hints: ⌘ on a Mac, Ctrl everywhere else. */
export function modifierKeyName(): string {
  return /Mac/.test(navigator.userAgent) ? "⌘" : "Ctrl";
}

type Shortcuts = {
  onNewChat: () => void;
  onSearch: () => void;
};

export function useShortcuts({ onNewChat, onSearch }: Shortcuts) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (!(event.ctrlKey || event.metaKey)) return;
      const key = event.key.toLowerCase();
      if (event.shiftKey && key === "o") {
        event.preventDefault();
        onNewChat();
      } else if (!event.shiftKey && key === "k") {
        event.preventDefault();
        onSearch();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onNewChat, onSearch]);
}
