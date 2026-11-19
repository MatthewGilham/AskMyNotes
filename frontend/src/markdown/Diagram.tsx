// Draws a Mermaid diagram from the model's text, in the colours of the theme in
// use, and draws it again when the theme changes.
//
// Mermaid is large, so it is only fetched (a separate file) when a reply
// actually contains a diagram. It runs with `securityLevel: "strict"`, which
// stops a diagram containing HTML or clickable parts. A diagram that won't draw
// shows its source with a muted note. "Show source" and Copy are always there.
import { Check, Code, Copy } from "lucide-react";
import { useEffect, useId, useState } from "react";
import { useTheme } from "../design/useTheme";
import styles from "./Diagram.module.css";

type Drawing =
  | { state: "drawing" }
  | { state: "ready"; svg: string }
  | {
      state: "failed";
      reason: string;
    };

/** A colour token from tokens.css, as the browser resolves it. */
function token(name: string): string {
  return getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
}

/** Mermaid's twelve section colours, all the theme's raised surface with an
 * accent edge, so each section of a timeline reads as one of the app's boxes. */
function sectionColours(): Record<string, string> {
  const colours: Record<string, string> = {};
  for (let section = 0; section < 12; section++) {
    colours[`cScale${section}`] = token("--color-raised");
    colours[`cScaleLabel${section}`] = token("--color-text");
    colours[`cScalePeer${section}`] = token("--color-accent");
  }
  return colours;
}

export function Diagram({ source }: { source: string }) {
  const [drawing, setDrawing] = useState<Drawing>({ state: "drawing" });
  const [showSource, setShowSource] = useState(false);
  const [copied, setCopied] = useState(false);
  // Mermaid wants an id that is a valid CSS name; React's has colons in it.
  const id = `diagram-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  // Mermaid bakes the colours into the picture, so a new theme means a redraw.
  const theme = useTheme();

  useEffect(() => {
    let current = true;
    async function draw() {
      try {
        const { default: mermaid } = await import("mermaid");
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          suppressErrorRendering: true,
          theme: "base",
          themeVariables: {
            darkMode: true,
            background: token("--color-surface"),
            primaryColor: token("--color-raised"),
            primaryTextColor: token("--color-text"),
            primaryBorderColor: token("--color-accent"),
            // A plain accent edge; Mermaid would otherwise fade it to grey.
            useGradient: false,
            lineColor: token("--color-muted"),
            secondaryColor: token("--color-surface"),
            tertiaryColor: token("--color-sidebar"),
            noteBkgColor: token("--color-raised"),
            noteTextColor: token("--color-text"),
            // Labels on lines sit on the box's own colour, not black.
            edgeLabelBackground: token("--color-surface"),
            fontFamily: token("--font-body"),
            // Timelines colour each section from this scale; without it they
            // are black boxes.
            ...sectionColours(),
          },
        });
        const { svg } = await mermaid.render(id, source);
        if (current) setDrawing({ state: "ready", svg });
      } catch (error) {
        if (current)
          setDrawing({
            state: "failed",
            reason: error instanceof Error ? error.message : "unknown error",
          });
      }
    }
    void draw();
    return () => {
      current = false;
    };
  }, [id, source, theme]);

  async function copy() {
    await navigator.clipboard.writeText(source);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  const failed = drawing.state === "failed";
  return (
    <figure className={styles.diagram} data-no-quote>
      <div className={styles.toolbar}>
        <button
          type="button"
          className={styles.button}
          aria-pressed={showSource || failed}
          disabled={failed}
          onClick={() => setShowSource((shown) => !shown)}
        >
          <Code size={14} />
          {showSource || failed ? "Hide source" : "Show source"}
        </button>
        <button
          type="button"
          className={styles.button}
          onClick={() => void copy()}
          aria-label={copied ? "Copied" : "Copy diagram source"}
        >
          {copied ? <Check size={14} /> : <Copy size={14} />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      {drawing.state === "drawing" && (
        <div className={styles.placeholder} role="status">
          Drawing…
        </div>
      )}
      {drawing.state === "ready" && (
        <div
          className={styles.picture}
          role="img"
          aria-label="Diagram"
          // Mermaid's own output, drawn in strict mode (which sanitises it).
          dangerouslySetInnerHTML={{ __html: drawing.svg }}
        />
      )}
      {(showSource || failed) && <pre className={styles.source}>{source}</pre>}
      {failed && <div className={styles.note}>Couldn't draw this diagram.</div>}
    </figure>
  );
}

/** Shown while a diagram or chart is still being written. */
export function Drawing() {
  return (
    <div className={styles.placeholder} role="status" data-no-quote>
      Drawing…
    </div>
  );
}
