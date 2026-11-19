// Hides the "Sources used: S1, S4" line while a notes answer streams in.
//
// After a search, the agent ends its answer with that line, naming the
// results it used. The server takes it off before saving and lists those
// sources under the answer instead. While the reply is still streaming, the
// line (or the start of it) is hidden here, so it never flashes on screen.
// This must agree with the server's reading of the line, in notes/sources.py:
// it may be on its own line, in bold, or straight after the last sentence.

const SOURCES_LABEL = "sources used:";
// Shorter starts, such as "So", are far more likely to be ordinary words.
const MIN_LABEL_START = 3;
const SOURCES_LINE = /[ \t]*[*_]*sources used:[^\n]*$/i;

export function hideSourcesLine(reply: string): string {
  const text = reply.trimEnd();
  const line = SOURCES_LINE.exec(text);
  if (line) return text.slice(0, line.index).trimEnd();

  // The label itself may not have fully arrived yet ("Sources us").
  const bare = text.replace(/[*_]+$/, "");
  for (
    let length = SOURCES_LABEL.length - 1;
    length >= MIN_LABEL_START;
    length--
  ) {
    const start = bare.length - length;
    const startsAWord = start === 0 || " \t\n*_".includes(bare[start - 1]);
    if (
      startsAWord &&
      bare.toLowerCase().endsWith(SOURCES_LABEL.slice(0, length))
    ) {
      return bare.slice(0, start).trimEnd();
    }
  }
  return reply;
}
