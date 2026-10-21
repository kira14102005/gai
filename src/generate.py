import argparse
import json
import re
from pathlib import Path

import ollama

from .retrieve import get_staged_diff, retrieve_commits

# The prompt contains natural-language SQL-like phrases that trigger S608.

ROOT_DIR = Path(__file__).resolve().parent.parent
METADATA_PATH = ROOT_DIR / "vectorstore" / "metadata.json"

GENERATION_MODEL = "gemma4"
DEFAULT_TOP_K = 5
MAX_DIFF_CHARS = 10000
MAX_EXAMPLE_DIFF_CHARS = 600


def request_commit_message(prompt, valid_tags):
    response = ollama.chat(
        model=GENERATION_MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.1, "num_predict": 80},
        keep_alive="10m",
        stream=False,
    )
    print(f"Gemma raw response: {response.message.content}")

    content = getattr(response, "message", None)
    content = getattr(content, "content", None)

    if content is None and isinstance(response, dict):
        content = response.get("message", {}).get("content")

    if not isinstance(content, str) or not content.strip():
        raise ValueError("Gemma returned an empty response.")

    return parse_commit_message(content, valid_tags)


def build_prompt(diff, examples, valid_tags, retry_feedback=None):
    examples_text = "\n".join(
        f"- {example['tag']}: {example['message']}" for example in examples[:3]
    )

    tags_text = ", ".join(valid_tags)
    current_diff = truncate_diff(diff, 8000)

    feedback = (
        f"\nYour previous response was rejected: {retry_feedback}\n"
        if retry_feedback
        else ""
    )

    return f"""Generate one Git commit message for the code changes below.

Allowed tags: {tags_text}

Examples of this repository's commit messages:
{examples_text}

Rules:
1. Understand the CURRENT DIFF before writing the message.
2. Describe what the diff actually changes, not your general instructions.
3. Choose one allowed tag, preserving its exact spelling.
4. Keep the message specific and concise.
5. Output exactly one line: tag: message
6. Do not explain your answer or repeat these instructions.
7. Never output a generic assistant response.
{feedback}
CURRENT DIFF:
{current_diff}

Commit message:"""


def validate_generated_message(output, valid_tags):
    message = parse_commit_message(output, valid_tags)
    _, text = message.split(":", 1)
    text = text.strip()
    normalized = text.lower().strip(" .!")

    generic_phrases = [
        "you are a helpful assistant",
        "i am a helpful assistant",
        "i'm a helpful assistant",
        "how can i help you",
        "i can help you with that",
        "answers questions in concise and accurate manner",
    ]

    if any(phrase in normalized for phrase in generic_phrases):
        raise ValueError(
            "The output is a generic assistant response, not a description "
            "of the code changes."
        )

    if len(text.split()) < 3:
        raise ValueError("The commit message is too vague or too short.")

    return message


def generate_commit_message(diff, top_k=3, retrieval_diff=None):
    if not isinstance(diff, str) or not diff.strip():
        raise ValueError("Cannot generate a commit message from an empty diff.")

    valid_tags = load_valid_tags()
    examples = retrieve_commits(
        retrieval_diff if retrieval_diff is not None else diff,
        top_k=top_k,
    )
    prompt = build_prompt(diff, examples, valid_tags)

    system_prompt = (
        "You are a Git commit-message generator. "
        "Your only task is to describe the supplied code diff. "
        "Never respond as a general-purpose assistant. "
        "Return exactly one line in the format tag: message."
    )

    for attempt in range(2):
        response = ollama.chat(
            model=GENERATION_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            options={
                "temperature": 0.8,
                "num_predict": 100,
            },
            keep_alive="10m",
        )

        content = getattr(response, "message", None)
        content = getattr(content, "content", None)

        if content is None and isinstance(response, dict):
            content = response.get("message", {}).get("content")

        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Gemma returned an empty response.")

        print(f"Gemma raw response: {content.strip()}")

        try:
            return validate_generated_message(content, valid_tags)
        except ValueError as exc:
            if attempt == 1:
                raise RuntimeError(
                    f"Gemma failed to generate a valid commit message: {exc}"
                ) from exc

            prompt = build_prompt(
                diff,
                examples,
                valid_tags,
                retry_feedback=str(exc),
            )

    raise RuntimeError("Commit message generation failed.")


def load_valid_tags():
    if not METADATA_PATH.exists():
        raise FileNotFoundError(f"Metadata file not found: {METADATA_PATH}")

    with METADATA_PATH.open(encoding="utf-8") as f:
        metadata = json.load(f)

    tags = sorted(
        {
            commit["tag"].strip()
            for commit in metadata
            if isinstance(commit.get("tag"), str) and commit["tag"].strip()
        }
    )

    if not tags:
        raise ValueError("No historical tags found in metadata.")

    return tags


def truncate_diff(diff, max_chars):
    if len(diff) <= max_chars:
        return diff

    half = max_chars // 2
    return diff[:half] + "\n\n... [diff truncated] ...\n\n" + diff[-half:]


def parse_commit_message(output, valid_tags):
    output = output.strip()
    output = re.sub(r"^```(?:text)?\s*|\s*```$", "", output, flags=re.IGNORECASE)
    output = output.strip()

    if "\n" in output:
        output = output.splitlines()[0].strip()

    if output.lower().startswith("commit message:"):
        output = output.split(":", 1)[1].strip()

    if ":" not in output:
        raise ValueError("Output must follow the format 'tag: message'.")

    tag, message = output.split(":", 1)
    tag = tag.strip().strip("`*")
    message = message.strip().strip("`").strip()

    if tag not in valid_tags:
        raise ValueError(f"Unknown tag '{tag}'. Choose an exact historical tag.")

    if not message:
        raise ValueError("Generated commit message is empty.")

    if "\n" in message:
        raise ValueError("Commit message must be a single line.")

    return f"{tag}: {message}"


def main():
    parser = argparse.ArgumentParser(
        description="Generate a commit message using FAISS retrieval and Gemma."
    )
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--diff-file", type=Path)
    args = parser.parse_args()

    if args.top_k < 1:
        parser.error("--top-k must be at least 1")

    diff = (
        args.diff_file.read_text(encoding="utf-8")
        if args.diff_file
        else get_staged_diff()
    )

    print("Generating commit message...\n")
    message = generate_commit_message(diff, top_k=args.top_k)

    print(f"Suggested commit message:\n{message}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        raise SystemExit(f"Error: {exc}") from exc
