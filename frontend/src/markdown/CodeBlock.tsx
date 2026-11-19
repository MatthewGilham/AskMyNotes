// A fenced code block. Ordinary code gets the language's name at the top left, a
// Copy button at the top right (a real button, so the keyboard reaches it) and
// the highlighted code. A ```mermaid block is drawn as a diagram and a ```chart
// block as a chart, once they have finished arriving.
import { Check, Copy } from "lucide-react";
import { lazy, Suspense, useContext, useState, type ReactNode } from "react";
import { Diagram, Drawing } from "./Diagram";
import { OpenFence } from "./openFence";
import styles from "./CodeBlock.module.css";

// Charts are drawn by a large library, which is only fetched when needed.
const Chart = lazy(() =>
  import("./Chart").then((module) => ({ default: module.Chart })),
);

// The part of react-markdown's syntax-tree node that is needed here.
type TreeNode = {
  type?: string;
  value?: string;
  tagName?: string;
  properties?: { className?: string[] };
  children?: TreeNode[];
  position?: { start: { line: number } };
};

type CodeBlockProps = {
  node?: TreeNode;
  children?: ReactNode;
};

function textOf(node: TreeNode): string {
  if (node.type === "text") return node.value ?? "";
  return (node.children ?? []).map(textOf).join("");
}

function languageOf(node: TreeNode | undefined): string {
  const classes = node?.properties?.className ?? [];
  const tag = classes.find((name) => name.startsWith("language-"));
  return tag ? tag.slice("language-".length) : "text";
}

export function CodeBlock({ node, children }: CodeBlockProps) {
  const openLine = useContext(OpenFence);
  const code = node?.children?.[0];
  // The syntax tree ends a fenced block's text with a line break that isn't
  // part of the code.
  const text = code ? textOf(code).replace(/\n$/, "") : "";
  const language = languageOf(code);

  if (language === "mermaid" || language === "chart") {
    // Still being written: wait for the closing fence.
    if (openLine !== null && node?.position?.start.line === openLine)
      return <Drawing />;
    if (language === "mermaid") return <Diagram source={text} />;
    return (
      <Suspense fallback={<Drawing />}>
        <Chart json={text} />
      </Suspense>
    );
  }
  return (
    <PlainCodeBlock text={text} language={language}>
      {children}
    </PlainCodeBlock>
  );
}

function PlainCodeBlock({
  text,
  language,
  children,
}: {
  text: string;
  language: string;
  children: ReactNode;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className={styles.block}>
      <div className={styles.header}>
        <span className={styles.language}>{language}</span>
        <button
          type="button"
          className={styles.copy}
          onClick={() => void copy()}
          aria-label={copied ? "Copied" : `Copy ${language} code`}
        >
          {copied ? <Check size={14} /> : <Copy size={14} />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className={styles.body}>{children}</pre>
    </div>
  );
}
