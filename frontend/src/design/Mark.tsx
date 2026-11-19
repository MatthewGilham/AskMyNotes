// The app's logo mark: two offset slides, the front one cut by a lightning
// bolt. The slides stand for your lecture notes, the bolt for the AI boost.
import { useId } from "react";

type MarkProps = {
  size?: number;
};

export function Mark({ size = 32 }: MarkProps) {
  // Each mark on the page needs its own gradient id, or they'd clash.
  const gradientId = useId();

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      role="img"
      aria-label="AskMyNotes"
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="var(--color-accent)" />
          <stop offset="100%" stopColor="var(--color-accent-2)" />
        </linearGradient>
      </defs>
      {/* The back slide, an outline. */}
      <rect
        x="9"
        y="3"
        width="20"
        height="16"
        rx="4"
        fill="none"
        stroke={`url(#${gradientId})`}
        strokeWidth="2"
        opacity="0.55"
      />
      {/* The front slide, solid, with the bolt cut out of it. */}
      <path
        fillRule="evenodd"
        fill={`url(#${gradientId})`}
        d="M7 10h16a4 4 0 0 1 4 4v10a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V14a4 4 0 0 1 4-4Z
           M17.5 12.5 10.5 20h4.5l-2 5.5 7-7.5h-4.5l2-5.5Z"
      />
    </svg>
  );
}
