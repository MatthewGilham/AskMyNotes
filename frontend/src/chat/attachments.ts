// Files waiting to be sent with the next message: adding them (button, paste
// or drag-and-drop), checking them against the limits from settings.toml,
// removing them, and turning them into the form the server expects. Images
// and documents (PDF, Word, Excel, PowerPoint) share one list.
import { useState } from "react";
import type { DocumentUpload, ImageUpload } from "../api/client";
import type { Attachment } from "./types";

const IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"];
const DOCUMENT_EXTENSIONS = [
  ".pdf",
  ".docx",
  ".doc",
  ".pptx",
  ".ppt",
  ".xlsx",
  ".xls",
];
const BYTES_PER_MEGABYTE = 1024 * 1024;

export const ACCEPT_ATTRIBUTE = [...IMAGE_TYPES, ...DOCUMENT_EXTENSIONS].join(
  ",",
);

function isDocument(file: File) {
  const name = file.name.toLowerCase();
  return DOCUMENT_EXTENSIONS.some((extension) => name.endsWith(extension));
}

export type Limits = {
  maxImages: number;
  maxImageMegabytes: number;
  maxDocuments: number;
  maxDocumentMegabytes: number;
};

export function useAttachments(limits: Limits) {
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [error, setError] = useState<string | null>(null);

  /** Adds every acceptable file; says what was wrong with the others. */
  function addFiles(files: File[]) {
    const next = [...attachments];
    let problem: string | null = null;
    const count = (isImage: boolean) =>
      next.filter((a) => a.isImage === isImage).length;
    for (const file of files) {
      const image = IMAGE_TYPES.includes(file.type);
      if (!image && !isDocument(file)) {
        problem = `${file.name} isn't a supported file type. Use an image (PNG, JPEG, WebP or GIF) or a PDF, Word, Excel or PowerPoint file.`;
        continue;
      }
      const maxMegabytes = image
        ? limits.maxImageMegabytes
        : limits.maxDocumentMegabytes;
      if (file.size > maxMegabytes * BYTES_PER_MEGABYTE) {
        problem = `${file.name} is larger than ${maxMegabytes} MB.`;
      } else if (image && count(true) >= limits.maxImages) {
        problem = `You can attach up to ${limits.maxImages} images to a message.`;
        break;
      } else if (!image && count(false) >= limits.maxDocuments) {
        problem = `You can attach up to ${limits.maxDocuments} documents to a message.`;
        break;
      } else {
        next.push({
          id: crypto.randomUUID(),
          name: file.name,
          file,
          isImage: image,
          previewUrl: image ? URL.createObjectURL(file) : null,
        });
      }
    }
    setAttachments(next);
    setError(problem);
  }

  function remove(id: string) {
    const removed = attachments.find((a) => a.id === id);
    if (removed?.previewUrl) URL.revokeObjectURL(removed.previewUrl);
    setAttachments(attachments.filter((a) => a.id !== id));
    setError(null);
  }

  function clear() {
    attachments.forEach((a) => {
      if (a.previewUrl) URL.revokeObjectURL(a.previewUrl);
    });
    setAttachments([]);
    setError(null);
  }

  async function toUploads(): Promise<{
    images: ImageUpload[];
    documents: DocumentUpload[];
  }> {
    const read = async (a: Attachment) => ({
      name: a.name,
      mediaType: a.file.type,
      data: await readAsBase64(a.file),
    });
    const images = await Promise.all(
      attachments.filter((a) => a.isImage).map(read),
    );
    const documents = await Promise.all(
      attachments
        .filter((a) => !a.isImage)
        .map(async (a) => {
          const { name, data } = await read(a);
          return { name, data };
        }),
    );
    return { images, documents };
  }

  return { attachments, error, addFiles, remove, clear, toUploads };
}

function readAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    // The result looks like "data:image/png;base64,AAAA…"; keep what follows the comma.
    reader.onload = () => resolve((reader.result as string).split(",")[1]);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}
