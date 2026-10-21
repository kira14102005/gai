import argparse
import json
import subprocess
from pathlib import Path

import faiss
import numpy as np
import ollama

ROOT_DIR = Path(__file__).resolve().parent.parent
VECTORSTORE_PATH = ROOT_DIR / "vectorstore"
INDEX_PATH = VECTORSTORE_PATH / "commits.index"
METADATA_PATH = VECTORSTORE_PATH / "metadata.json"

EMBEDDING_MODEL = "embeddinggemma:latest"
DEFAULT_TOP_K = 5


def load_vectorstore():
    for path in [INDEX_PATH, METADATA_PATH]:
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

    index = faiss.read_index(str(INDEX_PATH))

    with METADATA_PATH.open(encoding="utf-8") as f:
        metadata = json.load(f)

    if not isinstance(metadata, list):
        raise TypeError("Metadata must be a JSON list.")

    if index.ntotal != len(metadata):
        msg = (
            f"Index contains {index.ntotal} vectors, "
            f"but metadata contains {len(metadata)} commits."
        )
        raise ValueError(msg)

    if index.ntotal == 0:
        raise ValueError("FAISS index is empty.")

    return index, metadata


def get_embedding(text):
    if not isinstance(text, str):
        raise TypeError("Embedding input must be a string.")
    if not text.strip():
        raise ValueError("Cannot generate an embedding for an empty diff.")

    try:
        response = ollama.embed(model=EMBEDDING_MODEL, input=text)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to generate embedding using {EMBEDDING_MODEL}."
        ) from exc

    embeddings = getattr(response, "embeddings", None)

    if embeddings is None and isinstance(response, dict):
        embeddings = response.get("embeddings")

    if not embeddings or len(embeddings) != 1:
        raise RuntimeError("Ollama returned no valid query embedding.")

    vector = np.asarray(embeddings[0], dtype=np.float32).reshape(1, -1)

    if vector.shape[1] == 0 or not np.isfinite(vector).all():
        raise ValueError("Embedding contains invalid values.")

    if np.linalg.norm(vector) == 0:
        raise ValueError("Embedding has zero magnitude.")

    return vector


def retrieve_commits(diff, top_k=DEFAULT_TOP_K):
    if not isinstance(diff, str) or not diff.strip():
        raise ValueError("Diff is empty. Stage changes before running gai.")

    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    index, metadata = load_vectorstore()
    query_vector = get_embedding(diff)

    if query_vector.shape[1] != index.d:
        raise ValueError(
            f"Embedding dimension mismatch: query has {query_vector.shape[1]}, "
            f"index expects {index.d}. Rebuild the index with the same model."
        )

    k = min(top_k, index.ntotal)
    distances, indices = index.search(query_vector, k)

    results = []

    for rank, (distance, idx) in enumerate(
        zip(distances[0], indices[0], strict=True), start=1
    ):
        if idx < 0:
            continue

        commit = metadata[int(idx)]

        results.append(
            {
                "rank": rank,
                "distance": float(distance),
                "tag": commit.get("tag", ""),
                "message": commit.get("message", ""),
                "diff": commit.get("diff", ""),
            }
        )

    return results


def get_staged_diff():
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--no-ext-diff", "--unified=3"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Git is not installed or is not on PATH.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Could not read staged diff: {exc.stderr}") from exc

    diff = result.stdout

    # diff_path = Path.cwd() / "git_diff.txt"
    # diff_path.write_text(diff, encoding="utf-8")

    if not diff.strip():
        raise ValueError(
            "No staged changes found. The empty diff was saved to git_diff.txt."
        )

    return diff


def main():
    parser = argparse.ArgumentParser(
        description="Retrieve similar historical commits using FAISS."
    )
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--diff-file", type=Path)
    args = parser.parse_args()

    if args.top_k < 1:
        parser.error("--top-k must be at least 1")

    if args.diff_file:
        diff = args.diff_file.read_text(encoding="utf-8")
    else:
        diff = get_staged_diff()

    results = retrieve_commits(diff, args.top_k)
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        raise SystemExit(f"Error: {exc}") from exc
