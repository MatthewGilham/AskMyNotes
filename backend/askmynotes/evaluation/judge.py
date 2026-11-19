"""The judge: GPT-6 Luna scoring an answer against the reference answer."""

from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

JUDGE_PROMPT_FILE = Path(__file__).with_name("judge_prompt.md")


class JudgeScores(BaseModel):
    """The judge's scores for one answer, each from 1 to 5."""

    accuracy: int = Field(ge=1, le=5)
    completeness: int = Field(ge=1, le=5)
    relevance: int = Field(ge=1, le=5)
    explanation: str


async def judge_answer(
    chat_model: BaseChatModel, question: str, reference_answer: str, answer: str
) -> JudgeScores:
    """Score an answer. Raises if the judge's reply isn't valid scores."""
    request = (
        f"Question:\n{question}\n\nReference answer:\n{reference_answer}\n\n"
        f"Answer to mark:\n{answer}"
    )
    reply = await chat_model.ainvoke(
        [
            SystemMessage(content=JUDGE_PROMPT_FILE.read_text(encoding="utf-8")),
            HumanMessage(content=request),
        ]
    )
    text = str(reply.text)
    # Models sometimes wrap JSON in a code fence, so take from the first { to
    # the last }. What is inside is still checked by JudgeScores.
    return JudgeScores.model_validate_json(text[text.index("{") : text.rindex("}") + 1])
