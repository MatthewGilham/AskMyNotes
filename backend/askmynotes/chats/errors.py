"""Turns model failures into plain-English messages for the student."""

import openai


def friendly_error(error: Exception, doing: str = "writing the reply") -> str:
    """A short message saying what went wrong and what to do about it.

    `doing` names the task that failed, for the catch-all message.

    The technical details are logged by the caller, never shown, and never
    include the API key.
    """
    if isinstance(error, openai.APIConnectionError):
        return "Couldn't reach OpenAI. Check your internet connection, then try again."
    if isinstance(error, openai.AuthenticationError):
        return (
            "OpenAI rejected the API key in .env. Check that OPENAI_API_KEY is correct."
        )
    if isinstance(error, openai.RateLimitError):
        return (
            "OpenAI says there have been too many requests, or the account is out of "
            "credit. Wait a moment, then try again."
        )
    if isinstance(error, openai.APIStatusError) and error.status_code >= 500:
        return "OpenAI is having problems right now. Try again in a minute."
    return f"Something went wrong while {doing} ({type(error).__name__}). Try again."
