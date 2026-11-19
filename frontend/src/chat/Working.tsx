// The collapsed "Working (n)" panel under an answer: each calculation the
// agent made, with what it asked and what came back, drawn as maths, and each
// run of Python, with its code and what it printed. A refused calculation shows
// why it was refused.
import { ChevronRight, CircleAlert } from "lucide-react";
import { Markdown } from "../markdown/Markdown";
import type { ToolRun } from "./types";
import sources from "./Sources.module.css";
import styles from "./Working.module.css";

type WorkingProps = {
  runs: ToolRun[];
};

/** LaTeX as a one-line piece of maths, or the plain text if it has none. */
function Maths({
  latex,
  fallback,
}: {
  latex: string | null;
  fallback: string;
}) {
  if (latex === null) return <code>{fallback}</code>;
  return <Markdown content={`\\( ${latex} \\)`} />;
}

/** Code as a fenced block, longer-fenced than any run of backticks inside it. */
function fenced(code: string, language: string): string {
  const longest = Math.max(
    0,
    ...(code.match(/`+/g) ?? []).map((ticks) => ticks.length),
  );
  const fence = "`".repeat(Math.max(3, longest + 1));
  return `${fence}${language}\n${code}\n${fence}`;
}

export function Working({ runs }: WorkingProps) {
  return (
    <details className={sources.sources}>
      <summary className={sources.summary}>
        <ChevronRight size={14} className={sources.chevron} />
        Working ({runs.length})
      </summary>
      <ol className={styles.list}>
        {runs.map((run, index) => (
          <li key={index} className={styles.run}>
            {run.tool === "python" ? (
              <PythonRun run={run} />
            ) : (
              <>
                <div className={styles.input}>
                  <Maths latex={run.inputLatex} fallback={run.input} />
                </div>
                {run.ok ? (
                  <div className={styles.result}>
                    <span className={styles.equals}>=</span>
                    <Maths latex={run.resultLatex} fallback={run.result} />
                  </div>
                ) : (
                  <div className={styles.refused}>
                    <CircleAlert size={14} />
                    Refused: {run.result}
                  </div>
                )}
              </>
            )}
          </li>
        ))}
      </ol>
    </details>
  );
}

function PythonRun({ run }: { run: ToolRun }) {
  return (
    <div className={styles.python}>
      <div className={styles.label}>Python</div>
      <Markdown content={fenced(run.input, "python")} />
      {!run.ok && (
        <div className={styles.refused}>
          <CircleAlert size={14} />
          This run didn't finish.
        </div>
      )}
      {run.result !== "" && (
        <>
          <div className={styles.label}>Output</div>
          <pre className={styles.output} tabIndex={0}>
            {run.result}
          </pre>
        </>
      )}
      {run.truncated && (
        <div className={styles.note}>
          Only the first 200 lines of the output are shown.
        </div>
      )}
    </div>
  );
}
