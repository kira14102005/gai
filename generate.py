import argparse
import json
import re
from pathlib import Path

import ollama

from retrieve import get_staged_diff, retrieve_commits

# The prompt contains natural-language SQL-like phrases that trigger S608.

ROOT_DIR = Path(__file__).resolve().parent
METADATA_PATH = ROOT_DIR / "vectorstore" / "metadata.json"

GENERATION_MODEL = "gemma3:1b"
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


def build_prompt(diff, examples, valid_tags, correction=None):
    examples_text = []

    for example in examples:
        example_diff = truncate_diff(example["diff"], MAX_EXAMPLE_DIFF_CHARS)
        examples_text.append(
            f"Historical example {example['rank']}:\n"
            f"Tag: {example['tag']}\n"
            f"Message: {example['message']}\n"
            f"Diff excerpt:\n{example_diff}"
        )

    examples_text = "\n\n".join(examples_text)
    allowed_tags = ", ".join(valid_tags)
    current_diff = truncate_diff(diff, MAX_DIFF_CHARS)

    correction_text = (
        f"\nYour previous output was invalid: {correction}. "
        "Follow the required format exactly."
        if correction
        else ""
    )

    return (
        f"""You generate concise Git commit messages from staged diffs.

RULES:
- Describe the actual changes in the CURRENT DIFF.
- Use historical examples to learn the repository's commit-message style.
- Do not copy an example message unless it accurately describes the current changes.
- Select exactly one tag from the allowed tags below.
- Preserve tag spelling exactly, including compound tags containing '&'.
- Return exactly one line in this format: tag: message
- Do not include Markdown, quotes, explanations, or additional lines.
- Keep the message concise and specific.
- Do not invent changes that are absent from the current diff.

ALLOWED TAGS:
{allowed_tags}

CURRENT DIFF:
{current_diff}
{correction_text}

Return only the commit message in the required format."""
    )


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


def generate_commit_message(diff, top_k=DEFAULT_TOP_K):
    if not isinstance(diff, str) or not diff.strip():
        raise ValueError("Cannot generate a commit message from an empty diff.")

    valid_tags = load_valid_tags()
    examples = retrieve_commits(diff, top_k=top_k)

    prompt = build_prompt(diff, examples, valid_tags)

    for attempt in range(2):
        try:
            return request_commit_message(prompt, valid_tags)

        except ValueError as exc:
            if attempt == 1:
                raise RuntimeError(
                    f"Could not generate a valid commit message: {exc}"
                ) from exc

            prompt = build_prompt(diff, examples, valid_tags, correction=str(exc))

    raise RuntimeError("Commit message generation failed.")


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
