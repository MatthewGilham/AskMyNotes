// Lets you drag images and documents from your PC onto the chat. While you
// drag, a "Drop files to attach" cover shows over the chat area.
import { ImagePlus } from "lucide-react";
import { useEffect, useState, type DragEvent, type ReactNode } from "react";
import styles from "./DropZone.module.css";

type DropZoneProps = {
  onFiles: (files: File[]) => void;
  children: ReactNode;
};

function carriesFiles(event: DragEvent) {
  return event.dataTransfer.types.includes("Files");
}

export function DropZone({ onFiles, children }: DropZoneProps) {
  const [dragging, setDragging] = useState(false);

  // A file dropped anywhere else on the page would make the browser open it
  // and leave the app, so those drops are ignored.
  useEffect(() => {
    const ignore = (event: Event) => event.preventDefault();
    window.addEventListener("dragover", ignore);
    window.addEventListener("drop", ignore);
    return () => {
      window.removeEventListener("dragover", ignore);
      window.removeEventListener("drop", ignore);
    };
  }, []);

  return (
    <div
      className={styles.zone}
      onDragEnter={(event) => carriesFiles(event) && setDragging(true)}
    >
      {children}
      {dragging && (
        <div
          className={styles.cover}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            setDragging(false);
            onFiles(Array.from(event.dataTransfer.files));
          }}
        >
          <ImagePlus size={32} />
          Drop files to attach
        </div>
      )}
    </div>
  );
}
