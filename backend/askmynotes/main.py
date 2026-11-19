"""The one start command: `uv run askmynotes`.

Builds the frontend, starts the server on this PC only, and opens the
browser once the server is answering. The notes are brought up to date in
the background as soon as the server starts.
"""

import argparse
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

import uvicorn
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from pydantic import ValidationError

from askmynotes.agent.agent import create_chat_model
from askmynotes.app import create_app
from askmynotes.fake_model import FakeChatModel, FakeEmbeddings, FakeSandbox
from askmynotes.interpreter.sandbox import Sandbox, create_sandbox
from askmynotes.notes.store import EmbeddingModelChanged, create_embeddings
from askmynotes.settings import (
    DATA_DIR,
    PROJECT_ROOT,
    AppSettings,
    load_app_settings,
    load_env_settings,
)

FRONTEND_DIR = PROJECT_ROOT / "frontend"
SETTINGS_FILE = PROJECT_ROOT / "settings.toml"


def build_frontend() -> None:
    """Build the frontend so the server always serves the current code."""
    # shell=True because on Windows `npm` is npm.cmd, which needs the shell. It
    # also works on macOS, where the shell finds `npm` on the PATH.
    subprocess.run("npm run build", cwd=FRONTEND_DIR, shell=True, check=True)


def open_browser_when_ready(url: str) -> None:
    """Wait until the server answers, then open the browser."""
    for _ in range(100):
        try:
            urllib.request.urlopen(f"{url}/api/health")
        except OSError:
            time.sleep(0.1)
        else:
            webbrowser.open(url)
            return


def load_settings(path: Path = SETTINGS_FILE) -> AppSettings:
    """Load settings.toml, exiting with a clear message if it's wrong."""
    try:
        return load_app_settings(path)
    except FileNotFoundError as error:
        sys.exit(f"Settings file not found: {error.filename}")
    except ValidationError as error:
        sys.exit(describe_problems(error))


def load_models(
    use_fake_models: bool,
) -> tuple[BaseChatModel, Embeddings, str, Sandbox]:
    """The chat model, the embedding model and its name, and Python's sandbox.

    The real ones come from `.env`; the fakes are for the end-to-end tests.
    """
    if use_fake_models:
        return FakeChatModel(), FakeEmbeddings(), "fake-embeddings", FakeSandbox()
    try:
        env = load_env_settings()
    except ValidationError as error:
        sys.exit(describe_problems(error))
    return (
        create_chat_model(env),
        create_embeddings(env),
        env.embedding_model,
        create_sandbox(env),
    )


def describe_problems(error: ValidationError) -> str:
    """List each missing or wrong setting by name."""
    problems = "\n".join(
        f"  - {'.'.join(str(part) for part in e['loc'])}: {e['msg']}"
        for e in error.errors()
    )
    return f"A setting is missing or wrong:\n{problems}"


def run() -> None:
    """Check settings, build the frontend, start the server, open the browser."""
    parser = argparse.ArgumentParser(description="Start AskMyNotes.")
    parser.add_argument("--no-browser", action="store_true", help="don't open a tab")
    parser.add_argument("--port", type=int, help="override the port in settings.toml")
    # The rest are for the end-to-end tests: no paid models, a throwaway data
    # folder and their own settings, so the tests never touch your real chats
    # or notes.
    parser.add_argument(
        "--fake-model", action="store_true", help="use fake models (nothing paid)"
    )
    parser.add_argument("--data-dir", type=Path, help="where to keep generated data")
    parser.add_argument("--settings", type=Path, help="use another settings file")
    args = parser.parse_args()

    settings = load_settings(args.settings or SETTINGS_FILE)
    chat_model, embeddings, embedding_model, sandbox = load_models(args.fake_model)
    port = args.port or settings.port
    try:
        app = create_app(
            settings,
            args.data_dir or DATA_DIR,
            chat_model,
            embeddings,
            embedding_model,
            FRONTEND_DIR / "dist",
            sandbox,
        )
    except EmbeddingModelChanged as error:
        sys.exit(str(error))
    build_frontend()
    url = f"http://127.0.0.1:{port}"
    if not args.no_browser:
        threading.Thread(
            target=open_browser_when_ready, args=(url,), daemon=True
        ).start()
    # 127.0.0.1 means only this PC can reach the app.
    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    run()
