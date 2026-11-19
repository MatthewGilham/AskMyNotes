// The notes sync's status, checked once a second while an update runs, and
// the "Refresh notes" action.
import {
  useMutation,
  useQuery,
  useQueryClient,
  type Query,
} from "@tanstack/react-query";
import {
  getNotesStatus,
  refreshNotes,
  type NotesStatusData,
} from "../api/client";

const CHECK_EVERY_MS = 1000;
const QUERY_KEY = ["notes-status"];

export function useNotesStatus() {
  const queryClient = useQueryClient();

  const status = useQuery({
    queryKey: QUERY_KEY,
    queryFn: getNotesStatus,
    // Keep checking until an update has finished; then stop.
    refetchInterval: (query: Query<NotesStatusData>) =>
      query.state.data?.updating === false ? false : CHECK_EVERY_MS,
  });

  const refresh = useMutation({
    mutationFn: refreshNotes,
    onSuccess: (started) => queryClient.setQueryData(QUERY_KEY, started),
    // Refused because an update is already running: just show that one.
    onError: () => queryClient.invalidateQueries({ queryKey: QUERY_KEY }),
  });

  return {
    status: status.data,
    // Chat waits until the notes are known to be up to date.
    updating: status.data === undefined || status.data.updating,
    refresh: () => refresh.mutate(),
  };
}
