// Renaming, pinning and deleting chats from the sidebar. Each one changes the
// chat on the server, then reloads the chat list so the sidebar shows it.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { deleteChat, updateChat } from "../api/client";

export function useChatActions(openChatId: string | null) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  // The chat list and chat searches share the "chats" key, so one call
  // refreshes both.
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["chats"] });

  const rename = useMutation({
    mutationFn: (args: { chatId: string; title: string }) =>
      updateChat(args.chatId, { title: args.title }),
    onSuccess: refresh,
  });

  const setPinned = useMutation({
    mutationFn: (args: { chatId: string; pinned: boolean }) =>
      updateChat(args.chatId, { pinned: args.pinned }),
    onSuccess: refresh,
  });

  const remove = useMutation({
    mutationFn: (chatId: string) => deleteChat(chatId),
    onSuccess: (_, chatId) => {
      // Deleting the chat you're looking at leaves you on a new chat.
      if (chatId === openChatId) navigate("/");
      // Its cost moves from "Chats" to "Deleted chats" in the total.
      void queryClient.invalidateQueries({ queryKey: ["usage"] });
      return refresh();
    },
  });

  return {
    rename: (chatId: string, title: string) => rename.mutate({ chatId, title }),
    setPinned: (chatId: string, pinned: boolean) =>
      setPinned.mutate({ chatId, pinned }),
    remove: (chatId: string) => remove.mutate(chatId),
  };
}
