"""The `search_notes` tool: how the agent looks things up in the notes database.

Every result the agent is shown gets a short id, such as S1 or S2, numbered
across all the searches in one reply. The agent ends its answer with a line
naming the ids it used, so only those slides and pages are listed as its
sources (see `notes/sources.py`).
"""

import asyncio
from typing import Literal

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from askmynotes.chats.models import Source
from askmynotes.notes.store import NoteResult, NotesStore
from askmynotes.settings import Module
from askmynotes.usage.log import UsageLog, logging_usage

SEARCH_TOOL_NAME = "search_notes"

TOOL_DESCRIPTION = (
    "Search the student's university lecture slides. Returns the slides and "
    "pages closest in meaning to the query, best first. Each starts with an id "
    "such as [S1], then its module, file and slide or page number."
)


class SearchMade(BaseModel):
    """One search the agent ran: what it asked for and which slides it got.

    Kept so the evaluation can show what the agent really searched for, which
    isn't always the student's question. Slide references only, never text.
    """

    query: str
    modules: list[str]
    results: list[Source]


class FoundNotes:
    """Every result the agent was shown while writing one reply, by short id,
    and the searches that found them."""

    def __init__(self) -> None:
        self.by_short_id: dict[str, NoteResult] = {}
        self.searches: list[SearchMade] = []

    def add(self, result: NoteResult) -> str:
        """Give a result its short id. A result seen before keeps its first id."""
        for short_id, seen in self.by_short_id.items():
            if seen.chunk_id == result.chunk_id:
                return short_id
        short_id = f"S{len(self.by_short_id) + 1}"
        self.by_short_id[short_id] = result
        return short_id


def search_arguments(short_names: list[str]) -> type[BaseModel]:
    """The tool's arguments. `modules` only accepts the short names from
    settings.toml, so the model can't search a module that doesn't exist."""
    ModuleShortName = Literal[tuple(short_names)]  # type: ignore[valid-type]

    class SearchNotesArguments(BaseModel):
        query: str = Field(
            description="What to look for, in the words the slides are likely to use."
        )
        modules: list[ModuleShortName] = Field(  # type: ignore[valid-type]
            default=[],
            description=(
                "Short names of the only modules to search. Leave empty to search "
                "every module."
            ),
        )

    return SearchNotesArguments


def describe_results(results: list[NoteResult], found: FoundNotes) -> str:
    """The results as text for the agent, each headed by its short id."""
    if not results:
        return "No slides or pages were found."
    blocks = []
    for result in results:
        short_id = found.add(result)
        location = "Slide" if result.location == "slide" else "Page"
        blocks.append(
            f"[{short_id}] {result.module} | {result.file_name} | "
            f"{location} {result.number}\n{result.text}"
        )
    return "\n\n---\n\n".join(blocks)


class NotesSearch:
    """Searches the notes database on the agent's behalf."""

    def __init__(
        self, store: NotesStore, modules: list[Module], results_per_search: int
    ) -> None:
        self.modules = modules
        self._store = store
        self._results_per_search = results_per_search

    def tool(self, found: FoundNotes, usage: UsageLog | None = None) -> BaseTool:
        """The `search_notes` tool for one reply. It records what it finds in
        `found`, so the reply's sources can be worked out afterwards, and what
        embedding the query cost in `usage`."""

        def search_in_thread(query: str, modules: list[str]) -> list[NoteResult]:
            with logging_usage(usage):
                return self._store.search(query, modules, self._results_per_search)

        async def search_notes(query: str, modules: list[str]) -> str:
            # The search waits on OpenAI and Chroma, so it runs in a thread to
            # keep the server free. The ids are given out back here, one search
            # at a time, so two searches running together can't share an id.
            results = await asyncio.to_thread(search_in_thread, query, modules)
            found.searches.append(
                SearchMade(
                    query=query,
                    modules=modules,
                    results=[
                        Source(
                            file_name=r.file_name,
                            module=r.module,
                            location=r.location,
                            number=r.number,
                        )
                        for r in results
                    ],
                )
            )
            return describe_results(results, found)

        return StructuredTool.from_function(
            coroutine=search_notes,
            name=SEARCH_TOOL_NAME,
            description=TOOL_DESCRIPTION,
            args_schema=search_arguments([m.short_name for m in self.modules]),
        )
