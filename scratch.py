
from chromadb import PersistentClient
from rag.ingest import DB_NAME, collection_name, embedding_model

chroma = PersistentClient(path=DB_NAME)
collection = chroma.get_collection(collection_name)


print(collection.get(limit=1, include=["metadatas"]))
