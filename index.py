import json
import os

import faiss
import numpy as np
import ollama


DATA_PATH = "data/commit_messages.json"
VECTORSTORE_PATH = "vectorstore"
INDEX_PATH = os.path.join(VECTORSTORE_PATH, "commits.index")
METADATA_PATH = os.path.join(VECTORSTORE_PATH, "metadata.json")

EMBEDDING_MODEL = "embeddinggemma:latest"


def load_commits():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_embedding(text):
    response = ollama.embed(
        model=EMBEDDING_MODEL,
        input=text,
    )

    return response["embeddings"][0]


def build_index(commits):
    embeddings = []

    for i, commit in enumerate(commits):
        print(f"Embedding {i + 1}/{len(commits)}")

        diff = commit["diff"]

        embedding = get_embedding(diff)
        embeddings.append(embedding)

    embeddings = np.array(
        embeddings,
        dtype=np.float32,
    )

    dimension = embeddings.shape[1]

    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)

    return index


def main():
    os.makedirs(VECTORSTORE_PATH, exist_ok=True)
    commits = load_commits()
    print(f"Loaded {len(commits)} commits")

    index = build_index(commits)

    faiss.write_index(index, INDEX_PATH)

    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(commits, f, indent=2, ensure_ascii=False)

    print()
    print("Vector store created successfully.")
    print(f"Index:    {INDEX_PATH}")
    print(f"Metadata: {METADATA_PATH}")
    print(f"Vectors:  {index.ntotal}")


if __name__ == "__main__":
    main()