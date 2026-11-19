// The collapsed "Sources (n)" panel under a notes answer. Opened, each slide or
// page the answer used is drawn as a small slide: the module as a tag, the file
// name, and "Slide 8" or "Page 4" in display type. The row scrolls sideways
// inside itself, and is still a list for screen readers, each card reading file,
// module, then slide.
import { ChevronRight } from "lucide-react";
import type { Source } from "./types";
import styles from "./Sources.module.css";

type SourcesProps = {
  sources: Source[];
};

export function Sources({ sources }: SourcesProps) {
  return (
    <details className={styles.sources}>
      <summary className={styles.summary}>
        <ChevronRight size={14} className={styles.chevron} />
        {/* Two small slides, one over the other, like the app's mark. */}
        <span className={styles.deck} aria-hidden="true">
          <i />
          <i />
        </span>
        Sources ({sources.length})
      </summary>
      {/* Focusable, so the arrow keys scroll a long row. */}
      <ul className={styles.slides} tabIndex={0} aria-label="Sources">
        {sources.map((source) => (
          <li
            key={`${source.fileName}-${source.number}`}
            className={styles.slide}
          >
            <span className={styles.slideFile}>{source.fileName}</span>
            <span className={styles.slideModule}>{source.module}</span>
            <span className={styles.slideNumber}>
              {source.location === "slide" ? "Slide" : "Page"} {source.number}
            </span>
          </li>
        ))}
      </ul>
    </details>
  );
}
