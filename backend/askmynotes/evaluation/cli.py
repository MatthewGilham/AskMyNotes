"""`uv run askmynotes-eval --note "..."`: run the evaluation with the real models.

It costs money (about 50 agent answers, 50 judge calls and the behaviour
questions), so it only ever runs when you start it. It needs the notes
database to be filled first: start the app once so it indexes your notes.
"""

import argparse
import asyncio
import sys

from pydantic import ValidationError

from askmynotes.agent.agent import Agent, create_chat_model
from askmynotes.evaluation.cases import load_behaviour_cases, load_question_cases
from askmynotes.evaluation.report import format_report
from askmynotes.evaluation.results import last_run, save_run
from askmynotes.evaluation.runner import evaluate
from askmynotes.main import describe_problems, load_settings
from askmynotes.notes.search import NotesSearch
from askmynotes.notes.store import EmbeddingModelChanged, NotesStore, create_embeddings
from askmynotes.settings import DATA_DIR, PROJECT_ROOT, load_env_settings

RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"
DEFAULT_CONCURRENCY = 4


def main() -> None:
    """Run both test sets, save the results and print the report."""
    parser = argparse.ArgumentParser(description="Evaluate AskMyNotes.")
    parser.add_argument("--note", default="", help="a note saved with this run")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help="how many questions to run at once",
    )
    args = parser.parse_args()

    settings = load_settings()
    try:
        env = load_env_settings()
    except ValidationError as error:
        sys.exit(describe_problems(error))
    try:
        store = NotesStore(
            DATA_DIR / "chroma", create_embeddings(env), env.embedding_model
        )
    except EmbeddingModelChanged as error:
        sys.exit(str(error))
    if store.count() == 0:
        sys.exit(
            "The notes database is empty. Start the app once with "
            "`uv run askmynotes` so it indexes your notes, then run this again."
        )

    chat_model = create_chat_model(env)
    agent = Agent(
        chat_model,
        NotesSearch(store, settings.modules, settings.notes_search_results),
        web_search=settings.web_search,
    )
    previous = last_run(RESULTS_DIR)
    results = asyncio.run(
        evaluate(
            settings=settings,
            store=store,
            agent=agent,
            judge_model=chat_model,
            chat_model_name=env.chat_model,
            embedding_model_name=env.embedding_model,
            questions=load_question_cases(),
            behaviour_cases=load_behaviour_cases(),
            note=args.note,
            concurrency=args.concurrency,
        )
    )
    detail_file = save_run(results, RESULTS_DIR)
    print(format_report(results, previous))
    print(f"\nSaved {detail_file.relative_to(PROJECT_ROOT)} and history.csv")


if __name__ == "__main__":
    main()
