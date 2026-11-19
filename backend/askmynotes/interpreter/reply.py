"""What one reply's Python did: the code it ran, what that printed, and the
files it said it made.

Like web search, Code Interpreter runs on OpenAI's side: the agent only offers it
to the model. The model's reply then carries a `code_interpreter_call` block for
each run (with the code and, because the request asks for them, its printed
output) and a `container_file_citation` annotation for each file it presented.
`PythonReply` collects both while the reply streams.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessageChunk

from askmynotes.calculator.tools import ToolRuns
from askmynotes.chats.models import ToolRun

# The "Working" panel shows this many lines of a run's output.
MAX_OUTPUT_LINES = 200
# The request must ask for the output, or the blocks arrive without it.
INCLUDE_OUTPUTS = "code_interpreter_call.outputs"

# The model likes to link the files it made, as `[name](sandbox:/mnt/data/x.csv)`.
# The app shows them under the answer instead, so the links are taken out.
SANDBOX_IMAGE = re.compile(r"!\[[^\]]*\]\(sandbox:[^)]*\)\n?")
SANDBOX_LINK = re.compile(r"\[([^\]]*)\]\(sandbox:[^)]*\)")


@dataclass(frozen=True)
class CitedFile:
    """A file in the container that the model's answer pointed to."""

    file_id: str
    name: str


def without_sandbox_links(text: str) -> str:
    """The text without links to files in the sandbox, which only work on
    OpenAI's side. A picture's link goes; a file's link keeps its label."""
    return SANDBOX_LINK.sub(r"\1", SANDBOX_IMAGE.sub("", text))


def output_of(block: dict[str, Any]) -> tuple[str, bool]:
    """What a run printed (cut to the first lines), and whether it was cut."""
    logs = "".join(
        str(output.get("logs", ""))
        for output in block.get("outputs") or []
        if output.get("type") == "logs"
    )
    lines = logs.splitlines()
    if len(lines) <= MAX_OUTPUT_LINES:
        return logs.rstrip("\n"), False
    return "\n".join(lines[:MAX_OUTPUT_LINES]), True


class PythonReply:
    """The sandbox one reply is using, and what has come out of it so far."""

    def __init__(self, container_id: str, file_names: list[str], runs: ToolRuns):
        self.container_id = container_id
        # The Excel files that were copied into the sandbox.
        self.file_names = file_names
        self.cited: list[CitedFile] = []
        self._runs = runs
        self._seen: set[str] = set()

    def tool(self) -> dict[str, Any]:
        """The tool as OpenAI expects it, pointing at this reply's container."""
        return {"type": "code_interpreter", "container": self.container_id}

    def read(self, chunk: AIMessageChunk) -> int:
        """Take what one streamed piece of the reply says about Python. Returns
        how many runs it starts that weren't seen before."""
        if isinstance(chunk.content, str):
            return 0
        new_runs = 0
        for block in chunk.content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "code_interpreter_call":
                run_id = block.get("id") or f"run-{len(self._seen)}"
                if run_id not in self._seen:
                    self._seen.add(run_id)
                    new_runs += 1
                    self._add_run(block)
            for annotation in block.get("annotations", []):
                if annotation.get("type") == "container_file_citation":
                    self._add_file(annotation)
        return new_runs

    def _add_run(self, block: dict[str, Any]) -> None:
        result, truncated = output_of(block)
        self._runs.runs.append(
            ToolRun(
                tool="python",
                input=str(block.get("code") or ""),
                result=result,
                ok=block.get("status") != "failed",
                truncated=truncated,
            )
        )

    def _add_file(self, annotation: dict[str, Any]) -> None:
        file_id = annotation["file_id"]
        if any(f.file_id == file_id for f in self.cited):
            return
        name = Path(str(annotation.get("filename") or file_id)).name
        self.cited.append(CitedFile(file_id, name))
