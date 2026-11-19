"""The real embedding model, called through OpenAI's own library.

LangChain's `OpenAIEmbeddings` doesn't pass on how many tokens a request used,
and the cost indicators need that. This class sends the same requests (same
model, same text) and so gets the same vectors, so a notes database built
before it needs no rebuild. It also reports each request's token count to the
usage log in force (see `usage/log.py`), if there is one.
"""

import openai
from langchain_core.embeddings import Embeddings

from askmynotes.usage.log import report_embedding

# OpenAI accepts thousands of texts per request, but also caps the tokens per
# request, so a notes update sends modest batches. The vectors don't depend on
# how the texts are batched.
BATCH_SIZE = 100


class CountingOpenAIEmbeddings(Embeddings):
    """OpenAI embeddings that report the tokens they use."""

    def __init__(self, model: str, api_key: str) -> None:
        self._model = model
        self._client = openai.OpenAI(api_key=api_key)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            response = self._client.embeddings.create(
                model=self._model, input=texts[start : start + BATCH_SIZE]
            )
            report_embedding(self._model, response.usage.total_tokens)
            # `index` is each text's position in the batch.
            vectors.extend(
                item.embedding for item in sorted(response.data, key=lambda i: i.index)
            )
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]
