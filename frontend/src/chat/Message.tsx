// One message in the conversation. Your messages sit in a bubble on the
// right; replies are full width, rendered as Markdown, with their sources,
// a "Stopped" marker if you stopped them, and actions that appear on hover.
// While a reply searches the notes or the web, calculates or runs Python, it
// says so. A failed reply shows an
// amber error with a Retry button under whatever text arrived before it
// failed.
import {
  AlertTriangle,
  Calculator,
  Check,
  CircleStop,
  Copy,
  Globe,
  Pencil,
  RotateCcw,
  Save,
  Search,
  Terminal,
} from "lucide-react";
import { Link } from "react-router";
import { DocumentChip, describeDocument } from "./DocumentChip";
import { QuotedPassage } from "./QuotedPassage";
import { useState, type KeyboardEvent } from "react";
import { Markdown } from "../markdown/Markdown";
import { GeneratedFiles } from "./GeneratedFiles";
import { Sources } from "./Sources";
import { FoundOnline } from "./FoundOnline";
import { Working } from "./Working";
import { hideSourcesLine } from "./sourcesLine";
import { withoutCitationMarkers } from "./citationMarkers";
import type { ChatMessage } from "./types";
import styles from "./Message.module.css";

type MessageProps = {
  message: ChatMessage;
  /** Only the latest reply can be regenerated or retried. */
  isLatestReply: boolean;
  /** Undefined while a reply is being written. */
  onRegenerate?: () => void;
  isLatestUser?: boolean;
  onEdit?: (
    id: string,
    original: string,
    text: string,
  ) => Promise<string | null>;
  editingDisabled?: boolean;
};

export function Message({
  message,
  isLatestReply,
  onRegenerate,
  isLatestUser = false,
  onEdit,
  editingDisabled = false,
}: MessageProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.content);
  const [editError, setEditError] = useState<string | null>(null);
  async function saveEdit() {
    if (!onEdit || draft.trim() === message.content.trim()) return;
    const error = await onEdit(message.id, message.content, draft);
    if (error) setEditError(error);
    else setEditing(false);
  }
  if (message.role === "user") {
    return (
      <div className={styles.user}>
        {message.images && message.images.length > 0 && (
          <div className={styles.userImages}>
            {message.images.map((src) => (
              <img key={src} src={src} alt="Attached" />
            ))}
          </div>
        )}
        {message.documents && message.documents.length > 0 && (
          <div className={styles.userDocuments}>
            {message.documents.map((document, index) => (
              <DocumentChip
                key={`${index}-${document.name}`}
                name={document.name}
                detail={describeDocument(document)}
                icon={
                  document.kind === "sheet"
                    ? "sheet"
                    : document.kind === "slide"
                      ? "slide"
                      : "text"
                }
              />
            ))}
          </div>
        )}
        {message.quotedContext && (
          <>
            <QuotedPassage quote={message.quotedContext} />
            <Link
              className={styles.original}
              to={`#message-${message.quotedContext.sourceMessageId}`}
            >
              Original answer
            </Link>
          </>
        )}
        {editing ? (
          <div className={styles.editor}>
            <textarea
              aria-label="Edit your latest question"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  setDraft(message.content);
                  setEditError(null);
                  setEditing(false);
                }
              }}
              autoFocus
            />
            <div className={styles.editExplanation}>
              Saving replaces the latest answer.
            </div>
            {editError && (
              <div className={styles.editError} role="alert">
                {editError}
              </div>
            )}
            <div className={styles.editButtons}>
              <button
                onClick={() => {
                  setDraft(message.content);
                  setEditError(null);
                  setEditing(false);
                }}
              >
                Cancel
              </button>
              <button
                onClick={() => void saveEdit()}
                disabled={
                  editingDisabled || draft.trim() === message.content.trim()
                }
              >
                <Save size={14} /> Save &amp; resend
              </button>
            </div>
          </div>
        ) : (
          <>
            <div>{message.content}</div>
            {isLatestUser && onEdit && !editingDisabled && (
              <button
                className={styles.editAction}
                aria-label="Edit latest question"
                onClick={() => {
                  setDraft(message.content);
                  setEditError(null);
                  setEditing(true);
                }}
              >
                <Pencil size={14} /> Edit
              </button>
            )}
          </>
        )}
      </div>
    );
  }

  const canRegenerate = isLatestReply && onRegenerate !== undefined;
  // The saved reply has had its sources line taken off already.
  const cleanContent = withoutCitationMarkers(message.content);
  const content = message.streaming
    ? hideSourcesLine(cleanContent)
    : cleanContent;
  const eligible =
    !message.streaming &&
    message.status !== "error" &&
    /^\d+$/.test(message.id) &&
    Boolean(content.trim());
  function selectAnswer(event: KeyboardEvent<HTMLDivElement>) {
    if (
      eligible &&
      (event.ctrlKey || event.metaKey) &&
      event.key.toLowerCase() === "a"
    ) {
      event.preventDefault();
      const range = document.createRange();
      range.selectNodeContents(event.currentTarget);
      const selection = window.getSelection()!;
      selection.removeAllRanges();
      selection.addRange(range);
    }
  }
  return (
    <div className={styles.reply}>
      {content && (
        <div
          data-quote-answer={eligible ? message.id : undefined}
          tabIndex={eligible ? 0 : undefined}
          aria-label={
            eligible
              ? "Answer text; Ctrl+A or Command+A selects this answer"
              : undefined
          }
          onKeyDown={selectAnswer}
        >
          {/* A reply you stopped is no longer being written, even in the
              moment before its saved version arrives. */}
          <Markdown
            content={content}
            streaming={message.streaming && message.status !== "stopped"}
          />
        </div>
      )}

      {message.streaming && message.searching && (
        <SearchingStatus kind={message.searching} />
      )}

      {message.streaming && !message.searching && content === "" && (
        <TypingDots />
      )}

      {message.status === "stopped" && (
        <div className={styles.stopped}>
          <CircleStop size={13} />
          Stopped
        </div>
      )}

      {message.status === "error" && (
        <ErrorNotice
          error={message.error ?? ""}
          onRetry={canRegenerate ? onRegenerate : undefined}
        />
      )}

      {message.files && message.files.length > 0 && (
        <GeneratedFiles files={message.files} />
      )}

      {message.sources && message.sources.length > 0 && (
        <Sources sources={message.sources} />
      )}

      {(message.webSearches !== undefined ||
        (message.webSources?.length ?? 0) > 0) && (
        <FoundOnline
          searches={message.webSearches}
          pages={message.webSources ?? []}
        />
      )}

      {message.toolRuns && message.toolRuns.length > 0 && (
        <Working runs={message.toolRuns} />
      )}

      {!message.streaming && message.status !== "error" && (
        <div className={styles.actions}>
          {content && <CopyButton text={content} />}
          {canRegenerate && (
            <button
              className={styles.action}
              onClick={onRegenerate}
              title="Regenerate"
            >
              <RotateCcw size={15} />
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function TypingDots() {
  return (
    <div className={styles.typing} role="status" aria-label="Writing a reply">
      <span />
      <span />
      <span />
    </div>
  );
}

const SEARCHING = {
  notes: { Icon: Search, text: "Searching your notes…" },
  web: { Icon: Globe, text: "Searching the web…" },
  calculator: { Icon: Calculator, text: "Calculating…" },
  python: { Icon: Terminal, text: "Running Python…" },
};

function SearchingStatus({ kind }: { kind: keyof typeof SEARCHING }) {
  const { Icon, text } = SEARCHING[kind];
  return (
    <div className={styles.searching} role="status">
      <Icon
        size={14}
        className={
          kind === "web" ? styles.searchingWebIcon : styles.searchingIcon
        }
      />
      {text}
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <button
      className={styles.action}
      onClick={copy}
      title={copied ? "Copied" : "Copy"}
    >
      {copied ? <Check size={15} /> : <Copy size={15} />}
    </button>
  );
}

function ErrorNotice({
  error,
  onRetry,
}: {
  error: string;
  onRetry?: () => void;
}) {
  return (
    <div className={styles.error} role="alert">
      <AlertTriangle size={18} className={styles.errorIcon} />
      <div className={styles.errorText}>
        <div className={styles.errorTitle}>The reply didn't come through</div>
        <div>{error}</div>
      </div>
      {onRetry && (
        <button className={styles.retry} onClick={onRetry}>
          <RotateCcw size={14} />
          Retry
        </button>
      )}
    </div>
  );
}
