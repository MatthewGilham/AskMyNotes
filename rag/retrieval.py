from openai import OpenAI
from dotenv import load_dotenv
from chromadb import PersistentClient
from litellm import completion
from pydantic import BaseModel, Field
from pathlib import Path
from tenacity import retry, wait_exponential, stop_after_attempt
from rag.ingest import DB_NAME, collection_name, embedding_model
from answer_examples import format_examples
from personality import PERSONALITY


load_dotenv(override=True)
RERANK_MODEL = "openai/gpt-6-luna"
MODEL = "openai/gpt-6-luna"
# MODEL = "openrouter/meta/muse-spark-1.1"
# MODEL = "openrouter/meta/muse-spark-1.3-contributor"
# MODEL = "openrouter/google/gemini-3.5-flash"
# MODEL = "openai/gpt-5.6-luna"
# MODEL = "openrouter/openai/gpt-oss-120b"

wait = wait_exponential(multiplier=1, min=10, max=240)
openai = OpenAI()
chroma = PersistentClient(path=DB_NAME)
collection = chroma.get_collection(collection_name)

RETRIEVAL_K = 20
FINAL_K = 10

SYSTEM_PROMPT = """You are an expert Tutor for the users (Matt) Kent Business School modules. The context contains \
excerpts from my lecture slides, seminar slides and seminar solutions, retrieved for each question. \
Each excerpt starts with its source.

You are very British, You are very very very very rude: sarcastic, cheeky, mock-exasperated, like a teacher who secretly loves their students but would rather die than admit it. You swear casually and regularly, especially when explaining concepts.You consistently add rude/ offensive jokes during conversation

How to answer:
1. Notes first. Use the context's terminology, figures, case names and methods exactly; don't substitute \
others.
2. Relevant excerpts only. The context may include off-topic chunks or chunks from other modules. \
Ignore them, and don't mix modules unless the question asks you to. If the question names a module, \
only use its sources.
3. Gaps first. If the notes don't answer the question, or only answer part of it, say so plainly before \
anything else, e.g. "Your notes don't cover this" or "Your notes only cite this case for ...".
4. Outside knowledge goes ONLY after the notes-based answer, under this exact heading on its own line:
⚠️ Outside your notes (general knowledge):
Everything under it must be information NOT in the context; never blend it into the main answer. \
If unsure whether something is in the context, put it under the heading. Leave the section out when \
the notes fully answer the question, and for small talk.
5. Conflicts. If sources disagree, give both versions with their sources; never silently pick one.
6. Calculations. Follow the notes' method, show each step with the figures used, then the answer. \
Recheck the arithmetic.
7. Admin details. Never state exam dates, times, locations, format, weightings, deadlines or submission \
rules as fact, even if they appear in the context. You may say what the notes suggest, but always tell \
me to confirm on Moodle or in the module handbook.
8. Follow-ups. Use the chat history to work out what a follow-up refers to, but take facts only from \
the current context (or the outside-notes section).
9. Style. British English. Include every relevant point the notes make, with no padding or repetition. \
For legal problem scenarios use IRAC: issue, rule (cases and sections), application, conclusion. Use \
headings or bullets only when they help.
10. Sources. If you used the notes, end with a line in this form: \
*Source: BUSB5020 Financial Reporting, Week 4 Lecture*
11. Seminar slides and solutions contain fictional practice scenarios (e.g. "A v B", "E v F").\
Never cite these as legal authorities or real cases. For cases, definitions and principles, rely on lecture slides. \
Use seminar material only to show how a principle is applied, and say it is a seminar scenario.
12. Your Personality: You are very British, You are banter heavy and often go back and forth with your student, You are very very very very rude: sarcastic, cheeky, mock-exasperated, like a teacher who secretly loves their students but would rather die than admit it. You swear casually and regularly, especially when explaining concepts.You consistently add rude/ offensive jokes during conversation
""" + "\n\n" + PERSONALITY + "\n\n" + format_examples() + """

Context:
{context}

Before answering, check: every fact in the main answer comes from the context above, and everything \
else is under "⚠️ Outside your notes (general knowledge):"."""


class Result(BaseModel):
    page_content: str
    metadata: dict


class RankOrder(BaseModel):
    order: list[int] = Field(
        description="The order of relevance of chunks, from most relevant to least relevant, by chunk id number"
    )


@retry(wait=wait, stop=stop_after_attempt(3))
def rerank(question, chunks):
    system_prompt = """You are a re-ranker for a RAG system over my university lecture slides, seminar slides \
and seminar solutions. You get a question and numbered chunks. Rank the chunks by how useful each one is \
for answering the question, most useful first.

How to judge usefulness:
1. Answers beat mentions. Rank chunks that directly contain the answer (the facts, definition, figures, \
case details, method or worked solution) above chunks that only mention the topic, such as agendas, \
summaries and learning objectives.
2. Meaning, not wording. Questions are often phrased in everyday language rather than the notes' \
terminology. Work out which concept is being asked about, and rank chunks on that concept even if they \
share few words with the question.
3. Specific beats general. If the question names a module, case, company, standard or worked example, \
rank chunks about exactly that above similar material from elsewhere.
4. Calculations. If the question refers to a specific scenario, rank that scenario's worked figures first, \
then the method. If it asks how to calculate something in general, rank the method first, then a worked \
example.
5. Cover every part. If the question has several parts or spans topics, make sure the top positions \
include at least one chunk for each part. Only push a chunk down if it repeats information already \
ranked above it.
6. Ignore the input order. The chunks arrive in vector-similarity order, which is often wrong. Judge each \
chunk on its content alone.
Return every chunk id exactly once, ranked, and nothing else.
7. For questions about a case, definition or principle, rank lecture-slide chunks above seminar scenarios; for application or calculation questions, seminar solutions can rank highly."""
    user_prompt = f"The user has asked the following question:\n\n{question}\n\nOrder all the chunks of text by relevance to the question, from most relevant to least relevant. Include all the chunk ids you are provided with, reranked.\n\n"
    user_prompt += "Here are the chunks:\n\n"
    for index, chunk in enumerate(chunks):
        user_prompt += f"# CHUNK ID: {index + 1}:\n\n{chunk.page_content}\n\n"
    user_prompt += "Reply only with the list of ranked chunk ids, nothing else."
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    response = completion(model=RERANK_MODEL, messages=messages, response_format=RankOrder)
    reply = response.choices[0].message.content
    order = RankOrder.model_validate_json(reply).order
    seen = []
    for i in order:
        if 1 <= i <= len(chunks) and i not in seen:
            seen.append(i)
    seen += [i for i in range(1, len(chunks) + 1) if i not in seen]
    return [chunks[i - 1] for i in seen]


def make_rag_messages(question, history, chunks):
    history = [{"role": h["role"], "content": h["content"]} for h in history]
    context = "\n\n".join(
        f"Extract from {chunk.metadata['source']}:\n{chunk.page_content}" for chunk in chunks
    )
    system_prompt = SYSTEM_PROMPT.format(context=context)
    return (
        [{"role": "system", "content": system_prompt}]
        + history
        + [{"role": "user", "content": question}]
    )

def answer_question(question: str, history: list[dict] | None = None) -> tuple[str, list]:
    history = history or []

def merge_chunks(chunks, reranked):
    merged = chunks[:]
    existing = [chunk.page_content for chunk in chunks]
    for chunk in reranked:
        if chunk.page_content not in existing:
            merged.append(chunk)
    return merged


def fetch_context_unranked(question):
    query = openai.embeddings.create(model=embedding_model, input=[question]).data[0].embedding
    results = collection.query(query_embeddings=[query], n_results=RETRIEVAL_K)
    chunks = []
    for result in zip(results["documents"][0], results["metadatas"][0]):
        chunks.append(Result(page_content=result[0], metadata=result[1]))
    return chunks


def fetch_context(original_question, history=None):
    chunks = fetch_context_unranked(original_question)
    reranked = rerank(original_question, chunks)
    return reranked[:FINAL_K]


@retry(wait=wait, stop=stop_after_attempt(3))
def answer_question(question: str, history: list[dict] = []) -> tuple[str, list]:
    """
    Answer a question using RAG and return the answer and the retrieved context
    """
    chunks = fetch_context(question, history)
    messages = make_rag_messages(question, history, chunks)
    response = completion(model=MODEL, messages=messages, reasoning_effort="low")
    return response.choices[0].message.content, chunks

def stream_answer(question, history=[]):
    chunks = fetch_context(question, history)
    messages = make_rag_messages(question, history, chunks)
    response = completion(model=MODEL, messages=messages, reasoning_effort="low", stream=True)
    for chunk in response:
        piece = chunk.choices[0].delta.content
        if piece:
            yield piece

if __name__ == "__main__":
    answer, chunks = answer_question("Explain to me what parenting advantage is in strategic management?")
    print(answer)
    print("\nSources:")
    for chunk in chunks:
        print("-", chunk.metadata["source"])