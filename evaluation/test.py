import json
from pathlib import Path
from pydantic import BaseModel, Field




class TestQuestion(BaseModel):
    """A test question with expected keywords and reference answer."""

    question: str = Field(description="The question to ask the RAG system")
    keywords: list[str] = Field(description="Keywords that must appear in retrieved context")
    reference_answer: str = Field(description="The reference answer for this question")
    category: str = Field(description="Question category (e.g., direct_fact, spanning, temporal)")
    module: str = Field(default="Unknown", description="Which uni module the question comes from")


def load_tests(filename: str = "tests_small.jsonl") -> list[TestQuestion]:
    """Load test questions from JSONL file."""
    tests = []
    with open(Path(__file__).parent / filename, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line.strip())
            tests.append(TestQuestion(**data))
    return tests
