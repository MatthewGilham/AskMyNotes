"""The evaluation's test questions, read from `evaluation/*.jsonl`.

Each line of a file is one JSON object. Every line is checked with Pydantic
when it is loaded, so a misspelled field or category stops the run with a
message instead of quietly skewing the scores.
"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from askmynotes.settings import PROJECT_ROOT

EVALUATION_DIR = PROJECT_ROOT / "evaluation"
SMALL_TESTS_FILE = EVALUATION_DIR / "tests_small.jsonl"
BEHAVIOUR_TESTS_FILE = EVALUATION_DIR / "tests_behaviour.jsonl"

Category = Literal[
    "direct_fact", "definition", "calculation", "spanning", "paraphrased", "not_covered"
]


class QuestionCase(BaseModel):
    """A question about the notes, with what a good answer contains."""

    model_config = ConfigDict(extra="forbid")

    question: str
    # Words a relevant slide contains. Empty for `not_covered` questions.
    keywords: list[str]
    reference_answer: str
    category: Category
    # The module's full name, as in settings.toml.
    module: str


class Expectation(BaseModel):
    """What the agent should have done. A field left out isn't checked."""

    model_config = ConfigDict(extra="forbid")

    # Did it search the notes?
    searches: bool | None = None
    # Did it search the web?
    web_searches: bool | None = None
    # Does the answer list any sources?
    sources_listed: bool | None = None
    # Every source is from these modules (short names), and there is at least one.
    source_modules: list[str] | None = None
    # Does the answer contain a "Beyond your notes" block?
    beyond_label: bool | None = None
    # Does the answer say "Your notes don't cover this"?
    not_covered: bool | None = None


class BehaviourCase(BaseModel):
    """A question that checks one of the rules in the spec's section 4."""

    model_config = ConfigDict(extra="forbid")

    question: str
    expect: Expectation


def load_question_cases(path: Path = SMALL_TESTS_FILE) -> list[QuestionCase]:
    """Read the notes questions."""
    return [
        QuestionCase.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_behaviour_cases(path: Path = BEHAVIOUR_TESTS_FILE) -> list[BehaviourCase]:
    """Read the behaviour questions."""
    return [
        BehaviourCase.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
