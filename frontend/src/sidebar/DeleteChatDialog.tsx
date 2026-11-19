// Asks for confirmation before a chat is deleted for good.
import * as Dialog from "@radix-ui/react-dialog";
import type { ChatSummary } from "../chat/types";
import styles from "./Dialogs.module.css";

type DeleteChatDialogProps = {
  chat: ChatSummary | null;
  onCancel: () => void;
  onConfirm: (chat: ChatSummary) => void;
};

export function DeleteChatDialog({
  chat,
  onCancel,
  onConfirm,
}: DeleteChatDialogProps) {
  return (
    <Dialog.Root
      open={chat !== null}
      onOpenChange={(open) => !open && onCancel()}
    >
      <Dialog.Portal>
        <Dialog.Overlay className={styles.overlay} />
        <Dialog.Content className={styles.panel}>
          <Dialog.Title className={styles.title}>
            Delete this chat?
          </Dialog.Title>
          <Dialog.Description className={styles.description}>
            “{chat?.title}” and everything in it will be deleted for good. This
            can't be undone.
          </Dialog.Description>
          <div className={styles.buttons}>
            <button className={styles.secondary} onClick={onCancel}>
              Cancel
            </button>
            <button
              className={styles.danger}
              onClick={() => chat && onConfirm(chat)}
            >
              Delete
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
