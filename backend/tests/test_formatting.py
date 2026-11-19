"""Tests that the agent is told how to use code blocks and callout boxes."""

from pathlib import Path

from fastapi.testclient import TestClient
from helpers import build_app, send, wait_until_updated

from askmynotes.fake_model import FakeChatModel, text_of


def test_the_instructions_explain_code_blocks_and_the_four_callouts(
    tmp_path: Path,
) -> None:
    model = FakeChatModel(responder=lambda m: "Hello")
    with TestClient(build_app(tmp_path / "data", model)) as client:
        wait_until_updated(client)
        send(client, "Hi")

    answer_call = [m for m in model.received if "short title" not in text_of(m[0])][0]
    text = " ".join(text_of(answer_call[0]).split())
    for marker in (":::formula", ":::tip", ":::mistake", ":::example"):
        assert marker in text
    assert "```python or ```sql" in text
    # A callout never takes the place of the red and blue labels.
    assert "A callout never replaces a label" in text
    assert "nothing else nests" in text
    assert "sparingly" in text


def test_the_instructions_explain_diagrams_and_charts(tmp_path: Path) -> None:
    model = FakeChatModel(responder=lambda m: "Hello")
    with TestClient(build_app(tmp_path / "data", model)) as client:
        wait_until_updated(client)
        send(client, "Hi")

    answer_call = [m for m in model.received if "short title" not in text_of(m[0])][0]
    text = " ".join(text_of(answer_call[0]).split())
    assert "fenced block with the language `mermaid`" in text
    assert "fenced block with the language `chart`" in text
    assert "`type` is `line`, `bar` or `pie`" in text
    assert "at most 6 series and 500 rows" in text
    assert "never from a guess" in text
    # A picture doesn't change where something came from.
    assert "inside the `:::web` block" in text
