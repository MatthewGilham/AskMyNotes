// The discreet notes status at the bottom of the sidebar: whether the notes
// are up to date or being updated (with progress), any files that couldn't be
// read, any skipped because another app had them open, an error if the last
// update couldn't finish, and "Refresh notes".
import { RefreshCw } from "lucide-react";
import type { NotesStatusData } from "../api/client";
import styles from "./NotesStatus.module.css";

type NotesStatusProps = {
  /** Undefined until the first status has arrived from the server. */
  status: NotesStatusData | undefined;
  onRefresh: () => void;
};

function describe(status: NotesStatusData | undefined): string {
  if (status === undefined) return "Checking your notes…";
  if (status.updating && status.total === 0) {
    return "Checking your notes for changes…";
  }
  if (status.updating) {
    return `Updating notes: ${status.new} new, ${status.changed} changed, ${status.deleted} deleted`;
  }
  if (status.error) return "Your notes didn't finish updating";
  const files = status.fileCount === 1 ? "file" : "files";
  return `Notes up to date · ${status.fileCount} ${files}`;
}

export function NotesStatus({ status, onRefresh }: NotesStatusProps) {
  const updating = status === undefined || status.updating;
  const failed = !updating && status.error !== null;
  const dotStyle = updating
    ? styles.dotUpdating
    : failed
      ? styles.dotFailed
      : "";

  return (
    <div className={styles.notes}>
      <div className={styles.row}>
        <span className={`${styles.dot} ${dotStyle}`} />
        <span className={styles.label}>{describe(status)}</span>
        <button
          className={styles.refresh}
          disabled={updating}
          onClick={onRefresh}
          title="Refresh notes"
        >
          <RefreshCw size={14} className={updating ? styles.spinning : ""} />
        </button>
      </div>

      {status?.updating && status.total > 0 && (
        <div className={styles.track}>
          <div
            className={styles.bar}
            style={{ width: `${(status.done / status.total) * 100}%` }}
          />
        </div>
      )}

      {failed && (
        <div className={styles.error} role="alert">
          {status.error}
        </div>
      )}

      {status && !status.updating && status.inUse.length > 0 && (
        <div className={styles.inUse}>
          {status.inUse.length === 1
            ? `Skipped because it's open in another app: ${status.inUse[0]}. Close it, then refresh.`
            : `Skipped because they're open in another app: ${status.inUse.join(", ")}. Close them, then refresh.`}
        </div>
      )}

      {status && !status.updating && status.unreadable.length > 0 && (
        <details className={styles.unreadable}>
          <summary>
            {status.unreadable.length} file
            {status.unreadable.length === 1 ? "" : "s"} couldn't be read
          </summary>
          <ul>
            {status.unreadable.map((file) => (
              <li key={`${file.module}/${file.fileName}`}>
                <span className={styles.fileName}>
                  {file.module} · {file.fileName}
                </span>
                <span className={styles.reason}>{file.reason}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
