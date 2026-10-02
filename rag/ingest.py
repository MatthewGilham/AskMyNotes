from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from pydantic import BaseModel
from chromadb import PersistentClient
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv(override=True)




DB_NAME = str(Path(__file__).parent.parent / "vector_db")
collection_name = "docs"
embedding_model = "text-embedding-3-large"
# embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
KNOWLEDGE_BASE_PATH = Path(__file__).parent.parent / "knowledge_base"
AVERAGE_CHUNK_SIZE = 1250
AVERAGE_CHUNK_OVERLAP = 200

openai = OpenAI()

class Result(BaseModel):
    page_content: str
    metadata: dict



def fetch_documents():
    documents = []
    for file in KNOWLEDGE_BASE_PATH.rglob("*.md"):
        parts = file.relative_to(KNOWLEDGE_BASE_PATH).parts
        text = file.read_text(encoding="utf-8")
        if len(text) < 200:
            continue
        documents.append({
            "type": parts[0],                                  # the year folder
            "module": parts[1] if len(parts) > 2 else "",      # the module folder, if there is one
            "source": file.as_posix(),
            "text": text,
            "kind": parts[2] if len(parts) > 3 else "",   # Lecture Slides / Seminar Slides / Seminar Solutions
        })
    print(f"Loaded {len(documents)} documents")
    return documents


splitter = RecursiveCharacterTextSplitter(chunk_size=AVERAGE_CHUNK_SIZE, chunk_overlap=AVERAGE_CHUNK_OVERLAP)
def create_chunks(documents):
    chunks = []
    for document in documents:
        header = f"{document['module']} | {document['kind']} | {Path(document['source']).stem}"
        metadata = {"source": document["source"], "type": document["type"],
                    "module": document["module"], "kind": document["kind"]}
        for text in splitter.split_text(document["text"]):
            chunks.append(Result(page_content=f"{header}\n\n{text}", metadata=metadata))
    return chunks

def create_embeddings(chunks):
    chroma = PersistentClient(path=DB_NAME)
    if collection_name in [c.name for c in chroma.list_collections()]:
        chroma.delete_collection(collection_name)
    collection = chroma.get_or_create_collection(collection_name)

    for i in range(0, len(chunks), 500):
        batch = chunks[i:i + 500]
        texts = [chunk.page_content for chunk in batch]
        emb = openai.embeddings.create(model=embedding_model, input=texts).data
        collection.add(
            ids=[str(i + j) for j in range(len(batch))],
            embeddings=[e.embedding for e in emb],
            documents=texts,
            metadatas=[chunk.metadata for chunk in batch],
        )
        print(f"Embedded {i + len(batch)}/{len(chunks)}")

    print(f"Vectorstore created with {collection.count()} documents")




if __name__ == "__main__":
    documents = fetch_documents()
    chunks = create_chunks(documents)
    print(f"Created {len(chunks)} chunks")
    create_embeddings(chunks)
    print("Ingestion complete")
