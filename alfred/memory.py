import chromadb
import hashlib
from config import CHROMA_PATH

client = chromadb.PersistentClient(path=str(CHROMA_PATH))
collection = client.get_or_create_collection(name="alfred_memory")

# Before 2026-09-25 Alfred also stored its OWN replies here. Those are
# excluded from recall so they can't come back as "facts about Jay".
EXCLUDED_TYPES = ["alfred_response"]


def memory_id(text):
    # hash() is randomised every time Python starts, so the same text
    # would get a new id after each restart. sha256 is always identical.
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def store_memory(text, metadata):
    collection.upsert(documents=[text], metadatas=[metadata], ids=[memory_id(text)])


def retrieve_memories(query, n_results=3):
    usable = collection.get(where={"type": {"$nin": EXCLUDED_TYPES}}, include=[])["ids"]
    if not usable:
        return {"documents": [[]], "metadatas": [[]]}
    return collection.query(
        query_texts=[query],
        n_results=min(n_results, len(usable)),
        where={"type": {"$nin": EXCLUDED_TYPES}},
    )


def purge_assistant_memories():
    """One-off cleanup: permanently delete Alfred's old stored replies."""
    old = collection.get(where={"type": {"$in": EXCLUDED_TYPES}}, include=[])["ids"]
    if old:
        collection.delete(ids=old)
    return len(old)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "purge-assistant":
        print(f"Deleted {purge_assistant_memories()} old Alfred replies from memory.")
    else:
        results = collection.get(where={"type": {"$nin": EXCLUDED_TYPES}})
        for doc in results["documents"]:
            print("-", doc)
