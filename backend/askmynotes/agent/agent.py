"""Builds the agent and streams its replies one piece of text at a time.

The agent has `search_notes`, a calculator and OpenAI's web search, and decides
for itself, guided by its instructions, whether a question needs any of them. When
the student has switched Python on, it also has OpenAI's Code Interpreter.
"""

from collections.abc import AsyncIterator, Callable
from datetime import date
from pathlib import Path

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, AnyMessage, ToolMessage
from langchain_openai import ChatOpenAI

from askmynotes.calculator.tools import (
    CALCULATOR_TOOL_NAMES,
    ToolRuns,
    calculator_tools,
)
from askmynotes.interpreter.reply import INCLUDE_OUTPUTS, PythonReply
from askmynotes.notes.search import SEARCH_TOOL_NAME, FoundNotes, NotesSearch
from askmynotes.settings import EnvSettings, Module, WebSearch
from askmynotes.usage.log import UsageLog, message_characters
from askmynotes.web.search import (
    SEARCH_STARTED,
    SOURCES_INCLUDE,
    FoundWeb,
    watch_web_searches,
    web_search_tool,
)

INSTRUCTIONS_FILE = Path(__file__).with_name("instructions.md")
# Added to the instructions for a reply that has Python.
PYTHON_INSTRUCTIONS_FILE = Path(__file__).with_name("python_instructions.md")
# Where it lists the Excel files in the sandbox.
FILES_PLACEHOLDER = "{files}"
# Where the instructions file lists the modules from settings.toml.
MODULES_PLACEHOLDER = "{modules}"
# Where the instructions file gives today's date, filled in for each reply.
TODAY_PLACEHOLDER = "{today}"


def create_chat_model(env: EnvSettings) -> BaseChatModel:
    """The real model, from the model name and key in `.env`."""
    # The Responses API is the one OpenAI's web search and Code Interpreter
    # tools work through. `store=False` stops OpenAI keeping each conversation
    # for later retrieval, and "responses/v1" keeps the search and citation
    # details in the reply. stream_usage makes OpenAI report the tokens each
    # streamed call used, which the cost indicators rely on.
    model = ChatOpenAI(
        model=env.chat_model,
        api_key=env.openai_api_key,
        use_responses_api=True,
        output_version="responses/v1",
        store=False,
        stream_usage=True,
    )
    # So "Searching the web…" can show from the moment a search starts.
    return watch_web_searches(model)


def load_instructions(modules: list[Module]) -> str:
    """The instructions file, with the student's modules filled in."""
    module_list = "\n".join(f"- {m.name} ({m.short_name})" for m in modules)
    instructions = INSTRUCTIONS_FILE.read_text(encoding="utf-8")
    return instructions.replace(MODULES_PLACEHOLDER, module_list or "(none)")


def python_instructions(python: PythonReply) -> str:
    """The extra instructions for a reply with Python, naming its Excel files."""
    names = ", ".join(f"`{name}`" for name in python.file_names)
    files = f"The files in it are: {names}." if names else "No files are attached."
    text = PYTHON_INSTRUCTIONS_FILE.read_text(encoding="utf-8")
    return text.replace(FILES_PLACEHOLDER, files)


def format_today(today: date) -> str:
    """The date as the model reads it, such as "Thursday 29 October 2026"."""
    # Built by hand, because strftime's day-without-zero flag differs between
    # Windows and macOS.
    return f"{today:%A} {today.day} {today:%B %Y}"


class NotesSearchStarted:
    """Yielded by `Agent.stream_reply` when the agent starts searching the notes."""


class CalculationStarted:
    """Yielded by `Agent.stream_reply` when the agent starts a calculation."""


class WebSearchStarted:
    """Yielded by `Agent.stream_reply` when a web search starts."""


class PythonStarted:
    """Yielded by `Agent.stream_reply` when OpenAI reports a run of Python."""


class Agent:
    """The chatbot: a LangChain agent that answers from the chat's messages,
    searching the notes when a question calls for it."""

    def __init__(
        self,
        chat_model: BaseChatModel,
        notes_search: NotesSearch,
        today: Callable[[], date] = date.today,
        web_search: WebSearch | None = None,
    ) -> None:
        self._chat_model = chat_model
        self._notes_search = notes_search
        # The clock is a parameter so tests can fix the date.
        self._today = today
        # With no location the agent has no web search (the tests that don't
        # care about it, and anything that mustn't spend on it).
        self._web_search = web_search
        # Read from their Markdown file, so the agent's behaviour can be changed
        # without touching code. The date is filled in for each reply.
        self._instructions = load_instructions(notes_search.modules)

    async def stream_reply(
        self,
        messages: list[AnyMessage],
        found: FoundNotes,
        usage: UsageLog | None = None,
        web: FoundWeb | None = None,
        runs: ToolRuns | None = None,
        python: PythonReply | None = None,
    ) -> AsyncIterator[
        str | NotesSearchStarted | WebSearchStarted | CalculationStarted | PythonStarted
    ]:
        """Yield the reply's text as the model produces it, a
        `NotesSearchStarted` whenever it starts a notes search and a
        `WebSearchStarted` whenever a web search starts. Every notes
        result it is shown is recorded in `found`, the web pages it cites in
        `web`, the calculations it makes in `runs`, and what the model calls and
        searches cost in `usage`. With `python`, the model also has that
        sandbox, and what it runs and makes is recorded there and in `runs`."""
        usage = usage if usage is not None else UsageLog()
        web = web if web is not None else FoundWeb()
        runs = runs if runs is not None else ToolRuns()
        # Worked out here, not at start-up, so it stays right if the app runs
        # past midnight.
        instructions = self._instructions.replace(
            TODAY_PLACEHOLDER, format_today(self._today())
        )
        if python is not None:
            instructions += "\n\n" + python_instructions(python)
        usage.begin_call(
            len(instructions) + sum(message_characters(m) for m in messages)
        )
        # With no modules there are no notes to search.
        tools: list = (
            [self._notes_search.tool(found, usage)]
            if self._notes_search.modules
            else []
        )
        tools += calculator_tools(runs)
        if self._web_search is not None:
            tools.append(web_search_tool(self._web_search))
        if python is not None:
            tools.append(python.tool())
        # A fresh agent for each reply, so its tool records into this reply's
        # `found`. Building one takes about a millisecond.
        chat_model = self._chat_model
        # Extra things the reply must carry, which OpenAI leaves out unless asked:
        # every page a search read, and what the code printed.
        include: list[str] = []
        if self._web_search is not None:
            include.append(SOURCES_INCLUDE)
        if python is not None:
            include.append(INCLUDE_OUTPUTS)
        if include and isinstance(chat_model, ChatOpenAI):
            chat_model = chat_model.model_copy(update={"include": include})
        graph = create_agent(chat_model, tools=tools, system_prompt=instructions)
        # Searches already announced when they started, so that one reported
        # only when it finishes is announced then.
        announced = 0
        # "custom" carries the start of each web search, which LangChain's own
        # messages leave out until the search is over.
        async for mode, data in graph.astream(
            {"messages": messages}, stream_mode=["messages", "custom"]
        ):
            if mode == "custom":
                if data.get(SEARCH_STARTED):
                    announced += 1
                    yield WebSearchStarted()
                continue
            chunk, _metadata = data
            if isinstance(chunk, ToolMessage):
                # The search results, which aren't shown. The model is called
                # again with them.
                usage.continue_after_search(len(chunk.text))
                continue
            if not isinstance(chunk, AIMessageChunk):
                continue
            usage.note_output(
                len(chunk.text)
                + sum(len(c["args"] or "") for c in chunk.tool_call_chunks)
            )
            # OpenAI's report comes in a last, empty piece of each call.
            if chunk.usage_metadata:
                usage.report_call(chunk.usage_metadata)
            # The first piece of a tool call carries the tool's name.
            if any(c["name"] == SEARCH_TOOL_NAME for c in chunk.tool_call_chunks):
                yield NotesSearchStarted()
            for call in chunk.tool_call_chunks:
                if call["name"] in CALCULATOR_TOOL_NAMES:
                    yield CalculationStarted()
            for _ in range(web.read(chunk)):
                usage.add_web_search()
                if web.search_count > announced:
                    announced += 1
                    yield WebSearchStarted()
            if python is not None:
                for _ in range(python.read(chunk)):
                    yield PythonStarted()
            if chunk.text:
                yield str(chunk.text)
