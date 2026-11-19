"""The events streamed to the browser while a reply is being written.

The stream is one JSON object per line, each with a `type`, so the browser
can read it line by line and know what each one means.
"""

from typing import Literal

from askmynotes.chats.models import ApiModel, ChatSummary, EditAcceptanceEvent, Message


class StartEvent(ApiModel):
    """A new message was saved; sent first, so the browser knows the chat's id."""

    type: Literal["start"] = "start"
    chat: ChatSummary
    user_message: Message


class TokenEvent(ApiModel):
    """The next piece of the reply's text."""

    type: Literal["token"] = "token"
    text: str


class SearchingEvent(ApiModel):
    """The agent is searching the notes or the web. The browser shows
    "Searching your notes…", "Searching the web…", "Calculating…" or "Running
    Python…" until the reply's text carries on."""

    type: Literal["searching"] = "searching"
    kind: Literal["notes", "web", "calculator", "python"] = "notes"


class TitleEvent(ApiModel):
    """The model has written a title for the chat (already saved)."""

    type: Literal["title"] = "title"
    title: str


class DoneEvent(ApiModel):
    """The reply is finished and saved."""

    type: Literal["done"] = "done"
    message: Message


class ErrorEvent(ApiModel):
    """The reply failed. The saved message carries a plain-English explanation."""

    type: Literal["error"] = "error"
    message: Message


StreamEvent = (
    StartEvent
    | EditAcceptanceEvent
    | TokenEvent
    | SearchingEvent
    | TitleEvent
    | DoneEvent
    | ErrorEvent
)
