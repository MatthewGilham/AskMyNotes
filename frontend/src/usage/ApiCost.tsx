// The all-chats API cost at the bottom of the sidebar, with a tooltip that
// splits it into chats, deleted chats and notes updates.
import { formatCost, formatDate } from "./format";
import { Readout } from "./Readout";
import { useTotalUsage } from "./useUsage";
import styles from "./ApiCost.module.css";

export function ApiCost({ notesUpdating }: { notesUpdating: boolean }) {
  const total = useTotalUsage(notesUpdating).data;
  if (total === undefined) return null;
  return (
    <div className={styles.row}>
      <Readout
        label={`API cost of everything: ${formatCost(total.cost)}`}
        placement="above"
        tooltip={
          <>
            <strong>{formatCost(total.cost)} in total</strong>
            <div>Chats {formatCost(total.chats)}</div>
            <div>Deleted chats {formatCost(total.deletedChats)}</div>
            <div>Notes updates {formatCost(total.notesUpdates)}</div>
            {total.includesEstimate && (
              <div className={styles.note}>
                Includes estimates (replies that were stopped).
              </div>
            )}
            <div className={styles.note}>
              Recorded since {formatDate(total.trackingStartedAt)}. OpenAI's
              dashboard is the authority.
            </div>
          </>
        }
      >
        API cost {formatCost(total.cost)}
      </Readout>
    </div>
  );
}
