"""The notes database: Chroma, stored in `data/chroma/`.

Embeddings always come from OpenAI (or the fake used by tests). Chroma's own
built-in embedding function is switched off, because it would download a model
into the user folder, and so is Chroma's usage reporting.
"""

from pathlib import Path
from typing import Literal

import chromadb
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel, ConfigDict

from askmynotes.notes.chunking import Chunk
from askmynotes.notes.embeddings import CountingOpenAIEmbeddings
from askmynotes.settings import EnvSettings

COLLECTION = "notes"
# How hard Chroma's approximate search looks. Its default sometimes missed the
# best slide altogether, and which slides came back varied from one start of the
# app to the next. At 500 the search was measured against exact search and
# found the best slide every time.
SEARCH_EFFORT = 500
# Some slide files exist more than once (copies), so a search asks for extra
# results to still have enough after the repeats are dropped.
DUPLICATE_ALLOWANCE = 3


def create_embeddings(env: EnvSettings) -> Embeddings:
    """The real embedding model, from the model name and key in `.env`."""
    # Unlike LangChain's own class, this one reports the tokens each request
    # used. It also skips LangChain's length check, which counts tokens with
    # tiktoken and downloads its encoding files into the Windows temp folder;
    # chunks are far below the model's limit (see max_chunk_characters).
    return CountingOpenAIEmbeddings(env.embedding_model, env.openai_api_key)


class NoteResult(BaseModel):
    """One chunk found by a search: where it came from, and its text."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str
    module: str
    file_name: str
    location: Literal["slide", "page"]
    number: int
    text: str


class EmbeddingModelChanged(Exception):
    """Raised when the database was built with a different embedding model.

    Vectors from two models can't be compared, so mixing them would make the
    search silently wrong.
    """


class NotesStore:
    """Adds, removes and searches note chunks."""

    def __init__(
        self, folder: Path, embeddings: Embeddings, embedding_model: str
    ) -> None:
        client = chromadb.PersistentClient(
            path=folder, settings=chromadb.Settings(anonymized_telemetry=False)
        )
        self._collection = client.get_or_create_collection(
            COLLECTION,
            embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}},
            metadata={"embedding_model": embedding_model},
        )
        built_with = (self._collection.metadata or {}).get("embedding_model")
        if built_with != embedding_model:
            raise EmbeddingModelChanged(
                f"The notes database in {folder} was built with the embedding model "
                f"{built_with!r}, but EMBEDDING_MODEL in .env is {embedding_model!r}. "
                f"Delete the {folder.name} folder to rebuild it with the new model."
            )
        # Saved with the collection, so it also applies to a database built before.
        self._collection.modify(configuration={"hnsw": {"ef_search": SEARCH_EFFORT}})
        self._embeddings = embeddings

    def add(self, chunks: list[Chunk]) -> None:
        """Embed chunks and store them."""
        if not chunks:
            return
        vectors = self._embeddings.embed_documents([c.text_to_embed for c in chunks])
        self._collection.add(
            ids=[c.id for c in chunks],
            embeddings=vectors,  # type: ignore[arg-type]
            documents=[c.text for c in chunks],
            metadatas=[c.metadata for c in chunks],  # type: ignore[arg-type]
        )

    def delete_file(self, file_id: str) -> None:
        """Remove every chunk of one file (none is fine)."""
        self._collection.delete(where={"file_id": file_id})

    def chunks_of(self, file_id: str) -> list[dict]:
        """The stored metadata of one file's chunks."""
        result = self._collection.get(where={"file_id": file_id}, include=["metadatas"])
        return [dict(m) for m in result["metadatas"] or []]

    def count(self) -> int:
        """How many chunks are stored."""
        return self._collection.count()

    def search(self, query: str, modules: list[str], count: int) -> list[NoteResult]:
        """The `count` chunks closest in meaning to `query`, best first.

        `modules` lists short names to search; an empty list searches them all.
        A slide that appears twice with identical text (a copied file) is
        returned once, so repeats don't take up the results.
        """
        result = self._collection.query(
            query_embeddings=[self._embeddings.embed_query(query)],
            n_results=count * DUPLICATE_ALLOWANCE,
            where={"module": {"$in": modules}} if modules else None,
            include=["documents", "metadatas"],
        )
        # Chroma answers a list of queries; [0] is the one query asked here.
        # Texts and metadata are there because `include` asks for them.
        ids = result["ids"][0]
        texts = result["documents"][0]  # type: ignore[index]
        metadatas = result["metadatas"][0]  # type: ignore[index]
        found: dict[str, NoteResult] = {}  # by text, so the first copy is kept
        for chunk_id, text, metadata in zip(ids, texts, metadatas, strict=True):
            if text not in found:
                found[text] = NoteResult.model_validate(
                    {**metadata, "chunk_id": chunk_id, "text": text}
                )
        return list(found.values())[:count]
