// Conversation navigation and scrolling share stable message targets.
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ArrowDown } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import { SelectionAction } from "./SelectionAction";
import { Message } from "./Message";
import { MessageBox, type ComposerProps } from "./MessageBox";
import { ChatUsage } from "../usage/ChatUsage";
import type { ChatMessage } from "./types";
import styles from "./Conversation.module.css";

const FOLLOW_DISTANCE = 160;
type ConversationProps = {
  chatId: string | null;
  title: string;
  messages: ChatMessage[];
  composer: ComposerProps;
  onRegenerate: () => void;
  onEdit: (
    id: string,
    original: string,
    text: string,
  ) => Promise<string | null>;
};

export function Conversation({
  chatId,
  title,
  messages,
  composer,
  onRegenerate,
  onEdit,
}: ConversationProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const scroller = useRef<HTMLDivElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const following = useRef(!location.hash);
  const handledTarget = useRef("");
  const previousUser = useRef<string | undefined>(undefined);
  const [away, setAway] = useState(false);
  const latestReplyId = messages.findLast((m) => m.role === "assistant")?.id;
  const latestUserId = messages.findLast((m) => m.role === "user")?.id;
  const questions = messages.filter(
    (m) => m.role === "user" && /^\d+$/.test(m.id),
  );
  const targetId = location.hash.startsWith("#message-")
    ? location.hash.slice(9)
    : "";
  const missing = Boolean(
    targetId && messages.length && !messages.some((m) => m.id === targetId),
  );

  function handleScroll() {
    const element = scroller.current!;
    following.current =
      element.scrollHeight - element.scrollTop - element.clientHeight <
      FOLLOW_DISTANCE;
    setAway(!following.current);
  }

  function jumpToLatest() {
    following.current = true;
    scroller.current!.scrollTop = scroller.current!.scrollHeight;
    setAway(false);
  }

  useEffect(() => {
    const element = scroller.current!;
    const targetKey = location.key + location.hash;
    if (targetId && messages.length && handledTarget.current !== targetKey) {
      handledTarget.current = targetKey;
      following.current = false;
      const target = document.getElementById(`message-${targetId}`);
      if (target) {
        target.scrollIntoView({ block: "start", behavior: "instant" });
        target.focus({ preventScroll: true });
        target.animate(
          [
            { backgroundColor: "var(--color-highlight)" },
            { backgroundColor: "transparent" },
          ],
          {
            duration: matchMedia("(prefers-reduced-motion: reduce)").matches
              ? 0
              : 1600,
          },
        );
      }
    } else {
      const newestUser = messages.findLast((m) => m.role === "user")?.id;
      if (newestUser === "pending-user" && previousUser.current !== newestUser)
        following.current = true;
      if (following.current) element.scrollTop = element.scrollHeight;
      previousUser.current = newestUser;
    }
    const observer = new ResizeObserver(() => {
      if (following.current) element.scrollTop = element.scrollHeight;
    });
    observer.observe(content.current!);
    return () => observer.disconnect();
  }, [messages, location.key, location.hash, targetId]);

  function goToQuestion(id: string) {
    navigate({ pathname: location.pathname, hash: `message-${id}` });
  }

  return (
    <div className={styles.conversation}>
      {composer.onQuote && (
        <SelectionAction key={location.key} onQuote={composer.onQuote} />
      )}
      <header className={styles.header}>
        <h1 className={styles.title}>{title}</h1>
        <div className={styles.tools}>
          <ChatUsage chatId={chatId} replying={composer.busy} />
          <DropdownMenu.Root>
            <DropdownMenu.Trigger className={styles.navigation}>
              Questions
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content
                className={styles.questionMenu}
                align="end"
                sideOffset={12}
                onCloseAutoFocus={(event) => {
                  if (document.activeElement?.id.startsWith("message-"))
                    event.preventDefault();
                }}
              >
                {questions.map((question, index) => (
                  <DropdownMenu.Item
                    key={question.id}
                    className={styles.questionItem}
                    onSelect={() => goToQuestion(question.id)}
                  >
                    {index + 1}.{" "}
                    {question.content.trim().slice(0, 90) ||
                      question.documents?.[0]?.name ||
                      "Image question"}
                  </DropdownMenu.Item>
                ))}
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        </div>
      </header>
      {missing && (
        <div className={styles.missing} role="status">
          This message is no longer available in this chat.
        </div>
      )}
      <div className={styles.scroller} ref={scroller} onScroll={handleScroll}>
        <div className={styles.messages} ref={content}>
          {messages.map((message) => (
            <div
              key={message.id}
              id={`message-${message.id}`}
              tabIndex={-1}
              className={`${styles.messageTarget} ${message.role === "user" ? styles.userTarget : ""}`}
            >
              <Message
                message={message}
                isLatestReply={message.id === latestReplyId}
                onRegenerate={composer.busy ? undefined : onRegenerate}
                isLatestUser={message.id === latestUserId}
                onEdit={onEdit}
                editingDisabled={composer.busy || composer.waitingForNotes}
              />
            </div>
          ))}
        </div>
      </div>
      <div className={styles.dock}>
        {away && (
          <button className={styles.latest} onClick={jumpToLatest}>
            <ArrowDown size={16} aria-hidden="true" />
            Jump to latest
          </button>
        )}
        <MessageBox composer={composer} />
      </div>
    </div>
  );
}
