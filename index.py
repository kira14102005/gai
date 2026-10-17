from email.mime import text
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
    response = ollama.embed(model=EMBEDDING_MODEL, input=text)

    embeddings = response["embeddings"]

    if not embeddings:
        raise ValueError(f"Ollama returned no embedding for input of length {len(text)}")

    return embeddings[0]


def build_index(commits):
    embeddings = []
    valid_commits = []

    for i, commit in enumerate(commits):
        diff = commit.get("diff", "")

        if not diff.strip():
            print(f"Skipping {i + 1}/{len(commits)}: {commit.get('tag', '')}: {commit.get('message', '')} (empty diff)")
            continue

        print(f"Embedding {i + 1}/{len(commits)}...")
        text = f"title: {commit['tag']}: {commit['message']} | text: {diff}"
        embedding = get_embedding(text)

        embeddings.append(embedding)
        valid_commits.append(commit)

    if not embeddings:
        raise RuntimeError("No valid commits were found.")

    embeddings = np.array(embeddings, dtype=np.float32)
    dimension = embeddings.shape[1]

    print(f"\nEmbedding dimension: {dimension}")
    print(f"Valid commits: {len(valid_commits)}")

    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)

    return index, valid_commits


def save_vectorstore(index, metadata):
    os.makedirs(VECTORSTORE_PATH, exist_ok=True)

    faiss.write_index(index, INDEX_PATH)

    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)


def main():
    commits = load_commits()
    print(f"Loaded {len(commits)} commits.")

    index, metadata = build_index(commits)
    save_vectorstore(index, metadata)

    print("\nVector store created successfully.")
    print(f"Vectors:  {index.ntotal}")
    print(f"Index:    {INDEX_PATH}")
    print(f"Metadata: {METADATA_PATH}")


if __name__ == "__main__":
    main()