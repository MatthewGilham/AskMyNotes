// The shapes of chats and messages, as the frontend sees them.

export type ChatSummary = {
  id: string;
  title: string;
  pinned: boolean;
  lastUsedAt: Date;
};

export type Source = {
  fileName: string;
  module: string;
  location: "slide" | "page";
  number: number;
};

/** One web page that a web answer searched for: cited, or read and not cited. */
export type WebSource = {
  title: string;
  /** The page's site, such as "bankofengland.co.uk". */
  site: string;
  url: string;
  /** False for a page the search read and the answer did not cite. */
  cited?: boolean;
};

/**
 * One calculation, or one run of Python, that an answer was worked out with,
 * for the "Working" panel.
 */
export type ToolRun = {
  tool: "calculate" | "solve_equation" | "python";
  /** The expression, or for Python the code. */
  input: string;
  /** The result as text, or why it was refused. For Python, what it printed. */
  result: string;
  ok: boolean;
  inputLatex: string | null;
  resultLatex: string | null;
  /** Python's output was cut to its first lines. */
  truncated?: boolean;
};

/** A file that Python made for an answer. */
export type MessageFile = {
  id: number;
  name: string;
  size: number;
  mediaType: string;
  /** A picture that is shown under the answer; other files are downloads. */
  isImage: boolean;
  url: string;
};

export type MessageStatus = "complete" | "stopped" | "error";

export type QuotedContext = {
  sourceMessageId: number;
  excerpt: string;
};

/** A document attached to a message: what it is and how big. Never its text. */
export type DocumentInfo = {
  name: string;
  kind: "page" | "slide" | "sheet" | "document";
  /** Pages, slides or sheets; null for a Word file, which has no fixed count. */
  count: number | null;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  status: MessageStatus;
  quotedContext?: QuotedContext | null;
  /** For an error reply: what went wrong, in plain English. */
  error?: string;
  /** For a notes answer: the slides and pages it used. */
  sources?: Source[];
  /** For a web answer: the pages it cited and the pages its searches read. */
  webSources?: WebSource[];
  /** For a web answer: what its searches asked for (missing on older answers). */
  webSearches?: string[];
  /** The calculations and Python runs the answer was worked out with. */
  toolRuns?: ToolRun[];
  /** The files Python made for the answer. */
  files?: MessageFile[];
  /** For a question: Python was switched on for it. */
  pythonRequested?: boolean;
  /** Addresses of the images attached to a message from you. */
  images?: string[];
  /** The documents attached to a message from you. */
  documents?: DocumentInfo[];
  /** True while the reply is still being written. */
  streaming?: boolean;
  /** What the agent is searching for this reply, while it is. */
  searching?: "notes" | "web" | "calculator" | "python";
};

/** An image or document chosen but not yet sent. */
export type Attachment = {
  id: string;
  name: string;
  file: File;
  isImage: boolean;
  /** A picture to show before sending; documents have none. */
  previewUrl: string | null;
};
