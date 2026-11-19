"""Asking the agent one question, the way the chat does.

This is the same agent, instructions and sources handling as a real reply,
without saving anything: each question is a fresh chat of one message.
"""

from dataclasses import dataclass

from langchain_core.messages import HumanMessage

from askmynotes.agent.agent import Agent, NotesSearchStarted, WebSearchStarted
from askmynotes.chats.models import Source
from askmynotes.notes.search import FoundNotes, SearchMade
from askmynotes.notes.sources import answer_and_sources, split_sources_line


@dataclass
class AgentRun:
    """What the agent did and wrote for one question."""

    answer: str
    sources: list[Source] | None
    searched: bool
    # Did it search the web?
    web_searched: bool
    # Every search it ran, with the slides each returned.
    searches: list[SearchMade]
    # Did the reply end with its "Sources used" line? If not, every result it
    # was shown is listed as a source instead.
    sources_line_found: bool


async def ask_agent(agent: Agent, question: str) -> AgentRun:
    """Put a question to the agent in a fresh chat and collect its answer."""
    found = FoundNotes()
    parts: list[str] = []
    searched = False
    web_searched = False
    async for piece in agent.stream_reply([HumanMessage(content=question)], found):
        if isinstance(piece, NotesSearchStarted):
            searched = True
        elif isinstance(piece, WebSearchStarted):
            web_searched = True
        else:
            parts.append(piece)
    reply = "".join(parts)
    answer, sources = answer_and_sources(reply, found, complete=True)
    return AgentRun(
        answer=answer,
        sources=sources,
        searched=searched,
        web_searched=web_searched,
        searches=found.searches,
        sources_line_found=split_sources_line(reply, complete=True)[1] is not None,
    )
