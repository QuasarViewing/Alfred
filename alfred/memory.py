import chromadb

client = chromadb.PersistentClient(path="chroma_db")
collection = client.get_or_create_collection(name="alfred_memory")


def store_memory(text, metadata):
    collection.add(documents=[text], metadatas=[metadata], ids=[str(hash(text))])


def retrieve_memories(query, n_results=3):
    return collection.query(query_texts=[query], n_results=n_results)

if __name__ == "__main__":
    store_memory("Jay loves sushi", {"type": "preference", "timestamp": "2026-03-08"})
    store_memory("Jay is learning Python", {"type": "observation", "timestamp": "2026-03-08"})

    results = retrieve_memories("What food does jay like")
    print(results)

# Peek at stored memories
# results = collection.get()
# for doc in results["documents"]:
#       print(doc)