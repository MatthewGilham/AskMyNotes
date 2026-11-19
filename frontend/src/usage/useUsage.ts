// The cost and context numbers from the server. Every query here shares the
// "usage" key, so one invalidation (after a reply, an edit, a deleted chat or a
// notes update) refreshes them all. Nothing ticks while a reply streams.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { getChatUsage, getTotalUsage } from "../api/client";

/**
 * One chat's cost and context. While a reply is being written the numbers are
 * left alone (`paused`): they only change once it ends, and asking mid-reply
 * could read them before the reply has been recorded.
 */
export function useChatUsage(chatId: string | null, paused: boolean) {
  return useQuery({
    queryKey: ["usage", "chat", chatId],
    queryFn: () => getChatUsage(chatId!),
    enabled: chatId !== null && !paused,
  });
}

/** The all-chats total. Notes updates cost money too, so it reloads when one ends. */
export function useTotalUsage(notesUpdating: boolean) {
  const queryClient = useQueryClient();
  useEffect(() => {
    if (!notesUpdating)
      void queryClient.invalidateQueries({ queryKey: ["usage"] });
  }, [notesUpdating, queryClient]);
  return useQuery({ queryKey: ["usage", "total"], queryFn: getTotalUsage });
}
