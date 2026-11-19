"""Working out which slides and pages a notes answer used.

After a search, the agent ends its answer with a line such as
`Sources used: S1, S4`, naming the results it used (see `notes/search.py`).
That line is taken off the answer before it is saved, and those results
become the sources listed under it. If the agent searched but left the line
out, every result it was shown is listed instead, so a notes answer is never
missing its sources.
"""

import logging
import re

from askmynotes.chats.models import Source
from askmynotes.notes.search import FoundNotes

logger = logging.getLogger(__name__)

SOURCES_LABEL = "sources used:"
# Shorter starts, such as "So", are far more likely to be ordinary words.
MIN_LABEL_START = 3
# The closing line at the very end of the reply: the label, then only ids,
# "none" and punctuation. The model sometimes puts it on its own line, in bold,
# or straight after the last sentence, so it isn't required to start a line.
SOURCES_LINE = re.compile(
    r"[ \t]*[*_]*sources used:(?P<ids>(?:[\s,;&.*_]|and|none|S\d+)*)$", re.IGNORECASE
)
# The same line cut off part-way through, in a reply that was stopped.
UNFINISHED_SOURCES_LINE = re.compile(r"[ \t]*[*_]*sources used:[^\n]*$", re.IGNORECASE)


def without_unfinished_sources_line(text: str) -> str:
    """Remove a sources line that a stopped reply ended part-way through,
    including one cut off inside the label itself ("Sources us")."""
    trimmed = text.rstrip()
    match = UNFINISHED_SOURCES_LINE.search(trimmed)
    if match:
        return trimmed[: match.start()].rstrip()
    bare = trimmed.rstrip("*_")
    for length in range(len(SOURCES_LABEL) - 1, MIN_LABEL_START - 1, -1):
        start = len(bare) - length
        if start < 0:
            continue  # the text is shorter than this much of the label
        starts_a_word = start == 0 or bare[start - 1] in " \t\n*_"
        if starts_a_word and bare.lower().endswith(SOURCES_LABEL[:length]):
            return bare[:start].rstrip()
    return text


def split_sources_line(reply: str, complete: bool) -> tuple[str, list[str] | None]:
    """Separate the answer from its sources line: (answer, ids named).

    The ids are None when there is no sources line. A reply that didn't
    finish (stopped, or failed) may end part-way through the line, so that
    unfinished piece is removed too.
    """
    if not complete:
        # Ids that were still being written can't be trusted, so none are read.
        # A partial reply with no sources line is kept exactly as it was.
        return without_unfinished_sources_line(reply), None
    text = reply.rstrip()
    match = SOURCES_LINE.search(text)
    if match:
        return text[: match.start()].rstrip(), re.findall(r"S\d+", match["ids"])
    return text, None


def answer_and_sources(
    reply: str, found: FoundNotes, complete: bool
) -> tuple[str, list[Source] | None]:
    """The answer to save, and the sources to list under it (None if none)."""
    answer, ids = split_sources_line(reply, complete)
    if not found.by_short_id:
        return answer, None
    if ids is None:
        if complete:
            logger.warning("The agent searched but didn't name its sources")
        used = list(found.by_short_id.values())
    else:
        # Ids the agent wasn't given are ignored.
        used = [found.by_short_id[i] for i in ids if i in found.by_short_id]

    # Parts of one long page share its page number, so list each page once.
    sources = {
        (r.module, r.file_name, r.number): Source(
            file_name=r.file_name, module=r.module, location=r.location, number=r.number
        )
        for r in used
    }
    return answer, [sources[key] for key in sorted(sources)] or None
