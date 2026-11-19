// The two readouts in a chat's header: its total API cost, and a ring showing
// how full the long-chat budget is. Each has a tooltip with the detail.
import type { ChatUsageData } from "../api/client";
import { formatCost, formatDate, formatTokens } from "./format";
import { Readout } from "./Readout";
import { useChatUsage } from "./useUsage";
import styles from "./ChatUsage.module.css";

// The ring turns amber from here, a warning that the next message may
// summarise the older part of the chat.
const WARN_FROM = 0.9;
const RING_RADIUS = 6;
const RING_LENGTH = 2 * Math.PI * RING_RADIUS;

type ChatUsageProps = {
  chatId: string | null;
  /** A reply is being written, so the numbers are about to change. */
  replying: boolean;
};

export function ChatUsage({ chatId, replying }: ChatUsageProps) {
  const usage = useChatUsage(chatId, replying).data;
  if (usage === undefined) return null;
  return (
    <>
      <Readout
        label={`API cost of this chat: ${formatCost(usage.cost)}`}
        placement="below"
        tooltip={<CostDetail usage={usage} />}
      >
        {formatCost(usage.cost)}
      </Readout>
      <Readout
        label={`Context used: ${Math.round(fillOf(usage) * 100)}% of the long-chat budget`}
        placement="below"
        tooltip={<ContextDetail usage={usage} />}
      >
        <Ring fill={fillOf(usage)} />
      </Readout>
    </>
  );
}

function fillOf(usage: ChatUsageData): number {
  const { tokens, budgetTokens } = usage.context;
  return Math.min(tokens / budgetTokens, 1);
}

function Ring({ fill }: { fill: number }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <circle className={styles.ringTrack} cx="8" cy="8" r={RING_RADIUS} />
      <circle
        className={fill >= WARN_FROM ? styles.ringWarn : styles.ringFill}
        cx="8"
        cy="8"
        r={RING_RADIUS}
        strokeDasharray={`${fill * RING_LENGTH} ${RING_LENGTH}`}
        transform="rotate(-90 8 8)"
      />
    </svg>
  );
}

function CostDetail({ usage }: { usage: ChatUsageData }) {
  const parts = [
    ["Replies", usage.breakdown.replies],
    ["Titles", usage.breakdown.titles],
    ["Summaries", usage.breakdown.summaries],
    ["Searches", usage.breakdown.searches],
    ["Web searches", usage.breakdown.webSearches],
    ["Python", usage.breakdown.python],
  ].filter(([, cost]) => (cost as number) > 0);
  return (
    <>
      <strong>{formatCost(usage.cost)} for this chat</strong>
      {parts.map(([name, cost]) => (
        <div key={name as string}>
          {name} {formatCost(cost as number)}
        </div>
      ))}
      {usage.includesEstimate && (
        <div className={styles.note}>
          Includes an estimate (a reply that was stopped).
        </div>
      )}
      {usage.earlierCostsUnrecorded && (
        <div className={styles.note}>
          Costs before {formatDate(usage.trackingStartedAt)} weren't recorded.
        </div>
      )}
    </>
  );
}

function ContextDetail({ usage }: { usage: ChatUsageData }) {
  const { tokens, budgetTokens, summarised, overBudget } = usage.context;
  return (
    <>
      <strong>
        ≈{formatTokens(tokens)} of {formatTokens(budgetTokens)} tokens
      </strong>
      {summarised && <div>Older messages have been summarised.</div>}
      {overBudget && (
        <div>The next message will summarise the older messages.</div>
      )}
      <div className={styles.note}>
        Instructions and notes search results aren't counted.
      </div>
    </>
  );
}
