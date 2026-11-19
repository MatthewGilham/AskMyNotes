// The same expandable excerpt preview is used before sending and in saved questions.
import { Markdown } from "../markdown/Markdown";
import type { QuotedContext } from "./types";
import styles from "./QuotedPassage.module.css";

export function QuotedPassage({ quote }: { quote: QuotedContext }) {
  const passage = <Markdown content={quote.excerpt} />;
  return (
    <div className={styles.quote}>
      <div className={styles.label}>Regarding</div>
      {quote.excerpt.length > 350 ? (
        <details>
          <summary>
            Quoted passage ({Array.from(quote.excerpt).length} characters):
            Expand passage
          </summary>
          {passage}
        </details>
      ) : (
        passage
      )}
    </div>
  );
}
