"""Loads and checks the app's settings.

Secrets and model names come from `.env`; everything else (your name, the
notes folders, ports, paths) comes from `settings.toml`. Both are checked
with Pydantic at start-up, so a missing or misspelled setting stops the app
with a message naming it, instead of failing later in some unrelated place.
"""

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Everything the app generates, including lecture content; never committed.
DATA_DIR = PROJECT_ROOT / "data"


class EnvSettings(BaseSettings):
    """Secrets and model names, read from `.env`."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", extra="ignore", env_ignore_empty=True
    )

    openai_api_key: str
    chat_model: str
    embedding_model: str


class Module(BaseModel):
    """One university module whose lecture slides are searched."""

    model_config = ConfigDict(extra="forbid")

    name: str
    short_name: str
    folder: Path


class Prices(BaseModel):
    """What the models cost, in US dollars per million tokens.

    Copied from OpenAI's pricing page. Each recorded model call stores its cost
    when it happens, so changing a price only affects calls made afterwards.
    """

    model_config = ConfigDict(extra="forbid")

    chat_input: float
    chat_cached_input: float
    chat_output: float
    embedding_input: float
    # Dollars per web search, not per million tokens: OpenAI charges each search
    # a flat fee. The pages a search reads are counted in the reply's own tokens.
    web_search_call: float
    # Dollars per Python sandbox (OpenAI charges $0.03 per 1 GB container, for
    # up to 20 minutes). The tokens used while it runs are counted in the reply.
    python_session: float


class WebSearch(BaseModel):
    """Where web searches say the student is, so "near me" and prices make
    sense. No city is sent."""

    model_config = ConfigDict(extra="forbid")

    country: str
    timezone: str


class AppSettings(BaseModel):
    """Everything in `settings.toml`."""

    model_config = ConfigDict(extra="forbid")

    user_name: str
    port: int
    libreoffice_path: Path
    max_images_per_message: int
    max_image_size_mb: int
    max_documents_per_message: int
    max_document_size_mb: int
    max_document_tokens: int
    max_generated_files_per_reply: int
    max_generated_file_mb: int
    context_budget_tokens: int
    max_chunk_characters: int
    notes_search_results: int
    example_prompts: list[str]
    prices: Prices
    web_search: WebSearch
    modules: list[Module]

    @model_validator(mode="after")
    def documents_fit_in_the_budget(self) -> "AppSettings":
        """A long chat keeps its newest messages within half the budget, so one
        message's documents must fit in that half."""
        if self.max_document_tokens * 2 > self.context_budget_tokens:
            raise ValueError(
                "max_document_tokens must be at most half of context_budget_tokens"
            )
        return self


def load_env_settings() -> EnvSettings:
    """Read `.env`. Raises a Pydantic error naming any missing variable."""
    return EnvSettings()  # type: ignore[call-arg]  # values come from .env


def load_app_settings(path: Path = PROJECT_ROOT / "settings.toml") -> AppSettings:
    """Read `settings.toml`. Raises a Pydantic error naming any bad setting."""
    with path.open("rb") as file:
        return AppSettings.model_validate(tomllib.load(file))
