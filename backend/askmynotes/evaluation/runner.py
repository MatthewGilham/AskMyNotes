"""Running the evaluation: every question goes through the real agent.

For each notes question it measures retrieval (straight to the notes search,
over all modules), gets the agent's answer in a fresh chat, has the judge
score it, and checks "Your notes don't cover this" for `not_covered`
questions. Behaviour questions are checked exactly from what the agent did.

A question that fails (no internet, say) is recorded with its error and left
out of the averages; the report says how many there were.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable
from datetime import datetime

from langchain_core.language_models import BaseChatModel

from askmynotes.agent.agent import Agent
from askmynotes.chats.errors import friendly_error
from askmynotes.evaluation.agent_run import ask_agent
from askmynotes.evaluation.cases import BehaviourCase, QuestionCase
from askmynotes.evaluation.judge import judge_answer
from askmynotes.evaluation.metrics import (
    check_behaviour,
    keyword_coverage,
    keywords_in,
    mean_reciprocal_rank,
    ndcg,
    says_not_covered,
)
from askmynotes.evaluation.results import (
    BehaviourResult,
    QuestionResult,
    RetrievalScores,
    RetrievedSlide,
    RunResults,
    summarise,
)
from askmynotes.notes.store import NotesStore
from askmynotes.settings import AppSettings

logger = logging.getLogger(__name__)


async def retrieval_scores(
    store: NotesStore, case: QuestionCase, results_per_search: int
) -> RetrievalScores:
    """Search the notes for the question, and score what comes back."""
    found = await asyncio.to_thread(store.search, case.question, [], results_per_search)
    texts = [result.text for result in found]
    gains = [keywords_in(text, case.keywords) for text in texts]
    return RetrievalScores(
        mrr=mean_reciprocal_rank(gains),
        ndcg=ndcg(gains),
        keyword_coverage=keyword_coverage(texts, case.keywords),
        results=[
            RetrievedSlide(
                file_name=result.file_name,
                module=result.module,
                location=result.location,
                number=result.number,
                keywords_matched=gain,
            )
            for result, gain in zip(found, gains, strict=True)
        ],
    )


async def evaluate_question(
    case: QuestionCase,
    module_short_name: str,
    store: NotesStore,
    agent: Agent,
    judge_model: BaseChatModel,
    results_per_search: int,
) -> QuestionResult:
    """Retrieval, answer, judge score and not-covered check for one question."""
    result = QuestionResult(
        question=case.question, category=case.category, module=module_short_name
    )
    try:
        if case.keywords:
            result.retrieval = await retrieval_scores(store, case, results_per_search)
        run = await ask_agent(agent, case.question)
        result.searched = run.searched
        result.searches = run.searches
        result.sources_line_found = run.sources_line_found
        result.answer = run.answer
        result.sources = run.sources
        result.says_not_covered = says_not_covered(run.answer)
        result.scores = await judge_answer(
            judge_model, case.question, case.reference_answer, run.answer
        )
    except Exception as error:  # recorded and reported, so one failure isn't a lost run
        logger.exception("Question failed: %s", case.question)
        result.error = friendly_error(error, doing="evaluating this question")
        # Whatever was measured before the failure is left out of the averages.
        result.retrieval = None
        result.scores = None
        result.says_not_covered = None
    return result


async def evaluate_behaviour(case: BehaviourCase, agent: Agent) -> BehaviourResult:
    """Ask a behaviour question and check what the agent did."""
    result = BehaviourResult(question=case.question, expect=case.expect)
    try:
        run = await ask_agent(agent, case.question)
    except Exception as error:  # recorded and reported, as above
        logger.exception("Question failed: %s", case.question)
        result.error = friendly_error(error, doing="evaluating this question")
        return result
    result.searched = run.searched
    result.web_searched = run.web_searched
    result.searches = run.searches
    result.sources_line_found = run.sources_line_found
    result.answer = run.answer
    result.sources = run.sources
    result.problems = check_behaviour(case.expect, run)
    result.passed = not result.problems
    return result


async def evaluate(
    *,
    settings: AppSettings,
    store: NotesStore,
    agent: Agent,
    judge_model: BaseChatModel,
    chat_model_name: str,
    embedding_model_name: str,
    questions: list[QuestionCase],
    behaviour_cases: list[BehaviourCase],
    note: str,
    concurrency: int,
) -> RunResults:
    """Run every question, a few at a time, and gather the results."""
    short_names = {module.name: module.short_name for module in settings.modules}
    unknown = sorted({q.module for q in questions} - set(short_names))
    if unknown:
        raise ValueError(
            f"The test set names modules that aren't in settings.toml: {unknown}"
        )

    started_at = datetime.now()
    started = time.perf_counter()
    # A few at a time keeps a run quick without flooding the API.
    slots = asyncio.Semaphore(concurrency)

    async def one_of_a_few[T](work: Awaitable[T]) -> T:
        async with slots:
            return await work

    question_results, behaviour_results = await asyncio.gather(
        asyncio.gather(
            *(
                one_of_a_few(
                    evaluate_question(
                        case,
                        short_names[case.module],
                        store,
                        agent,
                        judge_model,
                        settings.notes_search_results,
                    )
                )
                for case in questions
            )
        ),
        asyncio.gather(
            *(one_of_a_few(evaluate_behaviour(case, agent)) for case in behaviour_cases)
        ),
    )
    return RunResults(
        timestamp=started_at,
        note=note,
        chat_model=chat_model_name,
        embedding_model=embedding_model_name,
        seconds=time.perf_counter() - started,
        headline=summarise(question_results, behaviour_results),
        questions=question_results,
        behaviour=behaviour_results,
    )
