import json
import os

def process_commits(input_file: str, output_json: str):
    """Reads raw commits from txt and generates structured json"""
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file '{input_file}' not found.")

    commit_list = []
    unique_tags = set()

    with open(input_file, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if not line or line.startswith("---"):
            continue

        if ":" in line:
            tag, message = line.split(":", 1)
            tag = tag.strip().lower()
            message = message.strip()
        else:
            continue

        unique_tags.add(tag)
        commit_list.append({"tag": tag, "message": message})

    os.makedirs(os.path.dirname(output_json), exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(commit_list, f, indent=2, ensure_ascii=False)

    print(f"[2/2 Process] Found {len(unique_tags)} unique tags: {sorted(list(unique_tags))}")
    print(f"[2/2 Process] Saved {len(commit_list)} commits to '{output_json}'")