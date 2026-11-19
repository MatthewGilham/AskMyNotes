"""A fake chat model (and fake embeddings) for tests.

Tests must never call a paid model, so they run the app with this instead. It
is also what `uv run askmynotes --fake-model` uses for the Playwright tests,
which is why it lives in the app and not in `backend/tests/`.
"""

import asyncio
import json
import struct
import threading
import time
import uuid
import zlib
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass
from typing import Any

import httpx
import openai
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.messages.ai import UsageMetadata
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable
from pydantic import Field

from askmynotes.usage.log import report_embedding
from askmynotes.web.search import announce_search_started


@dataclass
class FakeReply:
    """A reply, with an optional pause before each word (to test Stop).

    With a `tool_call`, such as `{"name": "search_notes", "args": {...}}`, the
    model calls that tool after its text, as the real model does to search.
    """

    text: str = ""
    delay_seconds: float = 0.0
    tool_call: dict[str, Any] | None = None
    # The tokens it reports using, like OpenAI's report at the end of a call.
    # `reports_usage=False` leaves the report out, as when a reply is cut short.
    input_tokens: int = 1000
    cached_tokens: int = 200
    output_tokens: int = 500
    reports_usage: bool = True
    # Web searches OpenAI reports before the text, and the pages the text cites
    # (each `{"title": ..., "url": ...}`), as the real model's reply carries them.
    web_searches: int = 0
    web_citations: tuple[dict[str, str], ...] = ()
    # The addresses the searches read (the real model reports them with each
    # search), how long each search takes, and some text written before them.
    web_read: tuple[str, ...] = ()
    search_seconds: float = 0.0
    intro: str = ""
    # The connection drops after the text, as when OpenAI is unreachable.
    fails_after_text: bool = False
    # Explicit stream boundaries for regressions involving tokens split mid-word.
    text_chunks: tuple[str, ...] | None = None
    # Runs of Python, each `{"code": ..., "output": ...}`, reported before the
    # text, and the names of the files the text points to (see `FakeSandbox`).
    python_runs: tuple[dict[str, str], ...] = ()
    python_files: tuple[str, ...] = ()

    def usage(self) -> UsageMetadata | None:
        """The usage report this reply ends with."""
        if not self.reports_usage:
            return None
        return UsageMetadata(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            total_tokens=self.input_tokens + self.output_tokens,
            input_token_details={"cache_read": self.cached_tokens},
        )


Responder = Callable[[list[BaseMessage]], "str | FakeReply"]


def text_of(message: BaseMessage) -> str:
    """The text of a message, whether its content is a string or a list of parts."""
    if isinstance(message.content, str):
        return message.content
    return " ".join(
        part["text"]
        for part in message.content
        if isinstance(part, dict) and part.get("type") == "text"
    )


def count_images(message: BaseMessage) -> int:
    """How many images a message carries."""
    if isinstance(message.content, str):
        return 0
    return sum(
        1
        for part in message.content
        if isinstance(part, dict) and part.get("type") == "image_url"
    )


def last_human_text(messages: list[BaseMessage]) -> str:
    """The text of the newest message from the student."""
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return text_of(message)
    return ""


# What the Playwright tests' fake model answers after searching the notes.
FAKE_NOTES_ANSWER = (
    "Your notes say depreciation spreads the cost of an asset over its useful "
    "life.\n\n"
    ":::beyond\nSome firms also use the reducing-balance method.\n:::\n\n"
    "Sources used: S1"
)


FAKE_WEB_PAGES = (
    {"title": "Bank Rate | Example Bank", "url": "https://www.example-bank.test/rate"},
    {"title": "Rates explained", "url": "https://news.example.test/rates"},
)
# What the fake searches read: the two cited pages, written as OpenAI writes them
# (one with tracking, one with a final slash), and three that the answer doesn't
# cite.
FAKE_WEB_READ = (
    "https://www.example-bank.test/rate/",
    "https://news.example.test/rates?utm_source=openai",
    "https://regulator.example.test/policy/statement",
    "https://data.example.test/series/rate",
    "https://blog.example.test/2026/10/rates-roundup",
)
FAKE_WEB_ANSWER = (
    ":::web\nThe rate is 3.75% "
    "([example-bank.test](https://www.example-bank.test/rate)), and it has held "
    "for months ([news.example.test](https://news.example.test/rates)).\n:::"
)


def web_reply(text: str, messages: list[BaseMessage]) -> FakeReply:
    """The scripted answer to a message containing "web": two web searches and
    a "From the web" block citing two pages. With "mixed" too, the agent also
    searches the notes first, and answers with all three kinds of content."""
    cited = {
        "web_searches": 2,
        "web_citations": FAKE_WEB_PAGES,
        "web_read": FAKE_WEB_READ,
    }
    if "fail" in text.lower():
        # Searched, started writing, then lost the connection.
        return FakeReply(
            "The rate is", web_searches=1, fails_after_text=True, delay_seconds=0.3
        )
    if "nopages" in text.lower():
        return FakeReply("I searched but nothing useful came back.", web_searches=1)
    if "uncited" in text.lower():
        # Searched, read pages, and answered without citing any.
        return FakeReply(
            "The rate is about 3.75%.", web_searches=1, web_read=FAKE_WEB_READ
        )
    if "calc" in text.lower():
        return search_then_calculate_reply(messages)
    if "slowsearch" in text.lower():
        # Each search takes a while, so there is time to see the status.
        return FakeReply(FAKE_WEB_ANSWER, search_seconds=1.5, **cited)
    if "intro" in text.lower():
        return FakeReply(
            FAKE_WEB_ANSWER,
            intro="Let me check that for you. ",
            search_seconds=0.8,
            **cited,
        )
    if "mixed" not in text.lower():
        if "slow" in text.lower():
            return FakeReply((FAKE_WEB_ANSWER + "\n\n") * 5, delay_seconds=0.6, **cited)
        return FakeReply(FAKE_WEB_ANSWER, **cited)
    if not isinstance(messages[-1], ToolMessage):
        return FakeReply(tool_call={"name": "search_notes", "args": {"query": text}})
    return FakeReply(
        "Your notes say depreciation spreads the cost of an asset.\n\n"
        f"{FAKE_WEB_ANSWER}\n\n"
        ":::beyond\nSome firms also use the reducing-balance method.\n:::\n\n"
        "Sources used: S1",
        **cited,
    )


def search_then_calculate_reply(messages: list[BaseMessage]) -> FakeReply:
    """The scripted answer to a web question that also needs a calculation: the
    model searches, calls the calculator, then writes the answer in a later call.
    That answer links its page as plain Markdown, with no `url_citation`, as the
    real model sometimes does."""
    if not isinstance(messages[-1], ToolMessage):
        return FakeReply(
            web_searches=1,
            web_read=FAKE_WEB_READ,
            tool_call={
                "name": "calculate",
                "args": {"expression": "2500 * 0.0375 * 1.5"},
            },
        )
    return FakeReply(
        ":::web\nThe rate is 3.75% "
        "([example-bank.test](https://www.example-bank.test/rate)).\n:::\n\n"
        "So 18 months of simple interest on £2,500 comes to £140.63."
    )


FAKE_PYTHON_CODE = """import pandas as pd
frame = pd.read_excel("/mnt/data/figures.xlsx")
print(frame["Amount"].mean())
frame.to_csv("/mnt/data/summary.csv")"""
FAKE_PYTHON_ANSWER = (
    "I used `figures.xlsx`. The average amount was 100.5.\n\n"
    "![Amounts](sandbox:/mnt/data/amounts.png)\n\n"
    "[Download summary.csv](sandbox:/mnt/data/summary.csv)"
)


def python_reply(text: str) -> FakeReply:
    """The scripted answer to a message containing "python": one run of Python
    that prints a number, and an answer pointing to a chart and a CSV file.
    "bigfile", "manyfiles" and "svgfile" point to files the limits or the safety
    rules refuse; "longoutput" prints 250 lines, "pyerror" prints a traceback,
    "pyfail" loses the connection after the run, "slow" makes the answer slow."""
    lowered = text.lower()
    output = "100.5\n"
    files: tuple[str, ...] = ("amounts.png", "summary.csv")
    if "longoutput" in lowered:
        output = "".join(f"line {number}\n" for number in range(1, 251))
    if "pyerror" in lowered:
        output = 'Traceback (most recent call last):\nKeyError: "Missing"\n'
    if "bigfile" in lowered:
        files = ("big.csv", "summary.csv")
    if "manyfiles" in lowered:
        files = ("one.csv", "two.csv", "three.csv")
    if "svgfile" in lowered:
        files = ("figure.svg",)
    runs = ({"code": FAKE_PYTHON_CODE, "output": output},)
    if "pyfail" in lowered:
        return FakeReply(
            "The average is", python_runs=runs, fails_after_text=True, delay_seconds=0.3
        )
    return FakeReply(
        FAKE_PYTHON_ANSWER,
        delay_seconds=0.4 if "slow" in lowered else 0.0,
        python_runs=runs,
        python_files=files,
    )


LINE_CHART = """{"type": "line", "title": "NPV against the discount rate", \
"xLabel": "Discount rate", "yLabel": "NPV", "format": "currency", \
"series": ["NPV"], "data": [{"x": "0%", "NPV": 120}, {"x": "5%", "NPV": 80}, \
{"x": "10%", "NPV": 41.5}, {"x": "15%", "NPV": 8}]}"""
BAR_CHART = """{"type": "bar", "title": "Revenue and costs", "yLabel": "Amount", \
"format": "currency", "currency": "$", "series": ["Revenue", "Costs"], \
"data": [{"x": "2024", "Revenue": 100, "Costs": 70}, \
{"x": "2025", "Revenue": 130, "Costs": 85}]}"""
PIE_CHART = """{"type": "pie", "title": "Portfolio weights", "format": "percent", \
"series": ["Weight"], "data": [{"x": "Shares", "Weight": 0.6}, \
{"x": "Bonds", "Weight": 0.3}, {"x": "Cash", "Weight": 0.1}]}"""

FLOWCHART = """flowchart TD
    A[Is there an offer?] -->|Yes| B[Is it accepted?]
    A -->|No| X[No contract]
    B -->|Yes| C[Is there consideration?]
    B -->|No| X
    C -->|Yes| D[Contract formed]
    C -->|No| X"""
SEQUENCE = """sequenceDiagram
    Student->>Lecturer: Asks a question
    Lecturer-->>Student: Explains"""
TIMELINE = """timeline
    title Standards
    2001 : IAS 1
    2013 : IFRS 10"""

# Keywords that make the fake model answer with pictures, and what it says.
PICTURE_ANSWERS = {
    "bluechart": (":::web\nRates over time:\n\n```chart\n" + LINE_CHART + "\n```\n:::"),
    "brokenchart": (
        "A chart that can't be drawn:\n\n```chart\n"
        '{"type": "scatter", "title": "Oops", "series": ["a"], "data": []}'
        "\n```"
    ),
    "brokendiagram": (
        "A diagram that can't be drawn:\n\n```mermaid\nflowchart TD\n    A -->\n```"
    ),
    "diagrams": (
        "A flowchart:\n\n```mermaid\n" + FLOWCHART + "\n```\n\n"
        "A sequence diagram:\n\n```mermaid\n" + SEQUENCE + "\n```\n\n"
        "A timeline:\n\n```mermaid\n" + TIMELINE + "\n```"
    ),
    "charts": (
        "A line chart:\n\n```chart\n" + LINE_CHART + "\n```\n\n"
        "A bar chart:\n\n```chart\n" + BAR_CHART + "\n```\n\n"
        "A pie chart:\n\n```chart\n" + PIE_CHART + "\n```\n\nThat is all."
    ),
}


def picture_reply(text: str, answer: str) -> FakeReply:
    """A reply made of pictures. "slow" streams it slowly, so there is time to
    see "Drawing…"."""
    slow = "slow" in text.lower()
    return FakeReply(answer, delay_seconds=0.15 if slow else 0.0)


FAKE_CODE_ANSWER = """Here is the idea in Python:

```python
def npv(rate, flows):
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(flows))
```

And the same data in SQL:

```sql
SELECT module, AVG(mark) AS average FROM results GROUP BY module;
```

A block with no language:

```
plain text
:::
```
"""

FAKE_CALLOUT_ANSWER = """:::formula
\\( \\text{NPV} = \\sum_t \\frac{CF_t}{(1+r)^t} \\)
:::

:::tip
Write the formula before you put numbers in.
:::

:::mistake
Discounting the cash flow at time 0.
:::

:::example
1. List the cash flows.
2. Discount each one.
3. Add them up.
:::

:::beyond
Outside your notes, this one is from a textbook:

:::formula
\\( E(R) = r_f + \\beta (R_m - r_f) \\)
:::
:::
"""


def calculation_reply(text: str, messages: list[BaseMessage]) -> FakeReply:
    """The scripted answer to a message containing "calc": it calls the
    calculator, then the equation solver, then answers. With "wrong" it first
    asks for 1/0, which is refused, and carries on. "slow" makes the answer
    slow, so there is time to see "Calculating…"."""
    plan = [
        {"name": "calculate", "args": {"expression": "1000 * (1 + 0.05)^2"}},
        {
            "name": "solve_equation",
            "args": {"equation": "1100 = 1000 * (1 + r)", "unknown": "r"},
        },
    ]
    if "wrong" in text.lower():
        plan.insert(0, {"name": "calculate", "args": {"expression": "1 / 0"}})
    # The calculations already made for this question.
    done = 0
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            break
        done += isinstance(message, ToolMessage)
    if done < len(plan):
        return FakeReply(tool_call=plan[done])
    answer = "After two years it is worth 1102.5, and the rate was 0.1."
    return FakeReply(answer, delay_seconds=0.6 if "slow" in text.lower() else 0.0)


def default_responder(messages: list[BaseMessage]) -> str | FakeReply:
    """The scripted behaviour used by the Playwright tests.

    - A request for a chat title gets the first few words of the message.
    - A request to summarise a long chat gets a short fixed summary.
    - A message containing "my notes" searches the notes, then answers with a
      "Beyond your notes" block and a sources line naming S1.
    - A message containing "python" runs Python once and answers pointing to a
      chart and a CSV file ("bigfile", "manyfiles", "svgfile", "longoutput",
      "pyerror", "pyfail" and "slow" change it; see `python_reply`).
    - A message containing "web" searches the web twice and answers in a
      "From the web" block citing two pages ("mixed" adds a notes search and a
      "Beyond your notes" block; "fail" loses the connection after a search).
    - A message containing "calc" uses the calculator twice and answers
      ("wrong" adds a refused calculation first; "slow" slows the answer).
    - A message containing "codeblocks" answers with Python, SQL and plain
      code blocks; "callouts" with all four callout boxes, one of them inside a
      "Beyond your notes" block ("slow" streams them slowly).
    - A message containing "diagrams" answers with a flowchart, a sequence
      diagram and a timeline; "charts" with a line, a bar and a pie chart;
      "bluechart" with a chart inside a "From the web" block; "brokendiagram"
      and "brokenchart" with ones that can't be drawn ("slow" streams the reply
      slowly).
    - A message containing "fail" makes the model fail, like a lost connection.
    - A message containing "slow" streams slowly, so there's time to press Stop.
    - Anything else gets an echo with a table, a fraction and a dollar amount.
    """
    text = last_human_text(messages)
    first = messages[0]
    if isinstance(first, SystemMessage) and "running summary" in text_of(first):
        return "A summary of the earlier chat."
    if isinstance(first, SystemMessage) and "short title" in text_of(first):
        return " ".join(text.split()[:5]) or "Image chat"
    if "citationcheck" in text.lower():
        marker = "\ue200cite\ue202turn0search0\ue201"
        chunks = ("Before ", *marker, "after.", marker)
        if "partial" in text.lower():
            chunks = ("Before ", *marker[:12])
        return FakeReply(
            "".join(chunks),
            text_chunks=chunks,
            delay_seconds=0.12,
            fails_after_text="fail" in text.lower(),
        )
    if "my notes" in text.lower():
        if isinstance(messages[-1], ToolMessage):
            return FAKE_NOTES_ANSWER
        return FakeReply(tool_call={"name": "search_notes", "args": {"query": text}})
    for keyword, answer in PICTURE_ANSWERS.items():
        if keyword in text.lower():
            return picture_reply(text, answer)
    if "python" in text.lower():
        return python_reply(text)
    if "web" in text.lower():
        return web_reply(text, messages)
    if "calc" in text.lower():
        return calculation_reply(text, messages)
    if "codeblocks" in text.lower():
        return FakeReply(FAKE_CODE_ANSWER)
    if "callouts" in text.lower():
        slow = "slow" in text.lower()
        return FakeReply(FAKE_CALLOUT_ANSWER, delay_seconds=0.15 if slow else 0.0)
    if "fail" in text.lower():
        request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        raise openai.APIConnectionError(request=request)
    images = sum(count_images(m) for m in messages if isinstance(m, HumanMessage))
    reply = f"You said: {text}\n\n"
    if images:
        reply += f"I can see {images} image(s).\n\n"
    reply += (
        "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
        "Half is \\( \\frac{1}{2} \\), and $5 is five dollars."
    )
    if "slow" in text.lower():
        return FakeReply((reply + "\n\n") * 5, delay_seconds=0.15)
    return reply


class FakeChatModel(BaseChatModel):
    """Streams whatever its `responder` returns, and remembers what it was sent."""

    responder: Responder = default_responder
    received: list[list[BaseMessage]] = Field(default_factory=list)
    # The tools the agent offered, one list for each time it asked for them.
    offered_tools: list[list[Any]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "fake"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Runnable:
        """The agent offers the model its tools; the script decides what to call."""
        self.offered_tools.append(list(tools))
        return self

    def _reply_for(self, messages: list[BaseMessage]) -> FakeReply:
        self.received.append(list(messages))
        reply = self.responder(messages)
        return reply if isinstance(reply, FakeReply) else FakeReply(reply)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        reply = self._reply_for(messages)
        tool_calls = []
        if reply.tool_call is not None:
            tool_calls = [{**reply.tool_call, "id": new_tool_call_id()}]
        message = AIMessage(
            content=reply.text, tool_calls=tool_calls, usage_metadata=reply.usage()
        )
        return ChatResult(generations=[ChatGeneration(message=message)])

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        reply = self._reply_for(messages)
        for word in split_into_words(reply.intro):
            yield ChatGenerationChunk(message=AIMessageChunk(content=word))
        for number in range(reply.web_searches):
            # As in the real stream, the start of a search is announced first,
            # and the search then arrives as one finished block.
            announce_search_started()
            await asyncio.sleep(reply.search_seconds)
            query = f"fake search {number + 1}"
            search = {
                "type": "web_search_call",
                "id": f"ws_{uuid.uuid4().hex[:12]}",
                "status": "completed",
                "action": {
                    "type": "search",
                    "queries": [query],
                    "query": query,
                    "sources": [{"type": "url", "url": url} for url in reply.web_read]
                    or None,
                },
                "index": 0,
            }
            yield ChatGenerationChunk(message=AIMessageChunk(content=[search]))
        for run in reply.python_runs:
            # As in the real stream, a run arrives as one finished block.
            call = {
                "type": "code_interpreter_call",
                "id": f"ci_{uuid.uuid4().hex[:12]}",
                "code": run["code"],
                "container_id": "cntr_fake",
                "outputs": [{"type": "logs", "logs": run["output"]}],
                "status": "completed",
                "index": 0,
            }
            yield ChatGenerationChunk(message=AIMessageChunk(content=[call]))
        for word in (
            reply.text_chunks
            if reply.text_chunks is not None
            else split_into_words(reply.text)
        ):
            await asyncio.sleep(reply.delay_seconds)
            yield ChatGenerationChunk(message=AIMessageChunk(content=word))
        if reply.fails_after_text:
            request = httpx.Request("POST", "https://api.openai.com/v1/responses")
            raise openai.APIConnectionError(request=request)
        annotations: list[dict[str, Any]] = [
            {"type": "url_citation", "start_index": 0, "end_index": 0, **page}
            for page in reply.web_citations
        ]
        annotations += [
            {
                "type": "container_file_citation",
                "container_id": "cntr_fake",
                "file_id": f"cfile_fake_{name}",
                "filename": name,
                "start_index": 0,
                "end_index": 0,
            }
            for name in reply.python_files
        ]
        if annotations:
            text_block = {"type": "text", "annotations": annotations, "index": 1}
            yield ChatGenerationChunk(message=AIMessageChunk(content=[text_block]))
        if reply.tool_call is not None:
            # The whole call in one piece; the real model streams it in several.
            call_piece = {
                "name": reply.tool_call["name"],
                "args": json.dumps(reply.tool_call["args"]),
                "id": new_tool_call_id(),
                "index": 0,
            }
            yield ChatGenerationChunk(
                message=AIMessageChunk(content="", tool_call_chunks=[call_piece])
            )
        # Like OpenAI, the usage report is the last piece of a streamed call.
        usage = reply.usage()
        if usage is not None:
            yield ChatGenerationChunk(
                message=AIMessageChunk(content="", usage_metadata=usage)
            )


def split_into_words(text: str) -> list[str]:
    """The text split after each space, so the pieces join back into the exact
    text."""
    return text.replace(" ", " \0").split("\0")


def new_tool_call_id() -> str:
    """Each tool call has an id, which its result refers back to."""
    return f"call_{uuid.uuid4().hex[:12]}"


def fake_chart_png() -> bytes:
    """A small picture of four violet bars on a dark ground, as a PNG."""
    width, height = 240, 120
    heights = (40, 70, 55, 90)
    rows = []
    for y in range(height):
        row = bytearray(b"\x00")
        for x in range(width):
            bar, offset = divmod(x - 20, 50)
            inside = 0 <= bar < 4 and offset < 36 and y >= height - 10 - heights[bar]
            row += bytes((167, 139, 250) if inside else (24, 24, 40))
        rows.append(bytes(row))

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"".join(rows)))
        + chunk(b"IEND", b"")
    )


# The files the fake Python "makes", by name.
FAKE_SANDBOX_FILES: dict[str, bytes] = {
    "amounts.png": fake_chart_png(),
    "summary.csv": b"Year,Amount\n2024,100.5\n",
    "big.csv": b"x" * 1_100_000,
    "figure.svg": b"<svg xmlns='http://www.w3.org/2000/svg'><script>1</script></svg>",
}


class FakeSandbox:
    """A stand-in for OpenAI's sandbox that makes nothing and costs nothing. It
    remembers the containers it was asked for, the files it was given and which
    containers were deleted, so tests can check them."""

    def __init__(self, create_seconds: float = 0.0) -> None:
        self.created: list[str] = []
        self.uploaded: dict[str, list[str]] = {}
        self.deleted: list[str] = []
        self.fail_to_create = False
        # How long making a container takes, for testing Stop during it.
        self.create_seconds = create_seconds
        self._lock = threading.Lock()

    def create(self, files: list[tuple[str, bytes]]) -> str:
        time.sleep(self.create_seconds)
        if self.fail_to_create:
            request = httpx.Request("POST", "https://api.openai.com/v1/containers")
            raise openai.APIConnectionError(request=request)
        with self._lock:
            container_id = f"cntr_fake_{len(self.created) + 1}"
            self.created.append(container_id)
            self.uploaded[container_id] = [name for name, _ in files]
        return container_id

    def download(self, container_id: str, file_id: str) -> bytes:
        name = file_id.removeprefix("cfile_fake_")
        return FAKE_SANDBOX_FILES.get(name, f"fake {name}".encode())

    def delete(self, container_id: str) -> None:
        with self._lock:
            self.deleted.append(container_id)

    @property
    def open_containers(self) -> list[str]:
        """Containers that were created and not deleted."""
        return [c for c in self.created if c not in self.deleted]


# What each text embedded costs in the fake, so cost tests have known numbers.
FAKE_TOKENS_PER_TEXT = 10


class FakeEmbeddings(DeterministicFakeEmbedding):
    """Embeddings for tests: the same text always gets the same vector, and it
    counts how many texts it was asked to embed (to prove nothing was redone)."""

    size: int = 64
    texts_embedded: int = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.texts_embedded += len(texts)
        report_embedding("fake-embeddings", FAKE_TOKENS_PER_TEXT * len(texts))
        return super().embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        report_embedding("fake-embeddings", FAKE_TOKENS_PER_TEXT)
        return super().embed_query(text)
