// The collapsed "Found online (3 cited, 5 searched)" panel under a web answer:
// what the agent searched for, the pages the answer cited, and the pages the
// search read that the answer did not cite. Every link opens in a new tab.
import { ChevronRight, ExternalLink, Globe, Search } from "lucide-react";
import type { ReactNode } from "react";
import type { WebSource } from "./types";
import styles from "./Sources.module.css";

type FoundOnlineProps = {
  /** What the searches asked for. Missing for answers saved before the panel. */
  searches: string[] | undefined;
  pages: WebSource[];
};

export function FoundOnline({ searches, pages }: FoundOnlineProps) {
  // Pages saved before the panel existed have no `cited` flag: all were cited.
  const cited = pages.filter((page) => page.cited !== false);
  const uncited = pages.filter((page) => page.cited === false);
  const heading =
    searches === undefined
      ? `${cited.length} cited`
      : `${cited.length} cited, ${uncited.length} searched`;
  return (
    <details className={styles.sources}>
      <summary className={`${styles.summary} ${styles.webSummary}`}>
        <ChevronRight size={14} className={styles.chevron} />
        <Globe size={14} className={styles.webIcon} />
        Found online ({heading})
      </summary>
      <div className={styles.list}>
        {searches !== undefined && searches.length > 0 && (
          <Group label="Searched for">
            {searches.map((query) => (
              <li key={query} className={styles.query}>
                <Search size={14} className={styles.webIcon} />
                {query}
              </li>
            ))}
          </Group>
        )}
        {cited.length > 0 && (
          <Group label="Cited in the answer">
            {cited.map((page) => (
              <Page key={page.url} page={page} />
            ))}
          </Group>
        )}
        {uncited.length > 0 && (
          <Group label="Searched, not cited">
            {uncited.map((page) => (
              <Page key={page.url} page={page} muted />
            ))}
          </Group>
        )}
        {pages.length === 0 && (
          <p className={styles.noPages}>No pages were returned.</p>
        )}
      </div>
    </details>
  );
}

function Group({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section className={styles.group} aria-label={label}>
      <h4 className={styles.groupLabel}>{label}</h4>
      <ul className={styles.items}>{children}</ul>
    </section>
  );
}

function Page({ page, muted }: { page: WebSource; muted?: boolean }) {
  return (
    <li className={`${styles.source} ${muted ? styles.mutedPage : ""}`}>
      <Globe size={14} className={styles.webIcon} />
      <a
        className={styles.webLink}
        href={page.url}
        target="_blank"
        rel="noopener noreferrer"
      >
        <span className={styles.fileName}>{page.title}</span>
        <ExternalLink size={12} className={styles.externalIcon} />
      </a>
      <span className={styles.webSite}>{page.site}</span>
    </li>
  );
}
