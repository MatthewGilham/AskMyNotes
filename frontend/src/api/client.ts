// Talks to the Python backend: one function per API route, plus the reader
// for the streamed reply. Names and dates from the server are converted into
// the shapes the rest of the frontend uses (see chat/types.ts).
import type {
  ChatMessage,
  ChatSummary,
  DocumentInfo,
  MessageFile,
  MessageStatus,
  QuotedContext,
  Source,
  ToolRun,
  WebSource,
} from "../chat/types";

// What the server sends, before conversion.
type WireMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
  status: MessageStatus;
  error: string | null;
  sources: Source[] | null;
  webSources?: WebSource[] | null;
  webSearches?: string[] | null;
  toolRuns?: ToolRun[] | null;
  files?: MessageFile[];
  pythonRequested?: boolean;
  images: string[];
  quotedContext?: QuotedContext | null;
  documents?: DocumentInfo[];
};

type WireChatSummary = {
  id: string;
  title: string;
  pinned: boolean;
  lastUsedAt: string;
};

type WireChatDetail = WireChatSummary & { messages: WireMessage[] };

export type StreamEvent =
  | { type: "start"; chat: WireChatSummary; userMessage: WireMessage }
  | { type: "accepted"; chat: WireChatSummary; userMessage: WireMessage }
  | { type: "token"; text: string }
  | {
      type: "searching";
      kind: "notes" | "web" | "calculator" | "python";
    }
  | { type: "title"; title: string }
  | { type: "done"; message: WireMessage }
  | { type: "error"; message: WireMessage };

export type ClientConfig = {
  userName: string;
  examplePrompts: string[];
  maxImagesPerMessage: number;
  maxImageSizeMb: number;
  maxDocumentsPerMessage: number;
  maxDocumentSizeMb: number;
};

/** An image ready to send: its bytes as base64 text. */
export type ImageUpload = {
  name: string;
  mediaType: string;
  data: string;
};

/** A document ready to send: its bytes as base64 text. */
export type DocumentUpload = {
  name: string;
  data: string;
};

export type SearchResult = {
  chatId: string;
  title: string;
  snippet: string;
  messageId: number | null;
};

/** A failed request, with a message that can be shown to the student. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

export function toChatSummary(chat: WireChatSummary): ChatSummary {
  return {
    id: chat.id,
    title: chat.title,
    pinned: chat.pinned,
    lastUsedAt: new Date(chat.lastUsedAt),
  };
}

export function toChatMessage(message: WireMessage): ChatMessage {
  return {
    id: String(message.id),
    role: message.role,
    content: message.content,
    status: message.status,
    error: message.error ?? undefined,
    sources: message.sources ?? undefined,
    webSources: message.webSources ?? undefined,
    webSearches: message.webSearches ?? undefined,
    toolRuns: message.toolRuns ?? undefined,
    files: message.files?.length ? message.files : undefined,
    pythonRequested: message.pythonRequested,
    images: message.images,
    documents: message.documents,
    quotedContext: message.quotedContext,
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

async function describeFailure(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail))
      return body.detail
        .map((item: { msg: string }) => item.msg.replace(/^Value error, /, ""))
        .join(" ");
  } catch {
    // The body wasn't JSON; the status line below is all we have.
  }
  return `The server answered ${response.status} ${response.statusText}`;
}

const jsonHeaders = { "Content-Type": "application/json" };

export const getConfig = () => request<ClientConfig>("/api/config");

export async function listChats(): Promise<ChatSummary[]> {
  return (await request<WireChatSummary[]>("/api/chats")).map(toChatSummary);
}

export async function getChat(
  chatId: string,
): Promise<{ chat: ChatSummary; messages: ChatMessage[] }> {
  const detail = await request<WireChatDetail>(`/api/chats/${chatId}`);
  return {
    chat: toChatSummary(detail),
    messages: detail.messages.map(toChatMessage),
  };
}

export function updateChat(
  chatId: string,
  changes: { title?: string; pinned?: boolean },
): Promise<WireChatSummary> {
  return request(`/api/chats/${chatId}`, {
    method: "PATCH",
    headers: jsonHeaders,
    body: JSON.stringify(changes),
  });
}

export function deleteChat(chatId: string): Promise<void> {
  return request(`/api/chats/${chatId}`, { method: "DELETE" });
}

export function searchChats(query: string): Promise<SearchResult[]> {
  return request(`/api/chats/search?q=${encodeURIComponent(query)}`);
}

/**
 * Starts a reply and yields its events as they arrive. The server streams one
 * JSON object per line, so the text is split into lines as it comes in.
 * Aborting the signal is how the Stop button works.
 */
export async function* streamReply(
  path: string,
  body: object | undefined,
  signal: AbortSignal,
): AsyncGenerator<StreamEvent> {
  const response = await fetch(path, {
    method: "POST",
    headers: jsonHeaders,
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  if (!response.ok || !response.body) {
    throw new ApiError(await describeFailure(response), response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let newline = buffer.indexOf("\n");
    while (newline >= 0) {
      const line = buffer.slice(0, newline);
      buffer = buffer.slice(newline + 1);
      if (line) yield JSON.parse(line) as StreamEvent;
      newline = buffer.indexOf("\n");
    }
  }
}

/** One chat's API cost (US dollars) and context, from GET /api/chats/{id}/usage. */
export type ChatUsageData = {
  cost: number;
  breakdown: {
    replies: number;
    titles: number;
    summaries: number;
    searches: number;
    webSearches: number;
    python: number;
  };
  includesEstimate: boolean;
  earlierCostsUnrecorded: boolean;
  trackingStartedAt: string;
  context: {
    tokens: number;
    budgetTokens: number;
    summarised: boolean;
    overBudget: boolean;
  };
};

/** Everything the app has spent, from GET /api/usage. */
export type TotalUsageData = {
  cost: number;
  chats: number;
  deletedChats: number;
  notesUpdates: number;
  includesEstimate: boolean;
  trackingStartedAt: string;
};

export const getChatUsage = (chatId: string) =>
  request<ChatUsageData>(`/api/chats/${chatId}/usage`);

export const getTotalUsage = () => request<TotalUsageData>("/api/usage");

/** What the notes sync is doing, from GET /api/notes/status. */
export type NotesStatusData = {
  updating: boolean;
  new: number;
  changed: number;
  deleted: number;
  done: number;
  total: number;
  fileCount: number;
  unreadable: { module: string; fileName: string; reason: string }[];
  /** Ids ("module/file") of files skipped because another app had them open. */
  inUse: string[];
  error: string | null;
};

export const getNotesStatus = () =>
  request<NotesStatusData>("/api/notes/status");

export const refreshNotes = () =>
  request<NotesStatusData>("/api/notes/refresh", { method: "POST" });
