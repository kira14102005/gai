import json
import os

def process_commits(input_file: str, output_json: str):
    """Reads raw commits and diffs from txt and generates structured json"""
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file '{input_file}' not found.")

    commit_list = []
    unique_tags = set()

    with open(input_file, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Split content into individual commit blocks
    blocks = content.split("<<<COMMIT_START>>>")

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Split subject line and diff section
        if "<<<DIFF_START>>>" in block:
            msg_part, diff_part = block.split("<<<DIFF_START>>>", 1)
        else:
            msg_part, diff_part = block, ""

        # Clean block markers
        msg_part = msg_part.strip()
        diff_part = diff_part.replace("<<<COMMIT_END>>>", "").strip()

        # Ignore empty entries or header blocks
        if not msg_part or msg_part.startswith("--- Repository:"):
            continue

        # Parse tag and message
        if ":" in msg_part:
            tag, message = msg_part.split(":", 1)
            tag = tag.strip().lower()
            message = message.strip()
        else:
            continue  # Skip if no tag is found

        unique_tags.add(tag)
        commit_list.append({
            "tag": tag,
            "message": message,
            "diff": diff_part
        })

    os.makedirs(os.path.dirname(output_json), exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(commit_list, f, indent=2, ensure_ascii=False)

    print(f"[2/2 Process] Found {len(unique_tags)} unique tags: {sorted(list(unique_tags))}")
    print(f"[2/2 Process] Saved {len(commit_list)} commits to '{output_json}'")