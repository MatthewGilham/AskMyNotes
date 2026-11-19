"""The sandbox Python runs in, which OpenAI calls a container.

When the student switches Python on for a message, the app creates one
container for that reply, copies their Excel files into it, and offers it to the
model as the `code_interpreter` tool. Nothing runs on this computer. When the
reply ends, the files Python made are downloaded and the container is deleted,
so each one is paid for (see `usage/ledger.py`) only when it is used.

`Sandbox` is the part of this the app talks to, so that the tests and the
end-to-end tests can use a fake one (`fake_model.FakeSandbox`) that costs
nothing.
"""

import logging
import time
from typing import Protocol

import openai
from openai import OpenAI

from askmynotes.settings import EnvSettings

logger = logging.getLogger(__name__)

CONTAINER_NAME = "askmynotes"
# If the app is closed before it can delete a container, OpenAI removes it after
# this many minutes without use.
EXPIRES_AFTER_MINUTES = 20
DELETE_ATTEMPTS = 3


class Sandbox(Protocol):
    """Makes, reads and removes the container for one reply."""

    def create(self, files: list[tuple[str, bytes]]) -> str:
        """Make a container holding these (name, contents) files; return its id."""

    def download(self, container_id: str, file_id: str) -> bytes:
        """The contents of a file in the container."""

    def delete(self, container_id: str) -> None:
        """Remove the container. Never raises: a container that can't be removed
        is logged, and expires by itself."""


class OpenAISandbox:
    """The real thing, through the `openai` package."""

    def __init__(self, client: OpenAI) -> None:
        self._client = client

    def create(self, files: list[tuple[str, bytes]]) -> str:
        # A 1 GB container, made explicitly rather than with "auto", so the app
        # knows exactly when one is created and charged for.
        container = self._client.containers.create(
            name=CONTAINER_NAME,
            memory_limit="1g",
            expires_after={
                "anchor": "last_active_at",
                "minutes": EXPIRES_AFTER_MINUTES,
            },
        )
        try:
            for name, data in files:
                self._client.containers.files.create(container.id, file=(name, data))
        except BaseException:
            self.delete(container.id)
            raise
        return container.id

    def download(self, container_id: str, file_id: str) -> bytes:
        response = self._client.containers.files.content.retrieve(
            file_id, container_id=container_id
        )
        return response.read()

    def delete(self, container_id: str) -> None:
        # OpenAI has been seen to go on listing a container as running after a
        # first delete, so each delete is checked, and repeated if needed.
        for attempt in range(DELETE_ATTEMPTS):
            try:
                self._client.containers.delete(container_id)
                self._client.containers.retrieve(container_id)
            except openai.NotFoundError:
                return
            except Exception:
                logger.exception("Couldn't delete the Python sandbox %s", container_id)
            time.sleep(0.5 * (attempt + 1))
        logger.warning(
            "The Python sandbox %s may still exist; it expires after %d minutes",
            container_id,
            EXPIRES_AFTER_MINUTES,
        )


def create_sandbox(env: EnvSettings) -> Sandbox:
    """The real sandbox, from the key in `.env`."""
    return OpenAISandbox(OpenAI(api_key=env.openai_api_key))
