// The chat search: type to find chats by their title or the text of their
// messages. Up and Down move through the results and Enter opens one.
import * as Dialog from "@radix-ui/react-dialog";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useEffect, useState, type KeyboardEvent, type ReactNode } from "react";
import { searchChats } from "../api/client";
import type { ChatSummary } from "../chat/types";
import styles from "./Dialogs.module.css";

// Wait for a pause in typing before searching.
const TYPING_PAUSE_MS = 200;
const RECENT_CHATS_SHOWN = 8;

type SearchDialogProps = {
  open: boolean;
  recentChats: ChatSummary[];
  onClose: () => void;
  onOpenChat: (chatId: string, messageId?: number | null) => void;
};

type Row = {
  chatId: string;
  title: string;
  snippet?: string;
  messageId?: number | null;
};

/**
 * The text with each searched word marked wherever a word starts with it,
 * which is how the search itself matches ("depre" finds "depreciation").
 */
function markMatches(text: string, query: string): ReactNode {
  const words = query.match(/[\p{L}\p{N}_]+/gu);
  if (!words) return text;
  const starts = new RegExp(
    String.raw`(?<![\p{L}\p{N}_])(${words.join("|")})`,
    "giu",
  );
  // Splitting on a group keeps the matches, at the odd positions.
  return text.split(starts).map((part, index) =>
    index % 2 ? (
      <mark key={index} className={styles.match}>
        {part}
      </mark>
    ) : (
      part
    ),
  );
}

export function SearchDialog({
  open,
  recentChats,
  onClose,
  onOpenChat,
}: SearchDialogProps) {
  const [text, setText] = useState("");
  const [query, setQuery] = useState("");
  const [highlighted, setHighlighted] = useState(0);

  useEffect(() => {
    const timer = setTimeout(() => setQuery(text.trim()), TYPING_PAUSE_MS);
    return () => clearTimeout(timer);
  }, [text]);

  const results = useQuery({
    queryKey: ["chats", "search", query],
    queryFn: () => searchChats(query),
    enabled: open && query !== "",
  });

  // With nothing typed, offer the most recent chats.
  const rows: Row[] =
    query === ""
      ? recentChats
          .slice(0, RECENT_CHATS_SHOWN)
          .map((chat) => ({ chatId: chat.id, title: chat.title }))
      : (results.data ?? []);

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlighted(Math.min(highlighted + 1, rows.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlighted(Math.max(highlighted - 1, 0));
    } else if (event.key === "Enter" && rows[highlighted]) {
      onOpenChat(rows[highlighted].chatId, rows[highlighted].messageId);
    }
  }

  function handleOpenChange(isOpen: boolean) {
    if (isOpen) return;
    setText("");
    setQuery("");
    setHighlighted(0);
    onClose();
  }

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className={styles.overlay} />
        <Dialog.Content
          className={`${styles.panel} ${styles.searchPanel}`}
          onKeyDown={handleKeyDown}
          aria-describedby={undefined}
          onCloseAutoFocus={(event) => event.preventDefault()}
        >
          <Dialog.Title className={styles.visuallyHidden}>
            Search chats
          </Dialog.Title>
          <div className={styles.searchBox}>
            <Search size={18} />
            <input
              className={styles.searchInput}
              value={text}
              onChange={(event) => {
                setText(event.target.value);
                setHighlighted(0);
              }}
              placeholder="Search chats"
              aria-label="Search chats"
              autoFocus
            />
          </div>

          <ul className={styles.results}>
            {rows.map((row, index) => (
              <li key={row.chatId}>
                <button
                  className={`${styles.result} ${index === highlighted ? styles.highlighted : ""}`}
                  onClick={() => onOpenChat(row.chatId, row.messageId)}
                  onMouseMove={() => setHighlighted(index)}
                >
                  <span className={styles.resultTitle}>
                    {markMatches(row.title, query)}
                  </span>
                  {row.snippet && row.snippet !== row.title && (
                    <span className={styles.resultSnippet}>
                      {markMatches(row.snippet, query)}
                    </span>
                  )}
                </button>
              </li>
            ))}
            {query !== "" && !results.isFetching && rows.length === 0 && (
              <li className={styles.noResults}>No chats found</li>
            )}
          </ul>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
