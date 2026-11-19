// The state of the open conversation: its messages, sending a message,
// stopping a reply, and regenerating or retrying one.
//
// The saved messages live on the server. While a reply streams, this keeps a
// local copy that grows token by token; when the reply ends, the server's
// saved version replaces it.
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import {
  ApiError,
  getChat,
  streamReply,
  toChatMessage,
  type DocumentUpload,
  type ImageUpload,
  type StreamEvent,
} from "../api/client";
import { glideMessageBox } from "../design/glide";
import type { ChatMessage, QuotedContext } from "./types";

// Ids for messages that exist only until the server confirms them.
const PENDING_USER = "pending-user";
const PENDING_REPLY = "pending-reply";

const SERVER_UNREACHABLE =
  "Couldn't reach the AskMyNotes server. Check that it is still running, then try again.";

// After Stop, the server needs a moment to save the partial reply.
const SAVE_DELAY_MS = 300;

export function useConversation(routeChatId: string | undefined) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const [chatId, setChatIdState] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [quotedContext, setQuotedContext] = useState<QuotedContext | null>(
    null,
  );
  const [sendError, setSendError] = useState<string | null>(null);

  // Async code needs the latest chat id, not the one from when it started.
  const chatIdRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const setChatId = useCallback((id: string | null) => {
    chatIdRef.current = id;
    setChatIdState(id);
  }, []);

  const refreshChatList = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ["chats"] }),
    [queryClient],
  );

  const loadChat = useCallback(
    async (id: string) => {
      try {
        const chat = await getChat(id);
        if (chatIdRef.current === id) setMessages(chat.messages);
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          navigate("/", { replace: true });
        } else if (chatIdRef.current === id) {
          setMessages([failedMessage(SERVER_UNREACHABLE)]);
        }
      }
    },
    [navigate],
  );

  /** Shows a saved chat: blank first, then its messages once they arrive. */
  const openChat = useCallback(
    async (id: string | null) => {
      setChatId(id);
      setQuotedContext(null);
      setSendError(null);
      setMessages([]);
      if (id !== null) await loadChat(id);
    },
    [setChatId, loadChat],
  );

  // Follow the address bar: opening another chat (or a new one) replaces
  // whatever is showing and stops any reply still being written. This is
  // also what loads a chat when the page is opened or refreshed on its address.
  useEffect(() => {
    const wanted = routeChatId ?? null;
    // A chat we just created from the new chat screen is already showing.
    if (wanted === chatIdRef.current) return;
    abortRef.current?.abort();
    void openChat(wanted);
  }, [routeChatId, openChat]);

  const applyEvent = useCallback(
    async (event: StreamEvent) => {
      switch (event.type) {
        case "start": {
          const showMessage = () => {
            setChatId(event.chat.id);
            setMessages((current) =>
              current.some((m) => m.id === PENDING_USER)
                ? current.map((m) =>
                    m.id === PENDING_USER
                      ? toChatMessage(event.userMessage)
                      : m,
                  )
                : [
                    ...current,
                    toChatMessage(event.userMessage),
                    pendingReply(),
                  ],
            );
          };
          // The first message of a new chat swaps the new chat screen for the
          // conversation, so the message box glides down. Waiting for that
          // change keeps the events that follow in order.
          if (chatIdRef.current === null) await glideMessageBox(showMessage);
          else showMessage();
          navigate(`/chat/${event.chat.id}`);
          void refreshChatList();
          break;
        }
        case "accepted":
          setMessages((current) => {
            const index = current.findIndex(
              (message) => String(message.id) === String(event.userMessage.id),
            );
            const kept = index < 0 ? current : current.slice(0, index);
            return [...kept, toChatMessage(event.userMessage), pendingReply()];
          });
          void refreshChatList();
          break;
        case "searching":
          setMessages((current) =>
            current.map((m) =>
              m.id === PENDING_REPLY ? { ...m, searching: event.kind } : m,
            ),
          );
          break;
        case "token":
          // The answer carrying on means any search has finished.
          setMessages((current) =>
            current.map((m) =>
              m.id === PENDING_REPLY
                ? {
                    ...m,
                    content: m.content + event.text,
                    searching: undefined,
                  }
                : m,
            ),
          );
          break;
        case "title":
          void refreshChatList();
          break;
        case "done":
        case "error":
          setMessages((current) =>
            current.map((m) =>
              m.id === PENDING_REPLY ? toChatMessage(event.message) : m,
            ),
          );
          break;
      }
    },
    [navigate, refreshChatList, setChatId],
  );

  /** Reads one streamed reply to the end, however it ends. */
  const runStream = useCallback(
    async (
      open: (signal: AbortSignal) => AsyncGenerator<StreamEvent>,
      onAcceptance?: (accepted: boolean) => void,
      showSendError = true,
      verifyInterruptedEdit?: () => Promise<boolean>,
    ) => {
      let accepted = false;
      const controller = new AbortController();
      let originId = chatIdRef.current;
      abortRef.current = controller;
      setBusy(true);
      try {
        for await (const event of open(controller.signal)) {
          if (!controller.signal.aborted) {
            if (event.type === "start" || event.type === "accepted") {
              originId = event.chat.id;
              accepted = true;
              if (event.type === "start") setQuotedContext(null);
              onAcceptance?.(true);
            }
            await applyEvent(event);
          }
        }
      } catch (error) {
        if (controller.signal.aborted) {
          if (chatIdRef.current === originId) await settleAfterStop(originId);
        } else if (onAcceptance && !accepted) {
          const savedEdit =
            !(error instanceof ApiError) && verifyInterruptedEdit
              ? await verifyInterruptedEdit()
              : false;
          if (savedEdit) {
            accepted = true;
            onAcceptance(true);
          } else {
            if (showSendError) setSendError(describe(error));
            setMessages((current) =>
              current.filter(
                (m) => m.id !== PENDING_USER && m.id !== PENDING_REPLY,
              ),
            );
          }
        } else {
          setMessages((current) =>
            current.map((m) =>
              m.id === PENDING_REPLY ? failedMessage(describe(error)) : m,
            ),
          );
        }
      } finally {
        if (!accepted) onAcceptance?.(false);
        if (abortRef.current === controller) {
          abortRef.current = null;
          setBusy(false);
        }
        void refreshChatList();
        // The reply (and its title) may have cost something.
        void queryClient.invalidateQueries({ queryKey: ["usage"] });
      }

      // The server saves what was written so far; show the saved version.
      async function settleAfterStop(id: string | null) {
        setMessages((current) =>
          current.map((m) =>
            m.id === PENDING_REPLY
              ? { ...m, id: "stopped-reply", status: "stopped" }
              : m,
          ),
        );
        if (id === null) return;
        await new Promise((resolve) => setTimeout(resolve, SAVE_DELAY_MS));
        if (chatIdRef.current === id) await loadChat(id);
      }
    },
    [applyEvent, loadChat, queryClient, refreshChatList],
  );

  const send = useCallback(
    (
      text: string,
      images: ImageUpload[] = [],
      documents: DocumentUpload[] = [],
      usePython = false,
    ) => {
      if (busy) return Promise.resolve(false);
      setSendError(null);
      // Keep the new-chat composer mounted until acceptance, so refusal keeps its draft.
      if (chatIdRef.current !== null)
        setMessages((current) => [
          ...current,
          {
            id: PENDING_USER,
            role: "user",
            content: text,
            quotedContext,
            status: "complete",
            pythonRequested: usePython,
            // Shown straight away from the bytes; the server's copy replaces it.
            images: images.map((i) => `data:${i.mediaType};base64,${i.data}`),
          },
          pendingReply(),
        ]);
      return new Promise<boolean>((resolve) => {
        void runStream(
          (signal) =>
            streamReply(
              "/api/chats/send",
              {
                chatId: chatIdRef.current,
                text,
                images,
                documents,
                quotedContext,
                usePython,
              },
              signal,
            ),
          resolve,
        );
      });
    },
    [busy, runStream, quotedContext],
  );

  /** Replaces the latest reply with a new one. Also what "Retry" does. */
  const regenerate = useCallback(() => {
    if (busy) return;
    const id = chatIdRef.current;
    if (id === null) return;
    setMessages((current) => {
      const last = current.at(-1);
      const kept = last?.role === "assistant" ? current.slice(0, -1) : current;
      return [...kept, pendingReply()];
    });
    void runStream((signal) =>
      streamReply(`/api/chats/${id}/regenerate`, undefined, signal),
    );
  }, [busy, runStream]);

  const edit = useCallback(
    (messageId: string, originalText: string, text: string) => {
      if (busy || routeChatId == null)
        return Promise.resolve("Another action is active.");
      return new Promise<string | null>((resolve) => {
        let settled = false;
        void runStream(
          (signal) =>
            streamReply(
              `/api/chats/${routeChatId}/messages/${messageId}/edit`,
              {
                text,
                expectedLatestMessageId: Number(messageId),
                expectedOriginalText: originalText,
              },
              signal,
            ),
          (accepted) => {
            if (settled) return;
            settled = true;
            resolve(
              accepted
                ? null
                : "The edit was not saved. Reload the chat if it has changed, then try again.",
            );
          },
          false,
          async () => {
            await new Promise((resolve) => setTimeout(resolve, SAVE_DELAY_MS));
            try {
              const saved = await getChat(routeChatId);
              if (chatIdRef.current === routeChatId)
                setMessages(saved.messages);
              return saved.messages.some(
                (message) =>
                  message.id === messageId && message.content === text,
              );
            } catch {
              return false;
            }
          },
        );
      });
    },
    [busy, routeChatId, runStream],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  return {
    chatId,
    messages,
    busy,
    send,
    regenerate,
    stop,
    quotedContext,
    setQuotedContext,
    sendError,
    edit,
  };
}

function pendingReply(): ChatMessage {
  return {
    id: PENDING_REPLY,
    role: "assistant",
    content: "",
    status: "complete",
    streaming: true,
  };
}

function failedMessage(error: string): ChatMessage {
  return {
    id: "failed-reply",
    role: "assistant",
    content: "",
    status: "error",
    error,
  };
}

function describe(error: unknown): string {
  return error instanceof ApiError ? error.message : SERVER_UNREACHABLE;
}
