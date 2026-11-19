// The screen the app opens on: the mark and greeting, the message box, and
// example prompts, all centred. Sending the first message hands over to the
// conversation layout.
import { Mark } from "../design/Mark";
import { greetingLines } from "./greeting";
import { MessageBox, type ComposerProps } from "./MessageBox";
import styles from "./NewChatScreen.module.css";

type NewChatScreenProps = {
  userName: string;
  examplePrompts: string[];
  composer: ComposerProps;
};

export function NewChatScreen({
  userName,
  examplePrompts,
  composer,
}: NewChatScreenProps) {
  const [hello, name] = greetingLines(userName);
  return (
    <div className={styles.screen}>
      <div className={styles.centre}>
        <div className={styles.greeting}>
          <Mark size={44} />
          {/* Set on two lines, but still one sentence to read: the name is on
              a line of its own through CSS, not a line break. */}
          <h1>
            {hello} <span className={styles.name}>{name}</span>
          </h1>
        </div>

        <MessageBox composer={composer} autoFocus />

        <div className={styles.prompts}>
          {examplePrompts.map((prompt) => (
            <button
              key={prompt}
              className={styles.prompt}
              disabled={composer.waitingForNotes || composer.busy}
              onClick={() => composer.onSend(prompt)}
            >
              {prompt}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
