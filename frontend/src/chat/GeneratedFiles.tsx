// The files Python made for an answer, under the answer. PNG, JPEG and GIF
// pictures are shown, and clicking one opens it full size. Every other file is a
// chip with a download button. Nothing here is ever opened as a page: the server
// serves every file as a download, so a file can't run scripts in the app.
import * as Dialog from "@radix-ui/react-dialog";
import { Download, X } from "lucide-react";
import { FileIcon, formatSize } from "./DocumentChip";
import type { MessageFile } from "./types";
import styles from "./GeneratedFiles.module.css";

type GeneratedFilesProps = {
  files: MessageFile[];
};

export function GeneratedFiles({ files }: GeneratedFilesProps) {
  const images = files.filter((file) => file.isImage);
  const others = files.filter((file) => !file.isImage);
  return (
    <div className={styles.files} data-no-quote>
      {images.length > 0 && (
        <div className={styles.images}>
          {images.map((file) => (
            <PictureButton key={file.id} file={file} />
          ))}
        </div>
      )}
      {others.length > 0 && (
        <ul className={styles.chips} aria-label="Files made by Python">
          {others.map((file) => (
            <li key={file.id}>
              <FileChip file={file} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function PictureButton({ file }: { file: MessageFile }) {
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <button
          className={styles.picture}
          aria-label={`Open ${file.name} full size`}
          title={`Open ${file.name} full size`}
        >
          <img src={file.url} alt={file.name} />
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className={styles.overlay} />
        <Dialog.Content className={styles.viewer}>
          <Dialog.Title className={styles.viewerTitle}>
            {file.name}
          </Dialog.Title>
          <Dialog.Description className={styles.hidden}>
            The picture {file.name}, shown full size.
          </Dialog.Description>
          <img className={styles.full} src={file.url} alt={file.name} />
          <div className={styles.viewerButtons}>
            <a
              className={styles.viewerButton}
              href={file.url}
              download={file.name}
            >
              <Download size={14} />
              Download
            </a>
            <Dialog.Close className={styles.viewerButton}>
              <X size={14} />
              Close
            </Dialog.Close>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function FileChip({ file }: { file: MessageFile }) {
  return (
    <a
      className={styles.chip}
      href={file.url}
      download={file.name}
      title={`Download ${file.name}`}
      aria-label={`Download ${file.name} (${formatSize(file.size)})`}
    >
      <FileIcon
        name={file.name}
        size={16}
        aria-hidden="true"
        className={styles.chipIcon}
      />
      <span className={styles.chipName}>{file.name}</span>
      <span className={styles.chipSize}>{formatSize(file.size)}</span>
      <Download size={14} aria-hidden="true" className={styles.chipDownload} />
    </a>
  );
}
