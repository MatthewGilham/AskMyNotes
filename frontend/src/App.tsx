// The root component: the moving backdrop behind everything, the sidebar on the
// left and, beside it, either the new chat screen or the open conversation. The address bar says which chat is
// open (/chat/<id>), so refreshing the page keeps your place. In a narrow
// window the sidebar is a rail, and opening it floats it over the page.
import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { useMatch, useNavigate } from "react-router";
import { getConfig, listChats } from "./api/client";
import { useAttachments } from "./chat/attachments";
import { Conversation } from "./chat/Conversation";
import { DropZone } from "./chat/DropZone";
import type { ComposerProps } from "./chat/MessageBox";
import { NewChatScreen } from "./chat/NewChatScreen";
import type { ChatSummary } from "./chat/types";
import { useConversation } from "./chat/useConversation";
import { useNotesStatus } from "./notes/useNotesStatus";
import { useShortcuts } from "./shortcuts";
import { DeleteChatDialog } from "./sidebar/DeleteChatDialog";
import { SearchDialog } from "./sidebar/SearchDialog";
import { Sidebar } from "./sidebar/Sidebar";
import { useChatActions } from "./sidebar/useChatActions";
import { useAppearance } from "./design/appearance";
import { Backdrop } from "./design/Backdrop";
import { useNarrowWindow } from "./useNarrowWindow";
import styles from "./App.module.css";

export function App() {
  const navigate = useNavigate();
  const narrow = useNarrowWindow();
  // The theme, the effects level and whether the sidebar is open in a wide
  // window: remembered by the browser. The floating sidebar's state is kept
  // apart, so whatever happens in a narrow window, widening it again brings
  // the sidebar back as you left it.
  const { appearance, changeAppearance } = useAppearance();
  const [floatingSidebarOpen, setFloatingSidebarOpen] = useState(false);
  const [wasNarrow, setWasNarrow] = useState(narrow);
  if (narrow !== wasNarrow) {
    // The window has just crossed 900px: a narrow window starts with the rail.
    setWasNarrow(narrow);
    setFloatingSidebarOpen(false);
  }
  const railToggle = useRef<HTMLButtonElement>(null);
  const floatingToggle = useRef<HTMLButtonElement>(null);
  const routeChatId = useMatch("/chat/:chatId")?.params.chatId;

  const config = useQuery({ queryKey: ["config"], queryFn: getConfig });
  const chats = useQuery({ queryKey: ["chats"], queryFn: listChats });
  const conversation = useConversation(routeChatId);
  const attachments = useAttachments({
    maxImages: config.data?.maxImagesPerMessage ?? 0,
    maxImageMegabytes: config.data?.maxImageSizeMb ?? 0,
    maxDocuments: config.data?.maxDocumentsPerMessage ?? 0,
    maxDocumentMegabytes: config.data?.maxDocumentSizeMb ?? 0,
  });
  const actions = useChatActions(conversation.chatId);
  const notes = useNotesStatus();
  const [searchOpen, setSearchOpen] = useState(false);
  const [chatToDelete, setChatToDelete] = useState<ChatSummary | null>(null);

  // Choosing anything from the floating sidebar closes it, as the chat it
  // opens is what you want to see.
  const startNewChat = useCallback(() => {
    setFloatingSidebarOpen(false);
    navigate("/");
  }, [navigate]);
  const openSearch = useCallback(() => {
    setFloatingSidebarOpen(false);
    setSearchOpen(true);
  }, []);
  useShortcuts({ onNewChat: startNewChat, onSearch: openSearch });

  // Opening the floating sidebar moves focus into it, for keyboard users.
  useEffect(() => {
    if (floatingSidebarOpen) floatingToggle.current?.focus();
  }, [floatingSidebarOpen]);

  function closeFloatingSidebar() {
    setFloatingSidebarOpen(false);
    railToggle.current?.focus();
  }

  const chatList = chats.data ?? [];
  const title =
    chatList.find((chat) => chat.id === conversation.chatId)?.title ??
    "New chat";
  const showConversation =
    conversation.chatId !== null || conversation.messages.length > 0;

  const composer: ComposerProps = {
    busy: conversation.busy,
    waitingForNotes: notes.updating,
    attachments: attachments.attachments,
    attachmentError: attachments.error,
    quotedContext: conversation.quotedContext,
    onQuote: conversation.setQuotedContext,
    sendError: conversation.sendError,
    onSend: async (text, usePython) => {
      const { images, documents } = await attachments.toUploads();
      const accepted = await conversation.send(
        text,
        images,
        documents,
        usePython,
      );
      if (accepted) attachments.clear();
      return accepted;
    },
    onStop: conversation.stop,
    onAddFiles: attachments.addFiles,
    onRemoveAttachment: attachments.remove,
  };

  const sidebar = {
    chats: chatList,
    selectedChatId: conversation.chatId,
    notes: notes.status,
    onRefreshNotes: notes.refresh,
    onNewChat: startNewChat,
    onSelectChat: (chatId: string) => {
      setFloatingSidebarOpen(false);
      navigate(`/chat/${chatId}`);
    },
    onSearch: openSearch,
    onRename: actions.rename,
    onSetPinned: actions.setPinned,
    onDelete: setChatToDelete,
    appearance,
    onAppearanceChange: changeAppearance,
  };

  return (
    // data-thinking is there for the whole of a reply. The stylesheets use it
    // to "charge up": the backdrop brightens and a band of light travels round
    // the message box.
    <div className={styles.app} data-thinking={conversation.busy || undefined}>
      <Backdrop />
      {narrow ? (
        <Sidebar
          {...sidebar}
          open={false}
          onToggle={() => setFloatingSidebarOpen(true)}
          toggleRef={railToggle}
        />
      ) : (
        <Sidebar
          {...sidebar}
          open={appearance.sidebarOpen}
          onToggle={() =>
            changeAppearance({ sidebarOpen: !appearance.sidebarOpen })
          }
        />
      )}
      <main className={styles.main}>
        <DropZone onFiles={attachments.addFiles}>
          {showConversation ? (
            <Conversation
              key={conversation.chatId ?? "new"}
              chatId={conversation.chatId}
              title={title}
              messages={conversation.messages}
              composer={composer}
              onRegenerate={conversation.regenerate}
              onEdit={conversation.edit}
            />
          ) : (
            config.data && (
              <NewChatScreen
                userName={config.data.userName}
                examplePrompts={config.data.examplePrompts}
                composer={composer}
              />
            )
          )}
        </DropZone>
      </main>

      {narrow && floatingSidebarOpen && (
        <div
          className={styles.floating}
          onKeyDown={(event) => {
            // Escape inside an open menu or the rename box is theirs to use.
            if (
              event.key === "Escape" &&
              !event.defaultPrevented &&
              !(event.target instanceof HTMLInputElement)
            )
              closeFloatingSidebar();
          }}
        >
          <div
            className={styles.backdrop}
            aria-hidden="true"
            onClick={closeFloatingSidebar}
          />
          <div className={styles.floatingPanel}>
            <Sidebar
              {...sidebar}
              open
              onToggle={closeFloatingSidebar}
              toggleRef={floatingToggle}
            />
          </div>
        </div>
      )}

      <SearchDialog
        open={searchOpen}
        recentChats={chatList}
        onClose={() => setSearchOpen(false)}
        onOpenChat={(chatId, messageId) => {
          setSearchOpen(false);
          navigate(
            `/chat/${chatId}${messageId == null ? "" : `#message-${messageId}`}`,
          );
        }}
      />
      <DeleteChatDialog
        chat={chatToDelete}
        onCancel={() => setChatToDelete(null)}
        onConfirm={(chat) => {
          actions.remove(chat.id);
          setChatToDelete(null);
        }}
      />
    </div>
  );
}
