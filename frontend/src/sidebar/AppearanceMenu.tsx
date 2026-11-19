// The Appearance menu: a button at the foot of the sidebar (an icon on the
// rail) that opens a small menu to choose the colour theme (Volt, Aurora or
// Ice) and the effects level (Full or Calm). The choice in use has a tick.
// The menu stays open after a choice, so the themes can be tried one after
// another; Escape or a click outside closes it.
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Check, Palette } from "lucide-react";
import {
  EFFECTS,
  THEMES,
  type Appearance,
  type Effects,
  type Theme,
} from "../design/appearance";
import styles from "./Sidebar.module.css";

const THEME_NAMES: Record<Theme, string> = {
  volt: "Volt",
  aurora: "Aurora",
  ice: "Ice",
};
const EFFECTS_NAMES: Record<Effects, string> = { full: "Full", calm: "Calm" };

type AppearanceMenuProps = {
  appearance: Appearance;
  onChange: (changes: Partial<Appearance>) => void;
  /** On the rail the button is only an icon, and the menu opens beside it. */
  onRail?: boolean;
};

export function AppearanceMenu({
  appearance,
  onChange,
  onRail = false,
}: AppearanceMenuProps) {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        {onRail ? (
          <button
            className={`${styles.iconButton} ${styles.railFoot}`}
            aria-label="Appearance"
          >
            <Palette size={18} />
          </button>
        ) : (
          <button className={`${styles.action} ${styles.appearance}`}>
            <Palette size={16} />
            Appearance
          </button>
        )}
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          className={styles.menu}
          side={onRail ? "right" : "top"}
          align={onRail ? "end" : "start"}
          sideOffset={8}
        >
          <Choices
            label="Theme"
            values={THEMES}
            names={THEME_NAMES}
            chosen={appearance.theme}
            onChoose={(theme) => onChange({ theme })}
          />
          <DropdownMenu.Separator className={styles.menuSeparator} />
          <Choices
            label="Effects"
            values={EFFECTS}
            names={EFFECTS_NAMES}
            chosen={appearance.effects}
            onChoose={(effects) => onChange({ effects })}
          />
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

type ChoicesProps<Value extends string> = {
  label: string;
  values: readonly Value[];
  names: Record<Value, string>;
  chosen: Value;
  onChoose: (value: Value) => void;
};

/** One group of the menu: a heading and its choices, one of them ticked. */
function Choices<Value extends string>({
  label,
  values,
  names,
  chosen,
  onChoose,
}: ChoicesProps<Value>) {
  return (
    <DropdownMenu.RadioGroup value={chosen}>
      <DropdownMenu.Label className={styles.menuLabel}>
        {label}
      </DropdownMenu.Label>
      {values.map((value) => (
        <DropdownMenu.RadioItem
          key={value}
          value={value}
          className={styles.menuItem}
          onSelect={(event) => {
            // Keeps the menu open, so another choice can be tried.
            event.preventDefault();
            onChoose(value);
          }}
        >
          {names[value]}
          <DropdownMenu.ItemIndicator className={styles.menuCheck}>
            <Check size={14} />
          </DropdownMenu.ItemIndicator>
        </DropdownMenu.RadioItem>
      ))}
    </DropdownMenu.RadioGroup>
  );
}
