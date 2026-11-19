"""One-off check that the real models support what the app needs.

Run with `uv run askmynotes-check-model`. It makes four tiny calls to
OpenAI (streaming, tool calling, image input, embeddings), costing a
fraction of a penny, and prints pass or fail for each. It prints the
model names but never the API key.

`uv run askmynotes-check-model --web` runs six checks instead, through OpenAI's
Responses API with `store=False`: streaming and usage, a function tool, an
image, OpenAI's web search, a request to "search the web" for something the
model already knows, and whether the pages a search reads are counted in the
usage. They cost under five cents in all.

`uv run askmynotes-check-model --web-detail` looks closer at web search: when
OpenAI reports a search starting, what the pages it read look like, and how a
question needing a search and a calculation goes. About 5 to 10 cents.

`uv run askmynotes-check-model --python` checks OpenAI's Code Interpreter: it
creates a 1 GB sandbox (a "container") holding a tiny made-up Excel file, has
the model read it with Python and draw a chart, downloads the chart, and deletes
the container. It costs about 3 cents plus tokens.
"""

import asyncio
import base64
import io
import re
import struct
import sys
import time
import zlib
from collections.abc import Callable
from typing import Any

from langchain.agents import create_agent
from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessageChunk, HumanMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from openai import OpenAI
from openpyxl import Workbook

from askmynotes.agent.agent import Agent
from askmynotes.calculator.tools import ToolRuns, calculator_tools
from askmynotes.notes.search import FoundNotes, NotesSearch
from askmynotes.notes.store import create_embeddings
from askmynotes.settings import EnvSettings, WebSearch, load_env_settings
from askmynotes.web.search import SOURCES_INCLUDE, FoundWeb, web_search_tool

WEB_SEARCH_TOOL = {
    "type": "web_search",
    "user_location": {
        "type": "approximate",
        "country": "GB",
        "timezone": "Europe/London",
    },
}


def red_square_png() -> bytes:
    """Build a tiny solid-red PNG in memory, so no image file is needed."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    size = 32
    row = b"\x00" + b"\xff\x00\x00" * size  # filter byte, then red RGB pixels
    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(row * size))
        + chunk(b"IEND", b"")
    )


@tool
def get_magic_number() -> int:
    """Return the magic number."""
    return 42


def check_streaming(model: ChatOpenAI) -> str:
    chunks = [c.text for c in model.stream("Say hello in three words.")]
    if len(chunks) < 2:
        raise RuntimeError(f"expected a streamed reply, got {len(chunks)} chunk(s)")
    return f"{len(chunks)} chunks"


def check_tool_calling(model: ChatOpenAI) -> str:
    reply = model.bind_tools([get_magic_number]).invoke(
        "What is the magic number? Use the tool."
    )
    if not reply.tool_calls or reply.tool_calls[0]["name"] != "get_magic_number":
        raise RuntimeError("the model did not call the tool")
    return "called get_magic_number"


def check_image_input(model: ChatOpenAI) -> str:
    image = base64.b64encode(red_square_png()).decode()
    reply = model.invoke(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What single colour is this image?"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image}"},
                    },
                ],
            }
        ]
    )
    if "red" not in reply.text.lower():
        raise RuntimeError(f"expected 'red', got: {reply.text!r}")
    return "saw a red image"


def check_embeddings(embeddings: Embeddings) -> str:
    vector = embeddings.embed_query("Depreciation spreads an asset's cost.")
    return f"{len(vector)} dimensions"


def responses_model(env: EnvSettings) -> ChatOpenAI:
    """The chat model in Responses API mode, as the app will use it."""
    return ChatOpenAI(
        model=env.chat_model,
        api_key=env.openai_api_key,
        use_responses_api=True,
        output_version="responses/v1",
        store=False,
        stream_usage=True,
    )


def stream_whole(model: Runnable, prompt: str) -> AIMessageChunk:
    """Stream a call and add its pieces up into one message."""
    whole: AIMessageChunk | None = None
    pieces = 0
    for piece in model.stream(prompt):
        pieces += 1
        whole = piece if whole is None else whole + piece
    if whole is None:
        raise RuntimeError("no pieces came back")
    whole.response_metadata["pieces"] = pieces
    return whole


def blocks_of(message: AIMessageChunk, kind: str) -> list[dict]:
    """The message's content blocks of one kind, such as web_search_call."""
    if isinstance(message.content, str):
        return []
    return [b for b in message.content if isinstance(b, dict) and b.get("type") == kind]


def citations_of(message: AIMessageChunk) -> list[dict]:
    """Every url_citation annotation in the message's text blocks."""
    return [
        a
        for block in blocks_of(message, "text")
        for a in block.get("annotations", [])
        if a.get("type") == "url_citation"
    ]


def check_responses_streaming(model: ChatOpenAI) -> str:
    whole = stream_whole(model, "Say hello in three words.")
    pieces = whole.response_metadata["pieces"]
    if pieces < 2 or not whole.text or not whole.usage_metadata:
        raise RuntimeError(f"{pieces} piece(s), usage {whole.usage_metadata}")
    return f"{pieces} pieces, usage {dict(whole.usage_metadata)}"


def check_web_search(model: ChatOpenAI) -> str:
    whole = stream_whole(
        model.bind_tools([WEB_SEARCH_TOOL]),
        "What is the current Bank of England base rate? Search the web and cite it.",
    )
    searches, urls = blocks_of(whole, "web_search_call"), citations_of(whole)
    if not searches or not urls:
        raise RuntimeError(f"{len(searches)} search(es), {len(urls)} citation(s)")
    # The shapes the app's code will be written against.
    kinds = [b.get("type") for b in whole.content]
    print(f"      content block kinds: {kinds}")
    print(
        f"      search block: {sorted(searches[0])}, action {searches[0].get('action')}"
    )
    print(f"      citation: {sorted(urls[0])}")
    print(f"      usage: {dict(whole.usage_metadata)}")
    return f"{len(searches)} search(es), {len(urls)} citation(s)"


def check_search_when_asked(model: ChatOpenAI) -> str:
    whole = stream_whole(
        model.bind_tools([WEB_SEARCH_TOOL]),
        "Search the web for the capital of France, and tell me what it is.",
    )
    searches = blocks_of(whole, "web_search_call")
    if not searches:
        raise RuntimeError("it answered from memory without searching")
    return f"{len(searches)} search(es)"


def check_search_tokens(model: ChatOpenAI) -> str:
    question = "What is the current Bank of England base rate? One sentence."
    plain = stream_whole(model, question).usage_metadata
    searched = stream_whole(
        model.bind_tools([WEB_SEARCH_TOOL]), question + " Search the web."
    ).usage_metadata
    assert plain and searched
    counted = searched["input_tokens"] > plain["input_tokens"]
    return (
        f"input tokens {plain['input_tokens']} without search, "
        f"{searched['input_tokens']} with: pages read "
        f"{'are' if counted else 'are not'} counted"
    )


def web_checks(env: EnvSettings) -> list[tuple[str, Callable[[], str]]]:
    """The six `--web` checks, all through the Responses API."""
    model, name = responses_model(env), env.chat_model
    return [
        (f"{name} streams text with usage", lambda: check_responses_streaming(model)),
        (f"{name} calls a function tool", lambda: check_tool_calling(model)),
        (f"{name} reads an image", lambda: check_image_input(model)),
        (f"{name} searches the web and cites pages", lambda: check_web_search(model)),
        (f"{name} searches when asked", lambda: check_search_when_asked(model)),
        (f"{name} counts the pages it reads", lambda: check_search_tokens(model)),
    ]


SEARCH_AND_CALCULATE_QUESTIONS = (
    "What is the Bank of England base rate now, and what is the simple interest "
    "on £2,500 at that rate for 18 months?",
    "What is today's pound to US dollar exchange rate? Convert £1,200 to dollars.",
    "Search the web for the current UK corporation tax main rate, then work out "
    "the tax on profits of £340,000.",
)


def compressed(items: list[str]) -> str:
    """A list with repeats squashed, such as `text x30, calc, text x12`."""
    parts: list[str] = []
    for item in items:
        if parts and parts[-1][0] == item:
            parts[-1][1] += 1
        else:
            parts.append([item, 1])
    return ", ".join(f"{name} x{n}" if n > 1 else name for name, n in parts)


def web_detail_checks(env: EnvSettings) -> list[tuple[str, Callable[[], str]]]:
    """The four `--web-detail` checks: how OpenAI reports a search while it runs,
    what the searched pages look like, and how searching plus calculating goes."""
    name = env.chat_model
    client = OpenAI(api_key=env.openai_api_key)
    model = responses_model(env).model_copy(update={"include": [SOURCES_INCLUDE]})
    raw: dict[str, Any] = {}

    def raw_search() -> None:
        """One search straight from OpenAI's stream, without LangChain. Checks 1
        and 2 both read it, so it is paid for once."""
        if raw:
            return
        started = time.monotonic()
        events: list[tuple[str, float]] = []
        stream = client.responses.create(
            model=env.chat_model,
            input="What is the current Bank of England base rate? Search the web.",
            tools=[WEB_SEARCH_TOOL],
            include=[SOURCES_INCLUDE],
            store=False,
            stream=True,
        )
        for event in stream:
            events.append((event.type, time.monotonic() - started))
            item = getattr(event, "item", None)
            if item is not None and item.type == "web_search_call":
                raw[event.type] = item.model_dump(mode="json")
        raw["events"] = events

    def search_events() -> str:
        raw_search()
        events: list[tuple[str, float]] = raw["events"]
        print(f"      event order: {compressed([kind for kind, _ in events])}")
        first = {}
        for kind, seconds in events:
            first.setdefault(kind, seconds)
        started_at = first.get("response.output_item.added")
        searching_at = first.get("response.web_search_call.searching")
        finished_at = next(
            (s for k, s in events if k == "response.web_search_call.completed"), None
        )
        done_at = next((s for k, s in events if k == "response.output_item.done"), None)
        print(
            f"      seconds: output_item.added {started_at}, searching "
            f"{searching_at}, completed {finished_at}, first output_item.done {done_at}"
        )
        print(f"      item when added: {raw.get('response.output_item.added')}")
        if started_at is None:
            raise RuntimeError("OpenAI sent no event when the search started")
        return "a start event arrives before the finish"

    def searched_pages() -> str:
        raw_search()
        item = raw.get("response.output_item.done")
        if item is None:
            raise RuntimeError("no finished search item")
        action = item.get("action") or {}
        sources = action.get("sources") or []
        print(f"      action keys: {sorted(action)}; query: {action.get('query')!r}")
        print(f"      {len(sources)} searched page(s); first three:")
        for source in sources[:3]:
            print(f"        {source}")
        shapes = sorted({tuple(sorted(source)) for source in sources})
        print(f"      source shapes: {shapes}")
        if not sources:
            raise RuntimeError("the include list returned no searched pages")
        return (
            f"{len(sources)} pages, with keys {sorted({k for s in sources for k in s})}"
        )

    def search_then_calculate() -> str:
        graph = create_agent(
            model,
            tools=[web_search_tool(WebSearch(country="GB", timezone="Europe/London"))]
            + calculator_tools(ToolRuns()),
            system_prompt="Search the web for any current figure, then calculate.",
        )
        result = graph.invoke(
            {"messages": [HumanMessage(SEARCH_AND_CALCULATE_QUESTIONS[0])]}
        )
        steps = []
        for message in result["messages"][1:]:
            kinds = (
                [b.get("type") for b in message.content if isinstance(b, dict)]
                if isinstance(message.content, list)
                else ["text"]
            )
            steps.append(f"{message.type}{kinds}")
        print(f"      messages: {steps}")
        final = result["messages"][-1]
        if not final.text:
            raise RuntimeError("the reply ended with no text")
        return f"{len(result['messages']) - 1} messages, ended with text"

    def both_tools() -> str:
        async def ask_all() -> list[str]:
            # One event loop for all of them: the model's client belongs to it.
            return [
                await ask_with_both_tools(model, question)
                for question in SEARCH_AND_CALCULATE_QUESTIONS
            ]

        return "; ".join(asyncio.run(ask_all()))

    return [
        (f"{name} sends a search-started event", search_events),
        (f"{name} lists the pages a search read", searched_pages),
        (f"{name} searches, then calculates, in one reply", search_then_calculate),
        (f"{name} handles questions needing both tools", both_tools),
    ]


async def ask_with_both_tools(model: ChatOpenAI, question: str) -> str:
    """Put one question to the app's own agent, with its real instructions, and
    describe what it did: the order of searching, calculating and writing."""
    agent = Agent(
        model,
        NotesSearch(None, [], 0),  # type: ignore[arg-type]  # no modules: never used
        web_search=WebSearch(country="GB", timezone="Europe/London"),
    )
    web, runs = FoundWeb(), ToolRuns()
    steps: list[str] = []
    text: list[str] = []
    async for piece in agent.stream_reply(
        [HumanMessage(question)], FoundNotes(), None, web, runs
    ):
        steps.append("text" if isinstance(piece, str) else type(piece).__name__)
        if isinstance(piece, str):
            text.append(piece)
    answer = "".join(text)
    links = len(re.findall(r"\]\(https?://", answer))
    summary = (
        f"{len(web.sources)} cited, {web.search_count} search(es), "
        f"{len(runs.runs)} calculation(s), :::web block "
        f"{'yes' if ':::web' in answer else 'NO'}, {links} link(s) in the text"
    )
    print(f"      {question[:50]!r}")
    print(f"        order: {compressed(steps)}")
    print(f"        {summary}")
    return summary


def returns_xlsx() -> bytes:
    """A tiny made-up spreadsheet of yearly returns."""
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append(["Year", "Return"])
    for year, value in [(2021, 0.05), (2022, -0.02), (2023, 0.08), (2024, 0.04)]:
        sheet.append([year, value])
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def python_checks(env: EnvSettings) -> list[tuple[str, Callable[[], str]]]:
    """The `--python` check: one container, one run of Python, one chart."""
    client = OpenAI(api_key=env.openai_api_key)
    model, name = responses_model(env), env.chat_model

    def run() -> str:
        before = len(list(client.containers.list(limit=100)))
        container = client.containers.create(name="askmynotes-check", memory_limit="1g")
        try:
            client.containers.files.create(
                container.id, file=("returns.xlsx", returns_xlsx())
            )
            tool = {"type": "code_interpreter", "container": container.id}
            whole = stream_whole(
                model.bind_tools([tool]),
                "Use Python to read /mnt/data/returns.xlsx, work out the average "
                "return, and save a bar chart of Return by Year as "
                "/mnt/data/returns.png. Then say the average in one sentence.",
            )
            runs = blocks_of(whole, "code_interpreter_call")
            if not runs:
                raise RuntimeError("it never ran Python")
            kinds = [b.get("type") for b in whole.content]
            print(f"      content block kinds: {kinds}")
            print(f"      run block: {sorted(runs[0])}")
            print(f"      first run's code: {str(runs[0].get('code'))[:200]!r}")
            print(f"      outputs: {str(runs[0].get('outputs'))[:200]}")
            print(f"      pieces: {whole.response_metadata['pieces']}")
            print(f"      usage: {dict(whole.usage_metadata)}")
            citations = [
                a
                for block in blocks_of(whole, "text")
                for a in block.get("annotations", [])
                if a.get("type") == "container_file_citation"
            ]
            print(f"      file citations: {citations}")
            files = list(client.containers.files.list(container.id))
            print(f"      container files: {[(f.path, f.bytes) for f in files]}")
            chart = next((f for f in files if f.path.endswith(".png")), None)
            if chart is None:
                raise RuntimeError("no chart file in the container")
            data = client.containers.files.content.retrieve(
                chart.id, container_id=container.id
            ).read()
            if data[1:4] != b"PNG":
                raise RuntimeError("the chart isn't a PNG")
            return f"{len(runs)} run(s), chart of {len(data)} bytes downloaded"
        finally:
            client.containers.delete(container.id)
            after = len(list(client.containers.list(limit=100)))
            print(f"      containers: {before} before, {after} after deleting")

    return [(f"{name} runs Python in a sandbox and draws a chart", run)]


def main() -> None:
    """Run the four checks (or, with --web, the six web checks, or with --python,
    the Python check) and exit with an
    error if any fail."""
    env = load_env_settings()
    if "--python" in sys.argv:
        checks = python_checks(env)
    elif "--web-detail" in sys.argv:
        checks = web_detail_checks(env)
    elif "--web" in sys.argv:
        checks = web_checks(env)
    else:
        model = ChatOpenAI(model=env.chat_model, api_key=env.openai_api_key)
        embeddings = create_embeddings(env)
        checks = [
            (f"{env.chat_model} streams text", lambda: check_streaming(model)),
            (f"{env.chat_model} calls a tool", lambda: check_tool_calling(model)),
            (f"{env.chat_model} reads an image", lambda: check_image_input(model)),
            (f"{env.embedding_model} embeds", lambda: check_embeddings(embeddings)),
        ]
    failed = 0
    for name, check in checks:
        try:
            print(f"PASS  {name}: {check()}")
        except Exception as error:  # report every check, not just the first failure
            failed += 1
            print(f"FAIL  {name}: {type(error).__name__}: {error}")
    if failed:
        raise SystemExit(f"{failed} check(s) failed")


if __name__ == "__main__":
    main()
