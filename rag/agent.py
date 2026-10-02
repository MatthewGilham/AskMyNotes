from dotenv import load_dotenv
from agents import Agent, Runner, ModelSettings, function_tool
from rag.retrieval import MODEL, fetch_context
from openai.types.shared import Reasoning
from instruction import AGENT_INSTRUCTIONS
from openai.types.responses import ResponseTextDeltaEvent
load_dotenv(override=True)
@function_tool
def search_notes(query: str):
    """Search the student's university notes: lecture slides, seminar slides and seminar solutions
    for Business Law, Financial Reporting and Intermediate Management Accounting.

    Use this for ANY question about these modules or anything the student is studying: cases,
    legal tests, accounting standards, definitions, calculations, worked examples or exam topics.
    Always search before answering such questions, even if you think you know the answer, because
    the answer must come from the student's own materials. You can search more than once, for example
    once per topic when a question covers two topics.

    Do NOT use this for greetings, small talk or general questions unrelated to the modules/university.

    Args:
        query: A short, specific search phrase naming the topic, e.g. "Caparo test duty of care"
            or "sales-mix variance calculation". Rewrite vague follow-ups into a full phrase
            using the conversation so far.
    """
    chunks = fetch_context(query, history=[])
    context = "\n\n".join(
        f"Extract from {chunk.metadata['source']}:\n{chunk.page_content}" for chunk in chunks
    )
    print(f"🔍 Searching notes for: {query}")
    return context

agent = Agent(name="professor bastard", instructions=AGENT_INSTRUCTIONS, model=MODEL,tools=[search_notes], model_settings=ModelSettings(reasoning=Reasoning(effort="low")))

async def stream_agent_answer(messages):
    result = Runner.run_streamed(agent, messages)
    async for event in result.stream_events():
        if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
            yield event.data.delta


def run_agent(question):
    result = Runner.run_sync(agent, question)
    outputs = [item.output for item in result.new_items if item.type == "tool_call_output_item"]
    notes = "\n\n---\n\n".join(outputs)
    searches = sum(1 for item in result.new_items if item.type == "tool_call_item")
    return result.final_output, notes, searches





