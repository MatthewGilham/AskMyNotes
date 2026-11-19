// The message box: previews of attached images and chips for attached
// documents, a growing text area, the attach button and the send button. Enter
// sends and Shift+Enter starts a new line. Files can be attached with the
// button or by pasting a screenshot or a copied file.
// While a reply is being written the send button becomes a Stop button and a
// band of light travels round the box's edge, and while the notes are updating
// the box says it's waiting.
import { ArrowUp, Paperclip, Square, Terminal, X } from "lucide-react";
import {
  useRef,
  useState,
  type ClipboardEvent,
  type KeyboardEvent,
} from "react";
import { ACCEPT_ATTRIBUTE } from "./attachments";
import { DocumentChip, formatSize, iconForName } from "./DocumentChip";
import { QuotedPassage } from "./QuotedPassage";
import type { Attachment, QuotedContext } from "./types";
import styles from "./MessageBox.module.css";

/** Everything the message box needs from the screen around it. */
export type ComposerProps = {
  busy: boolean;
  waitingForNotes: boolean;
  attachments: Attachment[];
  attachmentError: string | null;
  onSend: (text: string, usePython?: boolean) => void | Promise<boolean>;
  quotedContext?: QuotedContext | null;
  onQuote?: (quote: QuotedContext | null) => void;
  sendError?: string | null;
  onStop: () => void;
  onAddFiles: (files: File[]) => void;
  onRemoveAttachment: (id: string) => void;
};

type MessageBoxProps = {
  composer: ComposerProps;
  autoFocus?: boolean;
};

export function MessageBox({ composer, autoFocus = false }: MessageBoxProps) {
  const {
    busy,
    waitingForNotes,
    attachments,
    attachmentError,
    onSend,
    onStop,
    onAddFiles,
    onRemoveAttachment,
  } = composer;
  const [text, setText] = useState("");
  // The "Python" button applies to one message, so it switches off after sending.
  const [python, setPython] = useState(false);
  // True while documents are being read by the server, before the reply starts.
  const [reading, setReading] = useState(false);
  const input = useRef<HTMLTextAreaElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const hasContent = text.trim() !== "" || attachments.length > 0;
  const canSend = !busy && !reading && !waitingForNotes && hasContent;
  const images = attachments.filter((attachment) => attachment.isImage);
  const documents = attachments.filter((attachment) => !attachment.isImage);

  async function send() {
    if (!canSend) return;
    setReading(documents.length > 0);
    try {
      const accepted = await onSend(text.trim(), python);
      if (accepted !== false) {
        setText("");
        setPython(false);
      }
    } finally {
      setReading(false);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // isComposing: Enter confirms a word in some input methods; it isn't "send".
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      send();
    }
  }

  function handlePaste(event: ClipboardEvent<HTMLTextAreaElement>) {
    const files = Array.from(event.clipboardData.files);
    // Pasting text still works as normal; only pasted files are intercepted.
    if (files.length > 0) {
      event.preventDefault();
      onAddFiles(files);
    }
  }

  return (
    <div className={`${styles.box} ${waitingForNotes ? styles.waiting : ""}`}>
      {/* The band of light that travels round the edge during a reply. */}
      <span className={styles.charge} aria-hidden="true" />
      {composer.quotedContext && (
        <div>
          <QuotedPassage quote={composer.quotedContext} />
          <div className={styles.quoteActions}>
            <button
              onClick={() => composer.onQuote?.(null)}
              aria-label="Remove excerpt"
            >
              <X size={14} /> Remove
            </button>
            {["Explain this", "Show an example"].map((prompt) => (
              <button
                key={prompt}
                disabled={text.trim() !== ""}
                onClick={() => {
                  setText(prompt);
                  input.current?.focus();
                }}
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      )}
      {composer.sendError && (
        <div className={styles.error} role="alert">
          {composer.sendError}
        </div>
      )}
      {attachmentError && (
        <div className={styles.error} role="alert">
          {attachmentError}
        </div>
      )}

      {attachments.length > 0 && (
        <div className={styles.previews}>
          {images.map((attachment) => (
            <div key={attachment.id} className={styles.preview}>
              <img src={attachment.previewUrl ?? ""} alt={attachment.name} />
              <button
                className={styles.removePreview}
                onClick={() => onRemoveAttachment(attachment.id)}
                title={`Remove ${attachment.name}`}
                aria-label={`Remove ${attachment.name}`}
              >
                <X size={12} />
              </button>
            </div>
          ))}
          {documents.map((attachment) => (
            <DocumentChip
              key={attachment.id}
              name={attachment.name}
              detail={formatSize(attachment.file.size)}
              icon={iconForName(attachment.name)}
              onRemove={() => onRemoveAttachment(attachment.id)}
            />
          ))}
        </div>
      )}
      {reading && (
        <div className={styles.status} role="status">
          Reading files…
        </div>
      )}

      <textarea
        ref={input}
        className={styles.input}
        rows={1}
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        placeholder={
          waitingForNotes
            ? "Waiting for your notes to finish updating…"
            : "Ask anything, or ask about your notes"
        }
        disabled={waitingForNotes}
        autoFocus={autoFocus}
        aria-label="Message"
      />

      <div className={styles.toolbar}>
        <input
          ref={fileInput}
          type="file"
          accept={ACCEPT_ATTRIBUTE}
          multiple
          hidden
          aria-label="Attach files or images"
          onChange={(event) => {
            onAddFiles(Array.from(event.target.files ?? []));
            // Clearing it lets the same file be picked again later.
            event.target.value = "";
          }}
        />
        <div className={styles.tools}>
          <button
            className={styles.attach}
            disabled={waitingForNotes}
            onClick={() => fileInput.current?.click()}
            title="Attach files or images"
          >
            <Paperclip size={18} />
          </button>
          <button
            className={`${styles.python} ${python ? styles.pythonOn : ""}`}
            disabled={waitingForNotes}
            aria-pressed={python}
            onClick={() => setPython(!python)}
            title={
              python
                ? "Python is on for your next message"
                : "Switch on Python for your next message (a small extra cost)"
            }
          >
            <Terminal size={15} />
            Python
          </button>
        </div>
        {busy ? (
          <button className={styles.send} onClick={onStop} title="Stop">
            <Square size={14} fill="currentColor" />
          </button>
        ) : (
          <button
            className={styles.send}
            disabled={!canSend}
            onClick={send}
            title="Send"
          >
            <ArrowUp size={18} strokeWidth={2.5} />
          </button>
        )}
      </div>
    </div>
  );
}
