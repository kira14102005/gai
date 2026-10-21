from __future__ import annotations

import re
from typing import Any

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")


def _git_path(value: str) -> str:
    """Normalize a path from Git's diff header."""
    value = value.strip()

    # Git quotes unusual paths. Full C-style unquoting is deliberately
    # not attempted here; see the limitations noted below.
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]

    return value.replace("\\", "/")


def _header_path(line: str, prefix: str) -> str | None:
    if not line.startswith(prefix):
        return None

    value = line[len(prefix) :]

    # For standard unified diff headers, timestamps follow a tab.
    value = value.split("\t", 1)[0].strip()

    if value == "/dev/null":
        return None

    return _git_path(value)


def parse_diff(diff: str) -> dict[str, Any]:
    """Parse a unified Git diff into file and hunk records."""
    result: dict[str, Any] = {
        "files": [],
        "stats": {
            "files_changed": 0,
            "insertions": 0,
            "deletions": 0,
        },
    }

    current_file: dict[str, Any] | None = None
    current_hunk: dict[str, Any] | None = None
    old_remaining = 0
    new_remaining = 0
    in_hunk = False

    def finish_hunk() -> None:
        nonlocal current_hunk, in_hunk
        current_hunk = None
        in_hunk = False

    def finish_file() -> None:
        nonlocal current_file
        if current_file is not None:
            result["files"].append(current_file)
            current_file = None

    lines = diff.splitlines()

    for line in lines:
        if line.startswith("diff --git "):
            finish_hunk()
            finish_file()

            # Git's normal header is: diff --git a/path b/path.
            # Paths containing spaces/quotes need Git's quoting rules;
            # the fallback here is suitable for ordinary repository paths.
            match = re.match(r"^diff --git a/(.*?) b/(.*)$", line)
            old_path = match.group(1) if match else ""
            new_path = match.group(2) if match else old_path

            current_file = {
                "old_path": _git_path(old_path) if old_path else None,
                "path": _git_path(new_path) if new_path else None,
                "status": "modified",
                "binary": False,
                "hunks": [],
                "added_lines": [],
                "removed_lines": [],
            }
            continue

        if current_file is None:
            continue

        if line.startswith("new file mode "):
            current_file["status"] = "added"
        elif line.startswith("deleted file mode "):
            current_file["status"] = "deleted"
        elif line.startswith("rename from "):
            current_file["old_path"] = _git_path(line[len("rename from ") :])
            current_file["status"] = "renamed"
        elif line.startswith("rename to "):
            current_file["path"] = _git_path(line[len("rename to ") :])
            current_file["status"] = "renamed"
        elif line.startswith("Binary files ", "GIT binary patch"):
            current_file["binary"] = True
            finish_hunk()
        elif line.startswith("--- "):
            old_path = _header_path(line, "--- ")
            if old_path is not None:
                current_file["old_path"] = old_path
        elif line.startswith("+++ "):
            new_path = _header_path(line, "+++ ")
            if new_path is not None:
                current_file["path"] = new_path

        hunk_match = HUNK_RE.match(line)
        if hunk_match:
            finish_hunk()
            old_start = int(hunk_match.group(1))
            old_count = int(hunk_match.group(2) or 1)
            new_start = int(hunk_match.group(3))
            new_count = int(hunk_match.group(4) or 1)

            current_hunk = {
                "header": line,
                "old_start": old_start,
                "old_count": old_count,
                "new_start": new_start,
                "new_count": new_count,
                "section": hunk_match.group(5).strip(),
                "added": [],
                "removed": [],
                "context": [],
            }
            current_file["hunks"].append(current_hunk)
            old_remaining = old_count
            new_remaining = new_count
            in_hunk = True
            continue

        if not in_hunk or current_hunk is None:
            continue

        # This is metadata, not a changed source line.
        if line.startswith("\\ No newline at end of file"):
            continue

        if line.startswith("+"):
            content = line[1:]
            current_hunk["added"].append(content)
            current_file["added_lines"].append(content)
            result["stats"]["insertions"] += 1
            new_remaining -= 1
        elif line.startswith("-"):
            content = line[1:]
            current_hunk["removed"].append(content)
            current_file["removed_lines"].append(content)
            result["stats"]["deletions"] += 1
            old_remaining -= 1
        elif line.startswith(" "):
            current_hunk["context"].append(line[1:])
            old_remaining -= 1
            new_remaining -= 1
        else:
            # An unexpected line means we should stop interpreting this
            # section as hunk content rather than misclassifying metadata.
            finish_hunk()
            continue

        if old_remaining <= 0 and new_remaining <= 0:
            finish_hunk()

    finish_hunk()
    finish_file()

    result["stats"]["files_changed"] = len(result["files"])

    for file in result["files"]:
        if (
            file["status"] == "modified"
            and file["old_path"] is None
            and file["path"] is not None
        ):
            file["old_path"] = file["path"]

    return result


def format_changes(parsed: dict[str, Any]) -> str:
    """Render a readable, change-focused representation for an LLM."""
    sections: list[str] = []

    for file in parsed["files"]:
        sections.append(
            f"FILE: {file['path'] or file['old_path'] or '(unknown path)'}\n"
            f"STATUS: {file['status']}\n"
            f"BINARY: {file['binary']}"
        )

        for number, hunk in enumerate(file["hunks"], start=1):
            sections.append(f"HUNK {number}: {hunk['section'] or hunk['header']}")

            if hunk["removed"]:
                sections.append(
                    "REMOVED (-):\n"
                    + "\n".join(f"- {line}" for line in hunk["removed"])
                )

            if hunk["added"]:
                sections.append(
                    "ADDED (+):\n" + "\n".join(f"+ {line}" for line in hunk["added"])
                )

            if hunk["context"]:
                sections.append(
                    "CONTEXT (unchanged):\n"
                    + "\n".join(f"  {line}" for line in hunk["context"])
                )

    stats = parsed["stats"]
    sections.append(
        "DIFF STATS:\n"
        f"Files changed: {stats['files_changed']}\n"
        f"Insertions: {stats['insertions']}\n"
        f"Deletions: {stats['deletions']}"
    )

    return "\n\n".join(sections)
