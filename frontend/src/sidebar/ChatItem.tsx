// One chat in the sidebar: its title, and a "…" menu to rename, pin or delete
// it. Renaming happens in place, right where the title is.
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { MoreHorizontal, Pencil, Pin, PinOff, Trash2 } from "lucide-react";
import { useState, type KeyboardEvent } from "react";
import type { ChatSummary } from "../chat/types";
import styles from "./Sidebar.module.css";

type ChatItemProps = {
  chat: ChatSummary;
  selected: boolean;
  onSelect: () => void;
  onRename: (title: string) => void;
  onSetPinned: (pinned: boolean) => void;
  onDelete: () => void;
};

export function ChatItem({
  chat,
  selected,
  onSelect,
  onRename,
  onSetPinned,
  onDelete,
}: ChatItemProps) {
  const [renaming, setRenaming] = useState(false);

  function finishRename(title: string) {
    setRenaming(false);
    const trimmed = title.trim();
    if (trimmed !== "" && trimmed !== chat.title) onRename(trimmed);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") finishRename(event.currentTarget.value);
    if (event.key === "Escape") setRenaming(false);
  }

  return (
    <div className={`${styles.chat} ${selected ? styles.selected : ""}`}>
      {renaming ? (
        <input
          className={styles.renameInput}
          defaultValue={chat.title}
          autoFocus
          onFocus={(event) => event.currentTarget.select()}
          onKeyDown={handleKeyDown}
          onBlur={(event) => finishRename(event.currentTarget.value)}
          aria-label="Chat title"
        />
      ) : (
        <button className={styles.chatTitle} onClick={onSelect}>
          {chat.pinned && <Pin size={12} className={styles.pinIcon} />}
          <span className={styles.chatTitleText}>{chat.title}</span>
        </button>
      )}

      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button className={styles.chatMenu} title="Chat options">
            <MoreHorizontal size={16} />
          </button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content
            className={styles.menu}
            align="start"
            sideOffset={4}
            // Closing the menu would otherwise return focus to the "…" button,
            // which steals it from the rename box.
            onCloseAutoFocus={(event) => event.preventDefault()}
          >
            <DropdownMenu.Item
              className={styles.menuItem}
              onSelect={() => setRenaming(true)}
            >
              <Pencil size={14} /> Rename
            </DropdownMenu.Item>
            <DropdownMenu.Item
              className={styles.menuItem}
              onSelect={() => onSetPinned(!chat.pinned)}
            >
              {chat.pinned ? <PinOff size={14} /> : <Pin size={14} />}
              {chat.pinned ? "Unpin" : "Pin"}
            </DropdownMenu.Item>
            <DropdownMenu.Item
              className={`${styles.menuItem} ${styles.menuItemDanger}`}
              onSelect={onDelete}
            >
              <Trash2 size={14} /> Delete
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </div>
  );
}
