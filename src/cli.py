from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from src.generate import generate_commit_message
from src.retrieve import get_staged_diff
from src.utils.diff_parser import format_changes, parse_diff

DIFF_SNAPSHOT_PATH = Path.cwd() / "src" / "diffs" / f"git_diff{int(time.time())}.txt"


class CliError(RuntimeError):
    pass


def run_git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            ["git", *args],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise CliError(
            "Git was not found. Install Git for Windows and reopen your terminal."
        ) from exc

    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "Unknown Git error."
        raise CliError(detail)
    return result


def ensure_git_repository() -> None:
    result = run_git("rev-parse", "--is-inside-work-tree", check=False)
    if result.returncode != 0 or result.stdout.strip() != "true":
        raise CliError("Run gai from inside a Git repository.")


def staged_diff() -> str:
    # retrieve.get_staged_diff() is responsible for writing git_diff.txt.
    diff = get_staged_diff()
    if not isinstance(diff, str) or not diff.strip():
        raise CliError(
            "No staged changes found. Stage changes first with: git add <files>"
        )
    return diff


def diff_fingerprint(diff: str) -> str:
    return hashlib.sha256(diff.encode("utf-8", errors="replace")).hexdigest()


def current_staged_diff() -> str:
    result = run_git("diff", "--cached", "--no-ext-diff", "--unified=3")
    return result.stdout


def validate_message(message: str) -> tuple[bool, str]:
    message = message.strip()
    if not message:
        return False, "Commit message cannot be empty."
    if "\n" in message or "\r" in message:
        return False, "Use a single-line commit message."
    if ":" not in message:
        return False, "Expected format: tag: message"

    tag, body = message.split(":", 1)
    tag, body = tag.strip(), body.strip()
    if not tag or not body:
        return False, "Expected a non-empty tag and message in 'tag: message' format."

    # Validate against the historical tags in the existing vector-store metadata.
    metadata_path = (
        Path(__file__).resolve().parent.parent / "vectorstore" / "metadata.json"
    )
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            valid_tags = {
                str(item.get("tag", "")).strip() for item in metadata if item.get("tag")
            }
        except (OSError, json.JSONDecodeError, AttributeError, TypeError):
            valid_tags = set()

        if valid_tags and tag not in valid_tags:
            return (
                False,
                f"Unknown tag '{tag}'. Use one of the tags from vectorstore/metadata.json.",
            )

    return True, ""


def generate(diff: str, top_k: int) -> str:
    print("\nRetrieving similar historical commits and generating a message...")
    message = generate_commit_message(diff, top_k=top_k)
    if not isinstance(message, str) or not message.strip():
        raise CliError(
            "The generator did not return a valid message. Check generate.py output, "
            "Ollama status, and that the configured models are available."
        )
    message = message.strip()
    valid, reason = validate_message(message)
    if not valid:
        raise CliError(
            f"Generated message failed CLI validation: {reason}\nReceived: {message}"
        )
    return message


def edit_message(message: str) -> str | None:
    print("\nEnter the complete replacement message on one line.")
    print("Press Enter without typing anything to return to the menu.")
    edited = input("Message> ").strip()
    if not edited:
        return None
    valid, reason = validate_message(edited)
    if not valid:
        print(f"Invalid message: {reason}")
        return None
    return edited


def commit_if_unchanged(message: str, original_diff: str) -> None:
    latest_diff = current_staged_diff()
    if not latest_diff.strip():
        raise CliError(
            "The Git index has no staged changes now. Nothing was committed."
        )
    if diff_fingerprint(latest_diff) != diff_fingerprint(original_diff):
        raise CliError(
            "Staged changes changed after the message was generated. Nothing was committed. "
            "Run gai again to generate a message for the current staged diff."
        )

    print("\nCommitting staged changes...")
    result = run_git("commit", "-m", message, check=False)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    if result.returncode != 0:
        raise CliError(
            "git commit failed; your staged changes have not been discarded."
        )


def interactive_loop(
    raw_diff: str, formatted_diff: str, top_k: int, initial_message: str
) -> int:
    message = initial_message

    while True:
        print("\nSuggested commit:")
        print(f"  {message}")
        print("\n[Y] Accept and commit   [e] Edit   [r] Regenerate   [n] Cancel")
        choice = input("> ").strip().lower()

        if choice in {"y", "yes"}:
            commit_if_unchanged(message, raw_diff)
            return 0
        if choice in {"e", "edit"}:
            edited = edit_message(message)
            if edited:
                message = edited
            continue
        if choice in {"r", "regenerate"}:
            try:
                message = generate_commit_message(
                    formatted_diff,
                    top_k=top_k,
                    retrieval_diff=raw_diff,
                )
            except CliError as exc:
                print(f"\nGeneration failed: {exc}", file=sys.stderr)
                retry = input("Try generating again? [y/N] ").strip().lower()
                if retry not in {"y", "yes"}:
                    return 1
            continue
        if choice in {"n", "no", "q", "quit", "cancel"}:
            print("Cancelled. No commit was created.")
            return 0

        print("Choose Y, e, r, or n.")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="gai",
        description="Generate a commit message from staged changes using local Ollama models.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of similar commits to retrieve (default: 5).",
    )
    args = parser.parse_args()

    if args.top_k < 1:
        parser.error("--top-k must be at least 1.")

    try:
        ensure_git_repository()
        print("Reading staged changes...")
        raw_diff = staged_diff()
        formatted_diff = format_changes(parse_diff(raw_diff))

        print("\nFormatted diff for generation:")
        print(formatted_diff)

        message = generate_commit_message(
            formatted_diff,
            top_k=args.top_k,
            retrieval_diff=raw_diff,
        )
        print(f"Saved staged diff to: {DIFF_SNAPSHOT_PATH}")
        return interactive_loop(raw_diff, formatted_diff, args.top_k, message)
    except (CliError, OSError, ValueError) as exc:
        print(f"\ngai: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted. No commit was created.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
