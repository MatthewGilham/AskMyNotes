// Groups chats for the sidebar by when they were last used, as the spec
// describes: pinned chats first, then Today, Yesterday, Last 7 days,
// Last 30 days and Older. Days follow your local time.
import type { ChatSummary } from "../chat/types";

export type ChatGroup = {
  label: string;
  chats: ChatSummary[];
};

const DAY_MS = 24 * 60 * 60 * 1000;

export function groupChatsByLastUsed(
  chats: ChatSummary[],
  now: Date = new Date(),
): ChatGroup[] {
  const startOfToday = new Date(now);
  startOfToday.setHours(0, 0, 0, 0);
  const today = startOfToday.getTime();

  // Each group takes the chats used on or after its start time, checked in
  // order, so a chat lands in the first (most recent) group it fits.
  const groups: { label: string; startsAt: number; chats: ChatSummary[] }[] = [
    { label: "Today", startsAt: today, chats: [] },
    { label: "Yesterday", startsAt: today - DAY_MS, chats: [] },
    { label: "Last 7 days", startsAt: today - 7 * DAY_MS, chats: [] },
    { label: "Last 30 days", startsAt: today - 30 * DAY_MS, chats: [] },
    { label: "Older", startsAt: -Infinity, chats: [] },
  ];
  const pinned: ChatSummary[] = [];

  const newestFirst = [...chats].sort(
    (a, b) => b.lastUsedAt.getTime() - a.lastUsedAt.getTime(),
  );
  for (const chat of newestFirst) {
    if (chat.pinned) {
      pinned.push(chat);
      continue;
    }
    const group = groups.find((g) => chat.lastUsedAt.getTime() >= g.startsAt);
    group!.chats.push(chat); // "Older" starts at -Infinity, so one always fits
  }

  return [{ label: "Pinned", chats: pinned }, ...groups].filter(
    (group) => group.chats.length > 0,
  );
}
