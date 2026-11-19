// A compact chip for an attached document: an icon, its name and a short detail
// ("12 pages", "1.2 MB"). In the message box it has a remove button; in a sent
// message it is only a label.
import { FileSpreadsheet, FileText, Presentation, X } from "lucide-react";
import type { ComponentProps } from "react";
import type { DocumentInfo } from "./types";
import styles from "./DocumentChip.module.css";

const MAX_NAME_LENGTH = 32;

/** Long names keep their start and their ending (the file type), not the middle. */
export function shortenMiddle(name: string) {
  if (name.length <= MAX_NAME_LENGTH) return name;
  return `${name.slice(0, 20)}…${name.slice(-10)}`;
}

/** What to show beside a saved document's name. */
export function describeDocument({ kind, count }: DocumentInfo) {
  if (kind === "document" || count === null) return "Word document";
  const noun = { page: "page", slide: "slide", sheet: "sheet" }[kind];
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

export function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

type DocumentChipProps = {
  name: string;
  detail: string;
  /** Guides the icon: a spreadsheet, a presentation or a text document. */
  icon: "sheet" | "slide" | "text";
  onRemove?: () => void;
};

const ICONS = {
  sheet: FileSpreadsheet,
  slide: Presentation,
  text: FileText,
};

/** The icon for a file chosen in the message box, from its name. */
export function iconForName(name: string): DocumentChipProps["icon"] {
  const lower = name.toLowerCase();
  if (/\.xlsx?$/.test(lower)) return "sheet";
  if (/\.pptx?$/.test(lower)) return "slide";
  return "text";
}

/** The icon for a file, chosen from its name. */
export function FileIcon({
  name,
  ...props
}: { name: string } & ComponentProps<typeof FileText>) {
  const Icon = ICONS[iconForName(name)];
  return <Icon {...props} />;
}

export function DocumentChip({
  name,
  detail,
  icon,
  onRemove,
}: DocumentChipProps) {
  const Icon = ICONS[icon];
  return (
    <div className={styles.chip} title={name}>
      <Icon size={16} aria-hidden="true" className={styles.icon} />
      <span className={styles.name}>{shortenMiddle(name)}</span>
      <span className={styles.detail}>{detail}</span>
      {onRemove && (
        <button
          className={styles.remove}
          onClick={onRemove}
          aria-label={`Remove ${name}`}
          title={`Remove ${name}`}
        >
          <X size={12} />
        </button>
      )}
    </div>
  );
}
