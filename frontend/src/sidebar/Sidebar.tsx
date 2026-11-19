// The left sidebar: new chat, chat search, the chat history grouped by when
// each chat was last used, and the notes status, API cost and Appearance menu
// at the bottom. It collapses to a slim rail of icons.
import { PanelLeftClose, PanelLeftOpen, Search, SquarePen } from "lucide-react";
import type { Ref } from "react";
import type { ChatSummary } from "../chat/types";
import type { Appearance } from "../design/appearance";
import { AppearanceMenu } from "./AppearanceMenu";
import { Mark } from "../design/Mark";
import { followPointer } from "../design/spotlight";
import type { NotesStatusData } from "../api/client";
import { NotesStatus } from "../notes/NotesStatus";
import { ApiCost } from "../usage/ApiCost";
import { modifierKeyName } from "../shortcuts";
import { groupChatsByLastUsed } from "./chatGroups";
import { ChatItem } from "./ChatItem";
import styles from "./Sidebar.module.css";

type SidebarProps = {
  open: boolean;
  chats: ChatSummary[];
  selectedChatId: string | null;
  notes: NotesStatusData | undefined;
  onRefreshNotes: () => void;
  onToggle: () => void;
  onNewChat: () => void;
  onSelectChat: (chatId: string) => void;
  onSearch: () => void;
  onRename: (chatId: string, title: string) => void;
  onSetPinned: (chatId: string, pinned: boolean) => void;
  onDelete: (chat: ChatSummary) => void;
  appearance: Appearance;
  onAppearanceChange: (changes: Partial<Appearance>) => void;
  // The open/close button, so the floating sidebar can move focus to it.
  toggleRef?: Ref<HTMLButtonElement>;
};

export function Sidebar({
  open,
  chats,
  selectedChatId,
  notes,
  onRefreshNotes,
  onToggle,
  onNewChat,
  onSelectChat,
  onSearch,
  onRename,
  onSetPinned,
  onDelete,
  appearance,
  onAppearanceChange,
  toggleRef,
}: SidebarProps) {
  if (!open) {
    return (
      <nav
        className={styles.rail}
        aria-label="Chats"
        onPointerMove={followPointer}
      >
        <button
          ref={toggleRef}
          className={styles.iconButton}
          onClick={onToggle}
          title="Open sidebar"
        >
          <PanelLeftOpen size={18} />
        </button>
        <button
          className={styles.iconButton}
          onClick={onNewChat}
          title="New chat"
        >
          <SquarePen size={18} />
        </button>
        <button
          className={styles.iconButton}
          onClick={onSearch}
          title="Search chats"
        >
          <Search size={18} />
        </button>
        <AppearanceMenu
          appearance={appearance}
          onChange={onAppearanceChange}
          onRail
        />
      </nav>
    );
  }

  return (
    <nav
      className={styles.sidebar}
      aria-label="Chats"
      onPointerMove={followPointer}
    >
      <div className={styles.header}>
        <div className={styles.brand}>
          <Mark size={26} />
          <span className={styles.wordmark}>
            AskMy<span className={styles.wordmarkAccent}>Notes</span>
          </span>
        </div>
        <button
          ref={toggleRef}
          className={styles.iconButton}
          onClick={onToggle}
          title="Close sidebar"
        >
          <PanelLeftClose size={18} />
        </button>
      </div>

      <div className={styles.actions}>
        <button
          className={`${styles.action} ${styles.primary}`}
          onClick={onNewChat}
        >
          <SquarePen size={16} />
          New chat
          <kbd className={styles.shortcut}>{modifierKeyName()} ⇧ O</kbd>
        </button>
        <button className={styles.action} onClick={onSearch}>
          <Search size={16} />
          Search chats
          <kbd className={styles.shortcut}>{modifierKeyName()} K</kbd>
        </button>
      </div>

      <div className={styles.history}>
        {groupChatsByLastUsed(chats).map((group) => (
          <section key={group.label} className={styles.group}>
            <h2 className={styles.groupLabel}>{group.label}</h2>
            {group.chats.map((chat) => (
              <ChatItem
                key={chat.id}
                chat={chat}
                selected={chat.id === selectedChatId}
                onSelect={() => onSelectChat(chat.id)}
                onRename={(title) => onRename(chat.id, title)}
                onSetPinned={(pinned) => onSetPinned(chat.id, pinned)}
                onDelete={() => onDelete(chat)}
              />
            ))}
          </section>
        ))}
      </div>

      <NotesStatus status={notes} onRefresh={onRefreshNotes} />
      <ApiCost notesUpdating={notes === undefined || notes.updating} />
      <div className={styles.footer}>
        <AppearanceMenu appearance={appearance} onChange={onAppearanceChange} />
      </div>
    </nav>
  );
}
