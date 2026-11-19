"""Collecting what the model calls of one reply, or one notes update, used.

OpenAI reports how many tokens each call used. A `UsageLog` gathers those
reports while a reply is written, and the conversation saves them in the ledger
(`usage/ledger.py`) when the reply ends. A call that never reported (the reply
was stopped part-way, or the connection dropped) is estimated from the text
that went in and out, and marked as estimated.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.messages.ai import UsageMetadata

# A rough size estimate: about four characters per token is close enough for a
# budget with headroom. An exact token counter would download its encoding
# files into the user folder.
CHARS_PER_TOKEN = 4
# What an attached image is assumed to cost, since it has no text to measure.
IMAGE_TOKENS = 1000

UsageKind = Literal[
    "reply", "title", "summary", "search", "notes_update", "web_search", "python"
]
EMBEDDING_KINDS: tuple[UsageKind, ...] = ("search", "notes_update")


@dataclass(frozen=True)
class UsageEntry:
    """The tokens one model call used."""

    kind: UsageKind
    model: str
    # The cached tokens are part of the input tokens, as OpenAI reports them.
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    estimated: bool = False


def tokens_for_characters(characters: int) -> int:
    """A rough token count for some text, rounded up."""
    return (characters + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def model_name_of(chat_model: BaseChatModel) -> str:
    """The model's name, for the ledger (the fake model has none)."""
    return getattr(chat_model, "model_name", None) or type(chat_model).__name__


def message_characters(message: BaseMessage) -> int:
    """About how many characters of text a message sends, images included."""
    if isinstance(message.content, str):
        return len(message.content)
    total = 0
    for part in message.content:
        if isinstance(part, str):
            total += len(part)
        elif part.get("type") == "text":
            total += len(part["text"])
        elif part.get("type") == "image_url":
            total += IMAGE_TOKENS * CHARS_PER_TOKEN
    return total


def entry_from_metadata(
    kind: UsageKind, model: str, usage: UsageMetadata
) -> UsageEntry:
    """What OpenAI reported for one call."""
    details = usage.get("input_token_details") or {}
    return UsageEntry(
        kind,
        model,
        input_tokens=usage["input_tokens"],
        cached_tokens=details.get("cache_read", 0),
        output_tokens=usage["output_tokens"],
    )


def entry_from_reply(
    kind: UsageKind, model: str, reply: AIMessage, sent_characters: int
) -> UsageEntry:
    """The usage of a one-off call such as a title: what OpenAI reported, or an
    estimate if it reported nothing."""
    if reply.usage_metadata is not None:
        return entry_from_metadata(kind, model, reply.usage_metadata)
    return UsageEntry(
        kind,
        model,
        input_tokens=tokens_for_characters(sent_characters),
        cached_tokens=0,
        output_tokens=tokens_for_characters(len(reply.text)),
        estimated=True,
    )


class UsageLog:
    """The usage of one reply (or one notes update) as it happens.

    A reply is usually several model calls: the agent calls the model, runs a
    search, then calls it again with the results. The log follows the call that
    is in progress, so that if the reply ends before OpenAI's report arrives,
    that call can be estimated.
    """

    def __init__(
        self, chat_model: str = "unknown", embedding_kind: UsageKind = "search"
    ) -> None:
        self.entries: list[UsageEntry] = []
        self._chat_model = chat_model
        self._embedding_kind = embedding_kind
        self._call_open = False
        self._sent_characters = 0
        self._output_characters = 0

    def begin_call(self, sent_characters: int) -> None:
        """The agent is about to call the model, sending this much text."""
        self._call_open = True
        self._sent_characters = sent_characters
        self._output_characters = 0

    def note_output(self, characters: int) -> None:
        """The model in progress has written this many more characters."""
        self._output_characters += characters

    def report_call(self, usage: UsageMetadata) -> None:
        """OpenAI's own report for the call in progress, which then ends."""
        self.entries.append(entry_from_metadata("reply", self._chat_model, usage))
        self._call_open = False
        self._sent_characters += self._output_characters
        self._output_characters = 0

    def add_web_search(self) -> None:
        """OpenAI ran one web search for the reply. It costs a flat fee, so the
        entry carries no tokens; the pages it read are in the reply's own."""
        self.entries.append(UsageEntry("web_search", self._chat_model, 0, 0, 0))

    def add_python_session(self) -> None:
        """A Python sandbox was created for the reply. It costs a flat fee, so the
        entry carries no tokens; what the model writes and reads while it runs is
        in the reply's own."""
        self.entries.append(UsageEntry("python", self._chat_model, 0, 0, 0))

    def continue_after_search(self, result_characters: int) -> None:
        """Search results came back, so the agent calls the model again with
        everything so far plus the results."""
        # If the call that asked for the search never got its report, it still
        # happened, so it is estimated now.
        self._estimate_open_call()
        self.begin_call(self._sent_characters + result_characters)

    def add_embedding(self, model: str, tokens: int) -> None:
        """A batch of text was embedded (a notes search or update)."""
        self.entries.append(UsageEntry(self._embedding_kind, model, tokens, 0, 0))

    def finish(self, failed: bool) -> None:
        """The reply has ended. Estimate the call in progress, if it never got
        its report. A failed call that wrote nothing is not counted, because it
        may well never have reached OpenAI."""
        if failed and self._output_characters == 0:
            return
        self._estimate_open_call()

    def _estimate_open_call(self) -> None:
        if not self._call_open:
            return
        self.entries.append(
            UsageEntry(
                "reply",
                self._chat_model,
                input_tokens=tokens_for_characters(self._sent_characters),
                cached_tokens=0,
                output_tokens=tokens_for_characters(self._output_characters),
                estimated=True,
            )
        )
        self._sent_characters += self._output_characters
        self._output_characters = 0
        self._call_open = False


# Embeddings are made deep inside the notes store, which doesn't know whose
# reply or update it is working for. The caller sets the log here instead of
# passing it through every layer. A ContextVar is per thread and per task, so
# two searches at once can't mix up their logs.
_current_log: ContextVar[UsageLog | None] = ContextVar(
    "current_usage_log", default=None
)


@contextmanager
def logging_usage(log: UsageLog | None) -> Iterator[None]:
    """Within this block, embeddings made in this thread are added to `log`."""
    token = _current_log.set(log)
    try:
        yield
    finally:
        _current_log.reset(token)


def report_embedding(model: str, tokens: int) -> None:
    """Called by the embeddings classes after each request to OpenAI."""
    log = _current_log.get()
    if log is not None:
        log.add_embedding(model, tokens)
