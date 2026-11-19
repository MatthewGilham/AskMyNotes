"""The shapes of chats and messages in the API and in storage.

Python uses snake_case and the frontend uses camelCase, so every model here
converts names automatically when it is sent or received as JSON.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    """Base for every model that crosses the API: camelCase in JSON."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Source(ApiModel):
    """One slide or page that a notes answer used."""

    file_name: str
    module: str
    location: Literal["slide", "page"]
    number: int


class WebSource(ApiModel):
    """One web page that a web answer searched for: one it cited, or one the
    search read and the answer didn't cite."""

    title: str
    # The page's site, such as "bankofengland.co.uk".
    site: str
    url: str
    # False for a page the search read and the answer didn't cite. Answers saved
    # before the "Found online" panel only recorded cited pages.
    cited: bool = True


class ToolRun(ApiModel):
    """One calculation, or one run of Python, that the agent made while writing
    an answer, for the "Working" panel."""

    tool: Literal["calculate", "solve_equation", "python"]
    # The expression or equation, or the Python code.
    input: str
    # The result as text, or what was wrong with the calculation. For Python,
    # what the code printed.
    result: str
    ok: bool
    # Python's output was cut to its first lines (see `interpreter/runs.py`).
    truncated: bool = False
    # The same as LaTeX, for drawing as maths; None if it couldn't be written.
    input_latex: str | None = None
    result_latex: str | None = None


class MessageFile(ApiModel):
    """A file that Python made while writing an answer."""

    id: int
    name: str
    size: int
    media_type: str
    # Pictures that are safe to show under the answer; everything else is
    # offered as a download.
    is_image: bool
    # Where the browser gets it from (always downloaded, never opened as a page).
    url: str


class QuotedContext(ApiModel):
    """A user-provided excerpt snapshot and its original assistant answer."""

    source_message_id: int
    excerpt: str

    @model_validator(mode="after")
    def valid_excerpt(self) -> "QuotedContext":
        """Refuse empty or oversized passages without silently truncating them."""
        if not self.excerpt.strip():
            raise ValueError("Select a passage with text.")
        if len(self.excerpt) > 8000:
            raise ValueError(
                "Please select a shorter passage (maximum 8,000 characters)."
            )
        return self


class MessageDocument(ApiModel):
    """A document attached to a message. Its text is for the model only, so it
    is left out of everything sent to the browser."""

    name: str
    kind: Literal["page", "slide", "sheet", "document"]
    # How many pages, slides or sheets it has; Word files have no fixed count.
    count: int | None
    text: str = Field(exclude=True)


class Message(ApiModel):
    """One saved message."""

    id: int
    role: Literal["user", "assistant"]
    content: str
    status: Literal["complete", "stopped", "error"]
    error: str | None
    sources: list[Source] | None
    # Addresses of the images attached to this message.
    images: list[str]
    created_at: datetime
    quoted_context: QuotedContext | None = None
    documents: list[MessageDocument] = []
    # The web pages a web answer cited or searched; None if it searched no web
    # pages.
    web_sources: list[WebSource] | None = None
    # What the web searches asked for. None if it made none, and for answers
    # saved before the panel recorded them.
    web_searches: list[str] | None = None
    # The calculations the answer was worked out with; None if it made none.
    tool_runs: list[ToolRun] | None = None
    # The files Python made for this answer.
    files: list[MessageFile] = []
    # On a question: the student switched Python on for it.
    python_requested: bool = False


class ChatSummary(ApiModel):
    """A chat as listed in the sidebar."""

    id: str
    title: str
    pinned: bool
    created_at: datetime
    last_used_at: datetime


class ChatDetail(ChatSummary):
    """A whole chat: its summary and every message."""

    messages: list[Message]


class ChatUpdate(ApiModel):
    """A change to a chat. Only the fields that are sent are changed."""

    title: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None
    ) = None
    pinned: bool | None = None


class SearchResult(ApiModel):
    """A chat that matched a search, with the text that matched."""

    chat_id: str
    title: str
    snippet: str
    message_id: int | None = None


class ImageUpload(ApiModel):
    """An image attached to a message, sent as base64 text inside the JSON."""

    name: str
    media_type: Literal["image/png", "image/jpeg", "image/webp", "image/gif"]
    data: str


class DocumentUpload(ApiModel):
    """A Word, Excel, PowerPoint or PDF file attached to a message, sent as
    base64 text inside the JSON, like an image."""

    name: str
    data: str


class SendRequest(ApiModel):
    """A new message from the student. With no `chat_id`, it starts a new chat."""

    chat_id: str | None = None
    text: Annotated[str, StringConstraints(strip_whitespace=True)] = ""
    images: list[ImageUpload] = []
    documents: list[DocumentUpload] = []
    quoted_context: QuotedContext | None = None
    # The "Python" button was on for this message.
    use_python: bool = False

    @model_validator(mode="after")
    def needs_text_an_image_or_a_document(self) -> "SendRequest":
        if not self.text and not self.images and not self.documents:
            raise ValueError("Write a message or attach an image or document.")
        return self


class EditRequest(ApiModel):
    """A correction guarded by the exact latest question the browser saw."""

    text: Annotated[str, StringConstraints(strip_whitespace=True)]
    expected_latest_message_id: int
    expected_original_text: str


class EditAcceptanceEvent(ApiModel):
    """The edit transaction committed and its replacement turn can stream."""

    type: Literal["accepted"] = "accepted"
    chat: ChatSummary
    user_message: Message
