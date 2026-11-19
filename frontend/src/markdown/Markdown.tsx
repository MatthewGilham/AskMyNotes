// Renders a reply as Markdown: headings, lists, tables, highlighted code and
// maths, with its boxes drawn as they should be:
//   - "Beyond your notes" (red) and "From the web" (blue), which say where
//     something came from;
//   - four callouts (Key formula, Exam tip, Common mistake, Worked example),
//     which only pick out the important parts, and can sit inside either of
//     the boxes above without replacing their labels.
// Every link opens in a new tab, and the links in a web box are drawn as small
// pills showing the page's site.
import {
  Lightbulb,
  NotebookPen,
  Sigma,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";
import type { ComponentProps } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { CodeBlock } from "./CodeBlock";
import { splitReplyBlocks, type Callout, type ReplyNode } from "./replyBlocks";
import { convertMathDelimiters } from "./mathDelimiters";
import { OpenFence, openFenceLine } from "./openFence";
import styles from "./Markdown.module.css";

type MarkdownProps = {
  content: string;
  /** The reply is still being written, so an unfinished diagram or chart
   * isn't drawn yet. */
  streaming?: boolean;
};

const CALLOUTS: Record<
  Callout,
  { label: string; Icon: LucideIcon; className: string }
> = {
  formula: { label: "Key formula", Icon: Sigma, className: styles.formula },
  tip: { label: "Exam tip", Icon: Lightbulb, className: styles.tip },
  mistake: {
    label: "Common mistake",
    Icon: TriangleAlert,
    className: styles.mistake,
  },
  example: {
    label: "Worked example",
    Icon: NotebookPen,
    className: styles.example,
  },
};

export function Markdown({ content, streaming = false }: MarkdownProps) {
  const nodes = splitReplyBlocks(convertMathDelimiters(content));
  return (
    // data-streaming: the stylesheet draws a blinking caret after the last of
    // the text while the reply is being written.
    <div className={styles.markdown} data-streaming={streaming || undefined}>
      <Nodes nodes={nodes} streaming={streaming} />
    </div>
  );
}

function Nodes({
  nodes,
  streaming,
  citations = false,
}: {
  nodes: ReplyNode[];
  streaming: boolean;
  citations?: boolean;
}) {
  return (
    <>
      {nodes.map((node, index) => {
        switch (node.kind) {
          case "markdown":
            return (
              <MarkdownPart
                key={index}
                markdown={node.markdown}
                streaming={streaming}
                citations={citations}
              />
            );
          case "beyond":
            return (
              <aside key={index} className={styles.beyond}>
                <div className={styles.beyondLabel}>Beyond your notes</div>
                <Nodes nodes={node.children} streaming={streaming} />
              </aside>
            );
          case "web":
            return (
              <aside key={index} className={styles.web}>
                <div className={styles.webLabel}>From the web</div>
                <Nodes nodes={node.children} streaming={streaming} citations />
              </aside>
            );
          default: {
            const { label, Icon, className } = CALLOUTS[node.kind];
            return (
              <aside
                key={index}
                className={`${styles.callout} ${className}`}
                aria-label={label}
              >
                <div className={styles.calloutLabel}>
                  <Icon size={14} aria-hidden="true" />
                  {label}
                </div>
                <Nodes
                  nodes={node.children}
                  streaming={streaming}
                  citations={citations}
                />
              </aside>
            );
          }
        }
      })}
    </>
  );
}

/** A page's site as shown on a pill: its host without "www.". */
function siteOf(href: string): string {
  try {
    return new URL(href).hostname.replace(/^www\./, "");
  } catch {
    return href;
  }
}

type MarkdownPartProps = {
  markdown: string;
  streaming: boolean;
  /** Draw links as pills showing their site (inside a "From the web" block). */
  citations?: boolean;
};

function isWebAddress(href: string | undefined): href is string {
  return href !== undefined && /^https?:\/\//i.test(href);
}

// Defined once, here, so a streaming reply doesn't remount its links on every
// new piece of text.
function ExternalLink({ href, children }: ComponentProps<"a">) {
  if (!isWebAddress(href)) return <a href={href}>{children}</a>;
  return (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  );
}

function CitationLink({ href, children }: ComponentProps<"a">) {
  if (!isWebAddress(href)) return <a href={href}>{children}</a>;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={styles.citation}
    >
      {siteOf(href)}
    </a>
  );
}

function MarkdownPart({
  markdown,
  streaming,
  citations = false,
}: MarkdownPartProps) {
  return (
    <OpenFence value={streaming ? openFenceLine(markdown) : null}>
      <ReactMarkdown
        remarkPlugins={[
          remarkGfm,
          [remarkMath, { singleDollarTextMath: false }],
        ]}
        // A block with no language isn't guessed at, and an unknown one is left
        // plain.
        rehypePlugins={[
          rehypeKatex,
          [rehypeHighlight, { ignoreMissing: true }],
        ]}
        components={{
          a: citations ? CitationLink : ExternalLink,
          pre: CodeBlock,
        }}
      >
        {markdown}
      </ReactMarkdown>
    </OpenFence>
  );
}
