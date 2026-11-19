"""Scoring that needs no model: retrieval measures and behaviour checks.

Retrieval is judged by keywords. A search result is relevant if its text
contains any of the question's keywords (ignoring case), and it is worth
more the more of the keywords it contains.
"""

import math

from askmynotes.evaluation.agent_run import AgentRun
from askmynotes.evaluation.cases import Expectation

NOT_COVERED_PHRASE = "your notes don't cover this"


def keywords_in(text: str, keywords: list[str]) -> int:
    """How many different keywords the text contains."""
    lowered = text.lower()
    return sum(keyword.lower() in lowered for keyword in keywords)


def mean_reciprocal_rank(gains: list[int]) -> float:
    """1 / the rank of the first relevant result (0 if none is relevant).

    `gains` has one number per result, best-ranked first: how many keywords
    that result contains.
    """
    for rank, gain in enumerate(gains, start=1):
        if gain > 0:
            return 1 / rank
    return 0.0


def ndcg(gains: list[int]) -> float:
    """How well the results are ordered, from 0 to 1 (1 = best first).

    Compares the order found with the best possible order of the same
    results, with each result's worth being its keyword count, discounted
    the further down the list it is.
    """

    def discounted_total(ordered: list[int]) -> float:
        return sum(
            gain / math.log2(rank + 1) for rank, gain in enumerate(ordered, start=1)
        )

    best = discounted_total(sorted(gains, reverse=True))
    return discounted_total(gains) / best if best > 0 else 0.0


def keyword_coverage(texts: list[str], keywords: list[str]) -> float:
    """The share of keywords found somewhere in the results."""
    everything = "\n".join(texts).lower()
    return sum(keyword.lower() in everything for keyword in keywords) / len(keywords)


def says_not_covered(answer: str) -> bool:
    """Does the answer say "Your notes don't cover this"?"""
    return NOT_COVERED_PHRASE in answer.lower().replace("’", "'")


def check_behaviour(expect: Expectation, run: AgentRun) -> list[str]:
    """What went wrong, if anything: one message per failed expectation."""
    problems = []
    if expect.searches is not None and run.searched != expect.searches:
        problems.append(f"searched={run.searched}, expected {expect.searches}")
    if expect.web_searches is not None and run.web_searched != expect.web_searches:
        problems.append(
            f"searched the web={run.web_searched}, expected {expect.web_searches}"
        )
    if expect.sources_listed is not None:
        listed = run.sources is not None
        if listed != expect.sources_listed:
            problems.append(
                f"sources listed={listed}, expected {expect.sources_listed}"
            )
    if expect.source_modules is not None:
        used = sorted({s.module for s in run.sources or []})
        if not used or not set(used) <= set(expect.source_modules):
            problems.append(
                f"source modules {used}, expected only {expect.source_modules}"
            )
    if expect.beyond_label is not None:
        has_block = ":::beyond" in run.answer
        if has_block != expect.beyond_label:
            problems.append(
                f"'Beyond your notes' block={has_block}, expected {expect.beyond_label}"
            )
    if expect.not_covered is not None:
        says = says_not_covered(run.answer)
        if says != expect.not_covered:
            problems.append(f"says not covered={says}, expected {expect.not_covered}")
    return problems
