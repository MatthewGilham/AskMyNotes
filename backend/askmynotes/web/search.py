"""Web search through OpenAI's built-in `web_search` tool.

Unlike `search_notes`, this tool runs on OpenAI's side: the agent only offers it
to the model. The model's reply then carries, as pieces of its content, a
`web_search_call` for each search it made (with the query, and the pages the
search read), and a `url_citation` annotation for each page it cited. `FoundWeb`
collects these while a reply streams, the way `FoundNotes` collects the notes
results. It also reads the links the model wrote inside a `:::web` block, because
a reply written after a calculator call doesn't always carry `url_citation`s.

OpenAI says a search has started a couple of seconds before it says it has
finished, but LangChain only passes on the finish. `watch_web_searches` wraps
OpenAI's client to pass the start on too, so "Searching the web…" can show for
the whole search.
"""

import re
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse

from langchain_core.messages import AIMessageChunk
from langchain_openai import ChatOpenAI
from langgraph.config import get_stream_writer

from askmynotes.chats.models import WebSource
from askmynotes.settings import WebSearch

# Asking for this makes OpenAI return every page a search read, not only the
# ones the answer cites.
SOURCES_INCLUDE = "web_search_call.action.sources"
# The key of the custom event that tells the agent a search has started.
SEARCH_STARTED = "web_search_started"
# An uncited page has no title, so it is listed by its address, cut to this.
MAX_ADDRESS_LENGTH = 70

# Markers that open a box in a reply, and the kinds that are source boxes. This
# mirrors `frontend/src/markdown/replyBlocks.ts`.
BOX_MARKERS = {
    ":::beyond": "beyond",
    ":::web": "web",
    ":::formula": "formula",
    ":::tip": "tip",
    ":::mistake": "mistake",
    ":::example": "example",
}
SOURCE_BOXES = {"beyond", "web"}
FENCE = re.compile(r"^\s*(```+|~~~+)")
MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def web_search_tool(location: WebSearch) -> dict[str, Any]:
    """The tool as OpenAI expects it, saying roughly where the student is."""
    return {
        "type": "web_search",
        "user_location": {
            "type": "approximate",
            "country": location.country,
            "timezone": location.timezone,
        },
    }


def site_name(url: str) -> str:
    """A page's site as shown to the student: its host without "www."."""
    host = urlparse(url).hostname or url
    return host.removeprefix("www.")


def page_key(url: str) -> str:
    """What makes two addresses the same page: the site, the path without a
    final slash and the query without the tracking OpenAI adds to its links."""
    parts = urlparse(url)
    query = urlencode(
        [(k, v) for k, v in parse_qsl(parts.query) if not k.startswith("utm_")]
    )
    return f"{site_name(url)}{parts.path.rstrip('/')}?{query}"


def short_address(url: str) -> str:
    """A page's address without "https://www." and tracking, cut to fit."""
    parts = urlparse(url)
    address = f"{site_name(url)}{parts.path.rstrip('/')}"
    if len(address) <= MAX_ADDRESS_LENGTH:
        return address
    return address[: MAX_ADDRESS_LENGTH - 1] + "…"


def web_block_text(reply: str) -> str:
    """The parts of a reply inside `:::web` boxes, callouts in them included."""
    inside: list[str] = []
    open_boxes: list[str] = []
    fence: str | None = None
    for line in reply.split("\n"):
        match = FENCE.match(line)
        if match:
            if fence is None:
                fence = match.group(1)[0]
            elif match.group(1)[0] == fence:
                fence = None
        marker = line.strip()
        kind = BOX_MARKERS.get(marker) if fence is None else None
        top = open_boxes[-1] if open_boxes else None
        # Source boxes open only at the top; callouts at the top or inside one.
        if kind and (top is None or (kind not in SOURCE_BOXES and top in SOURCE_BOXES)):
            open_boxes.append(kind)
        elif fence is None and marker == ":::" and open_boxes:
            open_boxes.pop()
        elif "web" in open_boxes and fence is None and not match:
            # Code is not text with links in it.
            inside.append(line)
    return "\n".join(inside)


def announce_search_started() -> None:
    """Tell the agent's stream that a web search has begun. It must be called
    from inside the agent's graph, which is where the model is called."""
    get_stream_writer()({SEARCH_STARTED: True})


class WatchedStream:
    """OpenAI's stream of events for one reply, which announces each web search
    as it starts and passes every event on unchanged."""

    def __init__(self, stream: Any) -> None:
        self._stream = stream

    async def __aenter__(self) -> "WatchedStream":
        await self._stream.__aenter__()
        return self

    async def __aexit__(self, *error: Any) -> Any:
        return await self._stream.__aexit__(*error)

    def __aiter__(self) -> AsyncIterator[Any]:
        return self._events()

    async def _events(self) -> AsyncIterator[Any]:
        async for event in self._stream:
            if (
                event.type == "response.output_item.added"
                and event.item.type == "web_search_call"
            ):
                announce_search_started()
            yield event


def watch_web_searches(model: ChatOpenAI) -> ChatOpenAI:
    """Make the model's client announce each web search as it starts. It wraps
    the one call LangChain makes to open a streamed reply, so nothing else about
    the reply changes."""
    responses = model.root_async_client.responses
    open_stream = responses.create

    async def create_and_watch(**request: Any) -> Any:
        stream = await open_stream(**request)
        return WatchedStream(stream) if request.get("stream") else stream

    responses.create = create_and_watch
    return model


class FoundWeb:
    """What a reply found online: how many searches it made and what they asked
    for, the pages it cited (in the order cited) and the pages the searches read
    that it didn't cite."""

    def __init__(self) -> None:
        self.search_count = 0
        self.queries: list[str] = []
        # The cited pages: from `url_citation`s, and from links in `:::web` boxes.
        self.sources: list[WebSource] = []
        self._read: list[WebSource] = []
        self._search_ids: set[str] = set()

    def read(self, chunk: AIMessageChunk) -> int:
        """Take what one streamed piece of the reply says about the web.
        Returns how many searches it starts that weren't seen before."""
        if isinstance(chunk.content, str):
            return 0
        new_searches = 0
        for block in chunk.content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "web_search_call":
                # The same search can be reported more than once as it
                # progresses, so each is counted by its id.
                search_id = block.get("id") or f"search-{self.search_count}"
                if search_id not in self._search_ids:
                    self._search_ids.add(search_id)
                    self.search_count += 1
                    new_searches += 1
                self._read_search(block.get("action") or {})
            for annotation in block.get("annotations", []):
                if annotation.get("type") == "url_citation":
                    self._add_cited(annotation["url"], annotation.get("title"))
        return new_searches

    def cite_links_in(self, reply: str) -> None:
        """Count the pages the reply links to inside its `:::web` boxes as cited,
        for when OpenAI sent no `url_citation` for them."""
        for title, url in MARKDOWN_LINK.findall(web_block_text(reply)):
            self._add_cited(url, title)

    def pages(self) -> list[WebSource]:
        """Every page to list: the cited ones, then those searches read and the
        answer didn't cite."""
        cited = {page_key(source.url) for source in self.sources}
        return self.sources + [s for s in self._read if page_key(s.url) not in cited]

    def _read_search(self, action: dict[str, Any]) -> None:
        for query in action.get("queries") or [action.get("query")]:
            if query and query not in self.queries:
                self.queries.append(query)
        for source in action.get("sources") or []:
            url = source["url"]
            if all(page_key(url) != page_key(page.url) for page in self._read):
                self._read.append(
                    WebSource(
                        title=short_address(url),
                        site=site_name(url),
                        url=url,
                        cited=False,
                    )
                )

    def _add_cited(self, url: str, title: str | None) -> None:
        if any(page_key(url) == page_key(source.url) for source in self.sources):
            return
        title = (title or "").strip() or site_name(url)
        self.sources.append(WebSource(title=title, site=site_name(url), url=url))
