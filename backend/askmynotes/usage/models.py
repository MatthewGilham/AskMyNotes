"""The shapes of the usage API's responses (camelCase for the browser)."""

from askmynotes.chats.models import ApiModel


class ContextUsage(ApiModel):
    """How full a chat's long-chat budget is."""

    tokens: int
    budget_tokens: int
    # Has an older part of the chat been folded into a summary?
    summarised: bool
    # Past the budget: the next message will summarise the older messages.
    over_budget: bool


class ChatCostBreakdown(ApiModel):
    """A chat's cost, in dollars, by what it was spent on."""

    replies: float
    titles: float
    summaries: float
    searches: float
    web_searches: float
    python: float


class ChatUsage(ApiModel):
    """`GET /api/chats/{id}/usage`: one chat's cost and context."""

    cost: float
    breakdown: ChatCostBreakdown
    # Some of the cost is an estimate (a stopped reply, say).
    includes_estimate: bool
    # The chat is older than the cost tracking, so its earlier costs are missing.
    earlier_costs_unrecorded: bool
    tracking_started_at: str
    context: ContextUsage


class TotalUsage(ApiModel):
    """`GET /api/usage`: everything the app has spent, in dollars."""

    cost: float
    chats: float
    deleted_chats: float
    notes_updates: float
    includes_estimate: bool
    tracking_started_at: str
