"""Remove unsupported internal citations from assistant text at chat boundaries."""

import re

CITATION_OPEN = "\ue200cite\ue202"
CITATION = re.compile(re.escape(CITATION_OPEN) + "[^\ue201]*(?:\ue201|$)")


def without_citation_markers(text: str) -> str:
    """Remove reserved citations, including a trailing token still being written.

    Only an exact citation opening is special. A trailing prefix is held back
    too, so streaming never flashes half an opening before it can be recognised.
    User messages and uploaded material must not be passed through this helper.
    """
    text = CITATION.sub("", text)
    for length in range(len(CITATION_OPEN) - 1, 0, -1):
        if text.endswith(CITATION_OPEN[:length]):
            return text[:-length]
    return text
