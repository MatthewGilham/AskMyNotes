// A small, quiet readout with a tooltip. The tooltip opens on hover and on
// keyboard focus, and is tied to the button so screen readers announce it.
// It is plain CSS rather than a library, because it only has to show text.
import { useId, type ReactNode } from "react";
import styles from "./Readout.module.css";

type ReadoutProps = {
  /** The accessible name, which also says what the number is. */
  label: string;
  /** Where the tooltip opens: under the readout (header) or above it (sidebar). */
  placement: "below" | "above";
  tooltip: ReactNode;
  children: ReactNode;
};

export function Readout({ label, placement, tooltip, children }: ReadoutProps) {
  const tooltipId = useId();
  return (
    <span className={styles.wrap}>
      <button
        type="button"
        className={styles.trigger}
        aria-label={label}
        aria-describedby={tooltipId}
      >
        {children}
      </button>
      <span
        role="tooltip"
        id={tooltipId}
        className={`${styles.tooltip} ${placement === "below" ? styles.below : styles.above}`}
      >
        {tooltip}
      </span>
    </span>
  );
}
