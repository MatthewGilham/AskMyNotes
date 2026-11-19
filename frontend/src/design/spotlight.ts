// The soft light that follows the pointer across a glass pane. The light
// itself is drawn in CSS (glass.module.css); this only tells it where the
// pointer is.
import type { PointerEvent } from "react";

/** Use as a pane's onPointerMove, so its light follows the pointer. */
export function followPointer(event: PointerEvent<HTMLElement>) {
  const pane = event.currentTarget;
  const box = pane.getBoundingClientRect();
  pane.style.setProperty("--pointer-x", `${event.clientX - box.left}px`);
  pane.style.setProperty("--pointer-y", `${event.clientY - box.top}px`);
}
